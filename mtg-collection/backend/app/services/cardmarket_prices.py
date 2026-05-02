"""Cardmarket price data sync from public JSON feeds."""
import logging
from datetime import date
from typing import Any

import httpx

from ..database import get_db

logger = logging.getLogger(__name__)

CM_PRODUCTS_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_{n}.json"
CM_PRICES_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_{n}.json"


async def _fetch_json_pages(url_template: str) -> list[dict[str, Any]]:
    """Fetch all numbered JSON pages until 404."""
    all_items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        n = 1
        while True:
            url = url_template.format(n=n)
            try:
                resp = await client.get(url)
                if resp.status_code in (403, 404):
                    break
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    all_items.extend(data)
                elif isinstance(data, dict):
                    # Some formats wrap in a dict
                    items = data.get("products", data.get("priceGuides", data.get("data", [])))
                    if isinstance(items, list):
                        all_items.extend(items)
                    else:
                        all_items.append(data)
                logger.info("Fetched %s (%d items)", url, len(data) if isinstance(data, list) else 1)
                n += 1
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 404):
                    break
                logger.warning("HTTP error fetching %s: %s", url, e)
                break
            except Exception as e:
                logger.warning("Error fetching %s: %s", url, e)
                break
    return all_items


async def sync_cardmarket_prices() -> dict[str, Any]:
    """Download Cardmarket price data and store for owned cards only."""
    db = await get_db()
    today = date.today().isoformat()

    # Get all card names we own (from collection + cardmarket listings)
    cursor = await db.execute(
        """SELECT DISTINCT LOWER(c.name) FROM collection col
        JOIN cards c ON c.id = col.card_id
        UNION
        SELECT DISTINCT LOWER(card_name) FROM cardmarket_listings"""
    )
    owned_names = {row[0] for row in await cursor.fetchall()}
    if not owned_names:
        logger.info("No owned cards found, skipping price sync")
        return {"status": "skipped", "reason": "no owned cards", "products_matched": 0, "prices_stored": 0}

    logger.info("Found %d unique owned card names for price matching", len(owned_names))

    # Fetch product catalog
    products = await _fetch_json_pages(CM_PRODUCTS_URL)
    logger.info("Total product catalog entries: %d", len(products))

    # Build product ID -> product mapping for owned cards only
    matched_products: dict[int, dict[str, Any]] = {}
    for p in products:
        pid = p.get("idProduct")
        # Try different field names Cardmarket uses
        name = p.get("name", p.get("enName", ""))
        if not name:
            # Check localization array
            locs = p.get("localization", [])
            for loc in locs:
                if loc.get("idLanguage") == 1:  # English
                    name = loc.get("name", "")
                    break
            if not name and locs:
                name = locs[0].get("name", "")

        if pid and name and name.lower() in owned_names:
            expansion = p.get("expansionName", p.get("expansion", ""))
            matched_products[pid] = {"name": name, "expansion": expansion}

            # Upsert into cardmarket_products
            # Try to link to a card in our cards table
            card_id = None
            card_cursor = await db.execute(
                "SELECT id FROM cards WHERE LOWER(name) = ? LIMIT 1", (name.lower(),)
            )
            card_row = await card_cursor.fetchone()
            if card_row:
                card_id = card_row[0]

            await db.execute(
                """INSERT INTO cardmarket_products (cm_product_id, card_name, expansion_name, card_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cm_product_id) DO UPDATE SET
                    card_name=excluded.card_name,
                    expansion_name=excluded.expansion_name,
                    card_id=COALESCE(excluded.card_id, cardmarket_products.card_id),
                    updated_at=CURRENT_TIMESTAMP""",
                (pid, name, expansion, card_id),
            )

    await db.commit()
    logger.info("Matched %d products to owned cards", len(matched_products))

    if not matched_products:
        return {"status": "completed", "products_matched": 0, "prices_stored": 0}

    # Fetch price guide
    prices = await _fetch_json_pages(CM_PRICES_URL)
    logger.info("Total price guide entries: %d", len(prices))

    prices_stored = 0
    for pg in prices:
        pid = pg.get("idProduct")
        if pid not in matched_products:
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
        "products_matched": len(matched_products),
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


async def get_price_alerts() -> list[dict[str, Any]]:
    """Detect price spikes on owned cards that are unused in decks.

    A spike is defined as: current trend > avg30 * 1.3 (30% increase).
    Only flags cards with copies not used in any deck.

    Grouped per Cardmarket product (i.e. per edition/set), so a spike in a
    Revised dual land is NOT conflated with a cheaper reprint of the same name.
    Basic Lands (type_line LIKE '%Basic Land%') are excluded.
    """
    db = await get_db()

    # Get latest price entries with spike detection.
    # LEFT JOIN to cards gives us type_line (for Basic Land filter) and
    # set_code/set_name (for display) when the product was linked during sync.
    # Dual filter: type_line check (linked cards) + explicit name list (unlinked).
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
            CASE WHEN ph.avg30 > 0 THEN (ph.trend - ph.avg30) / ph.avg30 * 100 ELSE 0 END as spike_pct,
            c.set_code, c.set_name
        FROM cardmarket_products cp
        JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
        LEFT JOIN cards c ON c.id = cp.card_id
        WHERE ph.date = (SELECT MAX(date) FROM cardmarket_price_history)
        AND ph.avg30 > 0 AND ph.trend > ph.avg30 * 1.3
        AND (c.type_line IS NULL OR c.type_line NOT LIKE '%Basic Land%')
        AND LOWER(cp.card_name) NOT IN ({placeholders})
        ORDER BY spike_pct DESC""",
        BASIC_LAND_NAMES,
    )
    spiking = await cursor.fetchall()

    alerts = []
    for r in spiking:
        card_name = r["card_name"]
        card_id = r["card_id"]  # may be None if matching failed during sync

        # Count total owned copies — use exact card_id (per-edition) when available,
        # fall back to name-match across all editions.
        if card_id:
            owned_cursor = await db.execute(
                "SELECT COALESCE(SUM(col.quantity + col.foil_quantity), 0) FROM collection col WHERE col.card_id = ?",
                (card_id,),
            )
        else:
            owned_cursor = await db.execute(
                """SELECT COALESCE(SUM(col.quantity + col.foil_quantity), 0)
                FROM collection col JOIN cards c ON c.id = col.card_id
                WHERE LOWER(c.name) = LOWER(?)""",
                (card_name,),
            )
        owned_row = await owned_cursor.fetchone()
        total_owned = owned_row[0] if owned_row else 0

        # Count copies in decks — same precision logic.
        if card_id:
            deck_cursor = await db.execute(
                "SELECT COALESCE(SUM(dc.quantity), 0) FROM deck_cards dc WHERE dc.card_id = ?",
                (card_id,),
            )
        else:
            deck_cursor = await db.execute(
                """SELECT COALESCE(SUM(dc.quantity), 0)
                FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
                WHERE LOWER(c.name) = LOWER(?)""",
                (card_name,),
            )
        deck_row = await deck_cursor.fetchone()
        in_decks = deck_row[0] if deck_row else 0

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
            "suggestion": (
                f"Consider selling {unused} unused cop{'y' if unused == 1 else 'ies'} of {card_name} — "
                f"price spiked {spike_pct:.0f}% (€{r['avg30']:.2f} → €{r['trend']:.2f}), "
                f"not used in any deck"
                if in_decks == 0 else
                f"Consider selling {unused} extra cop{'y' if unused == 1 else 'ies'} of {card_name} — "
                f"price spiked {spike_pct:.0f}% (€{r['avg30']:.2f} → €{r['trend']:.2f}), "
                f"only {in_decks} needed in decks"
            ),
        })

    return alerts
