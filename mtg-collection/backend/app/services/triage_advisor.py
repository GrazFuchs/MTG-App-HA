"""Triage advisor: computes keep-scores and suggestions for acquisition events."""
from __future__ import annotations

from ..models.schemas import ExistingPrinting, TriageSuggestion


async def compute_keep_score(price_eur: str, is_foil: bool) -> float:
    base = float(price_eur) if price_eur else 0.0
    return base * (1.5 if is_foil else 1.0)


async def get_suggestion(db, event_row) -> tuple[TriageSuggestion, list[ExistingPrinting], int]:
    """Return (suggestion, existing_printings, in_decks) for an acquisition event."""
    # 1. Fetch the card
    cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (event_row["card_id"],))
    new_card = await cursor.fetchone()
    if not new_card:
        return (
            TriageSuggestion(action="keep", reason="Card not found", sell_collection_id=None, estimated_price_eur=0),
            [],
            0,
        )

    new_price = new_card["price_eur_foil"] if event_row["is_foil"] else new_card["price_eur"]
    new_score = await compute_keep_score(new_price or "", bool(event_row["is_foil"]))

    # 2. Other printings of the same card name
    cursor = await db.execute(
        """SELECT col.id, c.set_code, c.set_name, col.quantity, col.foil_quantity,
               c.price_eur, c.price_eur_foil
        FROM collection col JOIN cards c ON c.id = col.card_id
        WHERE c.name = ? AND col.id != COALESCE(?, -1)""",
        (new_card["name"], event_row["collection_id"]),
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

    # 4. Deck usage check
    cursor = await db.execute(
        """SELECT COALESCE(SUM(dc.quantity), 0) FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE c.name = ?""",
        (new_card["name"],),
    )
    in_decks = (await cursor.fetchone())[0]
    total_owned = sum(p.quantity + p.foil_quantity for p in printings) + event_row["qty_delta"]
    sellable = total_owned - in_decks

    # 5. Decision logic
    if sellable <= 0 or not printings:
        return (
            TriageSuggestion(
                action="keep",
                reason="No surplus to sell" if sellable <= 0 else "No other printings owned",
                sell_collection_id=None,
                estimated_price_eur=float(new_price or 0),
            ),
            printings,
            in_decks,
        )

    all_scores = sorted([new_score] + [p.keep_score for p in printings], reverse=True)
    if new_score >= all_scores[0]:
        # New is top → swap, sell old with lowest score
        worst = min(printings, key=lambda p: p.keep_score)
        return (
            TriageSuggestion(
                action="swap",
                reason=f"New {new_card['set_code']} (score {new_score:.2f}) > {worst.set_code} (score {worst.keep_score:.2f})",
                sell_collection_id=worst.collection_id,
                estimated_price_eur=float(worst.price_eur),
            ),
            printings,
            in_decks,
        )
    elif new_score <= all_scores[-1]:
        return (
            TriageSuggestion(
                action="sold_new",
                reason=f"New {new_card['set_code']} (score {new_score:.2f}) is lowest of {len(all_scores)} copies",
                sell_collection_id=None,
                estimated_price_eur=float(new_price or 0),
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
            ),
            printings,
            in_decks,
        )
