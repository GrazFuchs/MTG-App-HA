"""Triage advisor: computes keep-scores and suggestions for acquisition events."""
from __future__ import annotations

import logging
import sqlite3

from ..models.schemas import ExistingPrinting, TriageSuggestion

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION = TriageSuggestion(
    action="keep",
    reason="default — could not compute suggestion",
    sell_collection_id=None,
    estimated_price_eur=0.0,
    suggested_sell_price_eur=0.0,
)


async def compute_keep_score(price_eur: str, is_foil: bool) -> float:
    base = float(price_eur) if price_eur else 0.0
    return base * (1.5 if is_foil else 1.0)


async def _get_suggested_sell_price(db, card_name: str) -> float:
    """Return suggested sell price: prefer Cardmarket trend, fallback Scryfall price_eur."""
    cm_cursor = await db.execute("""
        SELECT cph.trend FROM cardmarket_price_history cph
        JOIN cardmarket_products cp ON cp.cm_product_id = cph.cm_product_id
        JOIN cards c ON c.id = cp.card_id
        WHERE c.name = ?
        ORDER BY cph.date DESC LIMIT 1
    """, (card_name,))
    cm_row = await cm_cursor.fetchone()
    if cm_row and cm_row["trend"]:
        return round(float(cm_row["trend"]), 2)

    scry_cursor = await db.execute("SELECT price_eur FROM cards WHERE name = ? LIMIT 1", (card_name,))
    scry_row = await scry_cursor.fetchone()
    try:
        return round(float(scry_row["price_eur"]), 2) if scry_row and scry_row["price_eur"] else 0.0
    except (ValueError, TypeError):
        return 0.0


async def _get_suggestion_impl(db, event_row) -> tuple[TriageSuggestion, list[ExistingPrinting], int]:
    """Internal implementation — see get_suggestion() for docs."""
    # 1. Fetch the card
    cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (event_row["card_id"],))
    new_card = await cursor.fetchone()
    if not new_card:
        return (
            TriageSuggestion(action="keep", reason="Card not found", sell_collection_id=None, estimated_price_eur=0, suggested_sell_price_eur=0),
            [],
            0,
        )

    card_name = new_card["name"]
    new_price = new_card["price_eur_foil"] if event_row["is_foil"] else new_card["price_eur"]
    new_score = await compute_keep_score(new_price or "", bool(event_row["is_foil"]))

    # Determine the event_id if available (for sibling detection)
    event_id = event_row.get("id")

    # 2. Other printings of the same card name in collection
    cursor = await db.execute(
        """SELECT col.id, c.set_code, c.set_name, col.quantity, col.foil_quantity,
               c.price_eur, c.price_eur_foil
        FROM collection col JOIN cards c ON c.id = col.card_id
        WHERE c.name = ? AND col.id != COALESCE(?, -1)""",
        (card_name, event_row["collection_id"]),
    )
    rows = await cursor.fetchall()

    # 3. Build existing printings list (one per foil/non-foil slot with qty>0)
    printings: list[ExistingPrinting] = []
    for r in rows:
        if r["quantity"] and r["quantity"] > 0:
            printings.append(ExistingPrinting(
                collection_id=r["id"],
                set_code=r["set_code"] or "",
                set_name=r["set_name"] or "",
                is_foil=False,
                quantity=r["quantity"],
                foil_quantity=0,
                price_eur=r["price_eur"] or "0",
                keep_score=await compute_keep_score(r["price_eur"] or "0", False),
            ))
        if r["foil_quantity"] and r["foil_quantity"] > 0:
            printings.append(ExistingPrinting(
                collection_id=r["id"],
                set_code=r["set_code"] or "",
                set_name=r["set_name"] or "",
                is_foil=True,
                quantity=0,
                foil_quantity=r["foil_quantity"],
                price_eur=r["price_eur_foil"] or r["price_eur"] or "0",
                keep_score=await compute_keep_score(r["price_eur_foil"] or r["price_eur"] or "0", True),
            ))

    # 4. Sibling-aware: count pending events for same card that arrived before this one (by id)
    sibling_qty = 0
    if event_id is not None:
        sibling_cursor = await db.execute("""
            SELECT COALESCE(SUM(ae.qty_delta), 0) as sibling_pending
            FROM acquisition_events ae
            JOIN cards c ON c.id = ae.card_id
            WHERE c.name = ?
              AND ae.triage_state = 'pending'
              AND ae.id != ?
              AND ae.id < ?
        """, (card_name, event_id, event_id))
        sibling_row = await sibling_cursor.fetchone()
        sibling_qty = sibling_row["sibling_pending"] if sibling_row else 0

    # 5. Deck usage check
    cursor = await db.execute(
        """SELECT COALESCE(SUM(dc.quantity), 0) FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE c.name = ?""",
        (card_name,),
    )
    in_decks = (await cursor.fetchone())[0]
    total_owned = sum(p.quantity + p.foil_quantity for p in printings) + event_row["qty_delta"] + sibling_qty
    sellable = total_owned - in_decks

    suggested_price = await _get_suggested_sell_price(db, card_name)

    # 6. Decision logic — sibling_qty makes later events in same sync see earlier ones as "existing"
    effective_existing = len(printings) + (1 if sibling_qty > 0 else 0)

    if sellable <= 0 or (not printings and sibling_qty == 0):
        return (
            TriageSuggestion(
                action="keep",
                reason="No surplus to sell" if sellable <= 0 else "No other printings owned",
                sell_collection_id=None,
                estimated_price_eur=float(new_price or 0),
                suggested_sell_price_eur=suggested_price,
            ),
            printings,
            in_decks,
        )

    all_scores = sorted([new_score] + [p.keep_score for p in printings], reverse=True)
    if printings and new_score >= all_scores[0]:
        # New is top → swap, sell old with lowest score
        worst = min(printings, key=lambda p: p.keep_score)
        return (
            TriageSuggestion(
                action="swap",
                reason=f"New {new_card['set_code']} (score {new_score:.2f}) > {worst.set_code} (score {worst.keep_score:.2f})",
                sell_collection_id=worst.collection_id,
                estimated_price_eur=float(worst.price_eur),
                suggested_sell_price_eur=suggested_price,
            ),
            printings,
            in_decks,
        )
    elif printings and new_score <= all_scores[-1]:
        return (
            TriageSuggestion(
                action="sold_new",
                reason=f"New {new_card['set_code']} (score {new_score:.2f}) is lowest of {len(all_scores)} copies",
                sell_collection_id=None,
                estimated_price_eur=float(new_price or 0),
                suggested_sell_price_eur=suggested_price,
            ),
            printings,
            in_decks,
        )
    elif sibling_qty > 0 and not printings:
        # No collection printings, but earlier sibling events count as "existing"
        return (
            TriageSuggestion(
                action="sold_new",
                reason=f"Earlier pending event(s) for {card_name} already cover a copy",
                sell_collection_id=None,
                estimated_price_eur=float(new_price or 0),
                suggested_sell_price_eur=suggested_price,
            ),
            printings,
            in_decks,
        )
    else:
        return (
            TriageSuggestion(
                action="keep",
                reason="New copy fits between existing printings — no clear swap candidate",
                sell_collection_id=None,
                estimated_price_eur=float(new_price or 0),
                suggested_sell_price_eur=suggested_price,
            ),
            printings,
            in_decks,
        )


async def get_suggestion(db, event_row) -> tuple[TriageSuggestion, list[ExistingPrinting], int]:
    """Return (suggestion, existing_printings, in_decks) for an acquisition event.

    Sibling-aware: if other pending events for the same card_name exist (earlier by id),
    they are treated as already-owned for the purpose of this suggestion.

    Gracefully falls back to DEFAULT_SUGGESTION on DB errors so a single schema drift
    does not kill the entire /pending route.
    """
    try:
        return await _get_suggestion_impl(db, event_row)
    except sqlite3.OperationalError as e:
        logger.error("get_suggestion failed for event %s: %s", event_row.get("id"), e)
        return (
            TriageSuggestion(**{**DEFAULT_SUGGESTION.__dict__, "reason": f"error: {type(e).__name__}"}),
            [],
            0,
        )
    except Exception as e:
        logger.exception("get_suggestion unexpected error for event %s", event_row.get("id"))
        return (
            TriageSuggestion(**{**DEFAULT_SUGGESTION.__dict__, "reason": f"error: {type(e).__name__}"}),
            [],
            0,
        )
