"""Cardmarket price data sync from public JSON feeds.

Cardmarket prices are per *product*, and a product is one printing: the Alpha
"Terror" and the Tenth Edition "Terror" are two products with two price
histories that differ by four orders of magnitude. The only printing-exact
bridge from our collection to those products is `cards.cardmarket_id`, which
Scryfall supplies per printing. Matching on the card name instead collapses all
31 "Terror" products into one and reports the spike of a printing you do not
own against the copies of one you do — see `_migration_19`.
"""
import logging
from datetime import date
from typing import Any

import httpx

from ..database import get_db

logger = logging.getLogger(__name__)

# The `_1` is Cardmarket's game id (Magic), not a page number. Games 2, 3, ...
# are World of Warcraft, Yu-Gi-Oh! and friends — different products entirely.
CM_PRICES_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json"

# Within the Magic guide, products are split by category: 1 is "Magic Single",
# the rest are boosters, displays and other sealed product we never price.
MAGIC_SINGLE_CATEGORY = 1

# Scryfall lookups per POST /cards/collection are capped at 75 identifiers.
_SCRYFALL_CHUNK = 75

# `cardmarket_id = 0` marks a card Scryfall has no Cardmarket product for
# (tokens, some promos). Distinguishing that from NULL keeps the backfill from
# asking about the same hopeless cards on every run.
_NO_CARDMARKET_PRODUCT = 0


async def _fetch_price_guide() -> list[dict[str, Any]]:
    """Fetch the Magic price guide, restricted to single cards."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(CM_PRICES_URL)
        resp.raise_for_status()
        data = resp.json()

    entries = data.get("priceGuides", []) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        logger.warning("Unexpected price guide shape: %s", type(entries).__name__)
        return []

    singles = [e for e in entries if e.get("idCategory") == MAGIC_SINGLE_CATEGORY]
    logger.info(
        "Fetched price guide: %d entries, %d Magic singles", len(entries), len(singles)
    )
    return singles


async def backfill_cardmarket_ids(max_cards: int | None = None) -> dict[str, Any]:
    """Fill `cards.cardmarket_id` from Scryfall for cards that still lack it.

    Only touches rows where the column is NULL, so a completed backfill costs
    one cheap query. Cards Scryfall has no Cardmarket product for are marked
    with 0 rather than left NULL, so they are asked about once and not again.
    """
    from ..clients.scryfall import scryfall

    db = await get_db()
    cursor = await db.execute(
        """SELECT id, scryfall_id FROM cards
        WHERE cardmarket_id IS NULL AND COALESCE(scryfall_id, '') != ''
        ORDER BY id"""
        + (" LIMIT ?" if max_cards else ""),
        (max_cards,) if max_cards else (),
    )
    pending = await cursor.fetchall()
    if not pending:
        return {"status": "completed", "checked": 0, "linked": 0, "unavailable": 0}

    by_scryfall_id = {row[1]: row[0] for row in pending}
    identifiers = [{"id": sid} for sid in by_scryfall_id]
    logger.info("Backfilling Cardmarket ids for %d cards", len(identifiers))

    linked = 0
    unavailable = 0
    for i in range(0, len(identifiers), _SCRYFALL_CHUNK):
        chunk = identifiers[i:i + _SCRYFALL_CHUNK]
        try:
            cards, _not_found = await scryfall.get_cards_collection(chunk)
        except Exception:
            logger.exception("Scryfall lookup failed, stopping backfill early")
            break

        resolved: set[str] = set()
        for card in cards:
            scryfall_id = card.get("id")
            card_id = by_scryfall_id.get(scryfall_id)
            if card_id is None:
                continue
            resolved.add(scryfall_id)
            cm_id = card.get("cardmarket_id") or _NO_CARDMARKET_PRODUCT
            await db.execute(
                "UPDATE cards SET cardmarket_id = ? WHERE id = ?", (cm_id, card_id)
            )
            if cm_id:
                linked += 1
            else:
                unavailable += 1

        # Cards Scryfall could not resolve at all get the same "asked, nothing
        # there" marker — otherwise every run re-requests them forever.
        for identifier in chunk:
            scryfall_id = identifier["id"]
            if scryfall_id not in resolved:
                await db.execute(
                    "UPDATE cards SET cardmarket_id = ? WHERE id = ?",
                    (_NO_CARDMARKET_PRODUCT, by_scryfall_id[scryfall_id]),
                )
                unavailable += 1

        await db.commit()

    logger.info(
        "Cardmarket id backfill: %d linked, %d without a product", linked, unavailable
    )
    return {
        "status": "completed",
        "checked": len(identifiers),
        "linked": linked,
        "unavailable": unavailable,
    }


async def sync_cardmarket_prices() -> dict[str, Any]:
    """Download Cardmarket price data and store it for owned printings only.

    The set of products we care about comes from `cards.cardmarket_id` of the
    printings actually held, so no product catalog download is needed: name,
    set and the card link all come from our own `cards` row, which is both
    cheaper and printing-exact.
    """
    db = await get_db()
    today = date.today().isoformat()

    # Cards without a Cardmarket id yet cannot be priced, so top the link table
    # up first. After the initial run this is a single indexed lookup.
    backfill = await backfill_cardmarket_ids()

    # Rebuild the links from scratch each run. Clearing first is what makes a
    # printing sold out of the collection let go of its product, instead of
    # keeping a stale claim that later shows up as somebody else's price spike.
    await db.execute("UPDATE cardmarket_products SET card_id = NULL WHERE card_id IS NOT NULL")

    # `MIN(c.id)` picks a stable winner on the rare occasion that two printings
    # share one Cardmarket product.
    await db.execute(
        f"""INSERT INTO cardmarket_products (cm_product_id, card_name, expansion_name, card_id)
        SELECT c.cardmarket_id, MIN(c.name), COALESCE(MIN(c.set_name), ''), MIN(c.id)
        FROM cards c
        WHERE c.cardmarket_id > {_NO_CARDMARKET_PRODUCT}
        AND (EXISTS (SELECT 1 FROM collection col WHERE col.card_id = c.id)
             OR EXISTS (SELECT 1 FROM cardmarket_listings cl WHERE cl.card_id = c.id))
        GROUP BY c.cardmarket_id
        ON CONFLICT(cm_product_id) DO UPDATE SET
            card_name=excluded.card_name,
            expansion_name=excluded.expansion_name,
            card_id=excluded.card_id,
            updated_at=CURRENT_TIMESTAMP"""
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT cm_product_id FROM cardmarket_products WHERE card_id IS NOT NULL"
    )
    owned_products = {row[0] for row in await cursor.fetchall()}
    if not owned_products:
        logger.info("No owned cards with a Cardmarket product, skipping price sync")
        return {
            "status": "skipped",
            "reason": "no owned cards linked to Cardmarket",
            "backfill": backfill,
            "products_matched": 0,
            "prices_stored": 0,
        }

    logger.info("Pricing %d owned printings", len(owned_products))

    prices = await _fetch_price_guide()

    prices_stored = 0
    for pg in prices:
        pid = pg.get("idProduct")
        if pid not in owned_products:
            continue

        avg = pg.get("avg", pg.get("avgSellPrice", 0)) or 0
        low = pg.get("low", pg.get("lowPrice", 0)) or 0
        trend = pg.get("trend", pg.get("trendPrice", 0)) or 0
        avg1 = pg.get("avg1", pg.get("avg1Day", 0)) or 0
        avg7 = pg.get("avg7", pg.get("avg7Day", 0)) or 0
        avg30 = pg.get("avg30", pg.get("avg30Day", 0)) or 0

        await db.execute(
            """INSERT INTO cardmarket_price_history
            (cm_product_id, date, avg, low, trend, avg1, avg7, avg30)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cm_product_id, date) DO UPDATE SET
                avg=excluded.avg, low=excluded.low, trend=excluded.trend,
                avg1=excluded.avg1, avg7=excluded.avg7, avg30=excluded.avg30""",
            (pid, today, avg, low, trend, avg1, avg7, avg30),
        )
        prices_stored += 1

    await db.commit()
    logger.info("Stored %d price entries for today", prices_stored)

    return {
        "status": "completed",
        "backfill": backfill,
        "products_matched": len(owned_products),
        "prices_stored": prices_stored,
    }


async def get_price_history(cm_product_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Get price history for a product."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT date, avg, low, trend, avg1, avg7, avg30
        FROM cardmarket_price_history
        WHERE cm_product_id = ?
        ORDER BY date DESC LIMIT ?""",
        (cm_product_id, days),
    )
    rows = await cursor.fetchall()
    return [
        {"date": r[0], "avg": r[1], "low": r[2], "trend": r[3],
         "avg1": r[4], "avg7": r[5], "avg30": r[6]}
        for r in reversed(rows)  # Oldest first for charting
    ]


def _printing_label(card_name: str, set_name: str) -> str:
    """Card name qualified by its set, so an alert names one printing."""
    return f"{card_name} ({set_name})" if set_name else card_name


async def get_price_alerts() -> list[dict[str, Any]]:
    """Detect price spikes on owned printings that no deck needs.

    A spike is `trend > avg30 * 1.3` (30% up) on the latest priced day.

    Every number in an alert describes the *same printing*: the product only
    enters the list if `cardmarket_products.card_id` links it to a specific
    `cards` row, and the owned count is taken from that row alone. A spike in
    an Alpha original can therefore no longer be reported against the copies of
    a bulk reprint you actually hold — that mismatch is exactly what made this
    notification untrustworthy before.

    Deck usage is counted the other way round, across all printings sharing an
    oracle id, because any printing fills a deck slot. Counting it per printing
    would advertise a card as spare while a deck is playing another copy of it.
    The asymmetry is deliberate and errs towards staying quiet.

    Basic lands are excluded, by type line and by name (the type line of a snow
    basic reads "Basic Snow Land", which the type filter alone would miss).
    """
    db = await get_db()

    BASIC_LAND_NAMES = (
        'plains', 'island', 'swamp', 'mountain', 'forest', 'wastes',
        'snow-covered plains', 'snow-covered island', 'snow-covered swamp',
        'snow-covered mountain', 'snow-covered forest', 'snow-covered wastes',
    )
    placeholders = ",".join("?" * len(BASIC_LAND_NAMES))
    cursor = await db.execute(
        f"""SELECT
            cp.cm_product_id, cp.card_name, cp.expansion_name, cp.card_id,
            ph.trend, ph.avg30, ph.low, ph.avg, ph.date,
            CASE WHEN ph.avg30 > 0
                 THEN (ph.trend - ph.avg30) / ph.avg30 * 100 ELSE 0 END as spike_pct,
            c.set_code, c.set_name,
            COALESCE((
                SELECT SUM(col.quantity + col.foil_quantity)
                FROM collection col WHERE col.card_id = c.id
            ), 0) AS total_owned,
            COALESCE((
                SELECT SUM(dc.quantity)
                FROM deck_cards dc JOIN cards dcc ON dcc.id = dc.card_id
                WHERE CASE
                    WHEN COALESCE(c.oracle_id, '') != '' THEN dcc.oracle_id = c.oracle_id
                    ELSE LOWER(dcc.name) = LOWER(c.name)
                END
            ), 0) AS in_decks
        FROM cardmarket_products cp
        JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
        JOIN cards c ON c.id = cp.card_id
        WHERE ph.date = (SELECT MAX(date) FROM cardmarket_price_history)
        AND ph.avg30 > 0 AND ph.trend > ph.avg30 * 1.3
        AND c.type_line NOT LIKE '%Basic Land%'
        AND LOWER(cp.card_name) NOT IN ({placeholders})
        ORDER BY spike_pct DESC""",
        BASIC_LAND_NAMES,
    )
    spiking = await cursor.fetchall()

    alerts = []
    for r in spiking:
        card_name = r["card_name"]
        total_owned = r["total_owned"]
        in_decks = r["in_decks"]

        unused = total_owned - in_decks
        if unused <= 0:
            continue

        spike_pct = r["spike_pct"]
        expansion = r["set_name"] or r["expansion_name"] or ""
        alerts.append({
            "card_name": card_name,
            "expansion": r["expansion_name"],
            "set_name": expansion,
            "set_code": r["set_code"] or "",
            "cm_product_id": r["cm_product_id"],
            "trend": round(r["trend"], 2),
            "avg30": round(r["avg30"], 2),
            "spike_pct": round(spike_pct, 1),
            "total_owned": total_owned,
            "in_decks": in_decks,
            "unused_copies": unused,
            # The printing belongs in the text: "Terror" alone was ambiguous
            # across 31 Cardmarket products with wildly different prices.
            "suggestion": (
                f"Consider selling {unused} unused cop{'y' if unused == 1 else 'ies'} of "
                f"{_printing_label(card_name, expansion)} — "
                f"price spiked {spike_pct:.0f}% (€{r['avg30']:.2f} → €{r['trend']:.2f}), "
                f"not used in any deck"
                if in_decks == 0 else
                f"Consider selling {unused} extra cop{'y' if unused == 1 else 'ies'} of "
                f"{_printing_label(card_name, expansion)} — "
                f"price spiked {spike_pct:.0f}% (€{r['avg30']:.2f} → €{r['trend']:.2f}), "
                f"only {in_decks} needed in decks"
            ),
        })

    return alerts
