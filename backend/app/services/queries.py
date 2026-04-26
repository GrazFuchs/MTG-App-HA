"""Shared query functions used by both API routers and MCP tools."""
from typing import Any

import aiosqlite


async def query_collection_stats(db: aiosqlite.Connection) -> dict[str, Any]:
    """Get collection statistics."""
    cursor = await db.execute(
        """SELECT
            COALESCE(SUM(col.quantity + col.foil_quantity), 0),
            COUNT(DISTINCT col.card_id),
            COALESCE(SUM(
                CASE WHEN c.price_eur != '' THEN CAST(c.price_eur AS REAL) * col.quantity ELSE 0 END
                + CASE WHEN c.price_eur_foil != '' THEN CAST(c.price_eur_foil AS REAL) * col.foil_quantity ELSE 0 END
            ), 0),
            COALESCE(SUM(
                CASE WHEN c.price_usd != '' THEN CAST(c.price_usd AS REAL) * col.quantity ELSE 0 END
                + CASE WHEN c.price_usd_foil != '' THEN CAST(c.price_usd_foil AS REAL) * col.foil_quantity ELSE 0 END
            ), 0)
        FROM collection col JOIN cards c ON c.id = col.card_id"""
    )
    row = await cursor.fetchone()

    cursor2 = await db.execute("SELECT COUNT(*) FROM decks")
    deck_count = (await cursor2.fetchone())[0]

    cursor3 = await db.execute(
        "SELECT COUNT(*), COALESCE(SUM(price * quantity), 0) FROM cardmarket_listings"
    )
    cm = await cursor3.fetchone()

    return {
        "total_cards": row[0],
        "unique_cards": row[1],
        "total_value_eur": round(row[2], 2),
        "total_value_usd": round(row[3], 2),
        "total_decks": deck_count,
        "total_cardmarket_listings": cm[0],
        "cardmarket_total_value": round(cm[1], 2),
    }


async def query_all_decks(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """List all decks with card counts."""
    cursor = await db.execute(
        """SELECT d.id, d.archidekt_id, d.name, d.format, d.commander_name,
        d.featured_image, d.last_synced, COUNT(dc.id) as card_count,
        d.folder_name, d.bracket
        FROM decks d LEFT JOIN deck_cards dc ON dc.deck_id = d.id
        GROUP BY d.id ORDER BY d.name"""
    )
    rows = await cursor.fetchall()
    return [{
        "id": r[0], "archidekt_id": r[1], "name": r[2], "format": r[3],
        "commander_name": r[4] or "", "featured_image": r[5] or "",
        "last_synced": r[6], "card_count": r[7],
        "folder_name": r[8] or "", "bracket": r[9] or 0,
    } for r in rows]


async def query_deck_detail(db: aiosqlite.Connection, deck_id: int) -> dict[str, Any] | None:
    """Get deck detail with all cards. Returns None if not found."""
    cursor = await db.execute("SELECT * FROM decks WHERE id=?", (deck_id,))
    deck = await cursor.fetchone()
    if not deck:
        return None

    cursor = await db.execute(
        """SELECT c.name, c.mana_cost, c.type_line, c.cmc,
        dc.quantity, dc.category, dc.is_commander, c.price_eur, c.price_usd
        FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id=? ORDER BY dc.category, c.name""",
        (deck_id,),
    )
    cards = [{
        "name": r[0], "mana_cost": r[1], "type_line": r[2], "cmc": r[3],
        "quantity": r[4], "category": r[5], "is_commander": bool(r[6]),
        "price_eur": r[7], "price_usd": r[8],
    } for r in await cursor.fetchall()]

    return {
        "name": deck["name"], "format": deck["format"],
        "commander": deck["commander_name"],
        "bracket": deck["bracket"] if "bracket" in deck.keys() else 0,
        "card_count": len(cards), "cards": cards,
    }


async def record_value_snapshot(db: aiosqlite.Connection) -> None:
    """Record today's collection value snapshot (idempotent per day)."""
    from datetime import date
    today = date.today().isoformat()
    stats = await query_collection_stats(db)
    await db.execute(
        """INSERT INTO value_snapshots (date, total_cards, unique_cards, value_eur, value_usd)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_cards=excluded.total_cards,
            unique_cards=excluded.unique_cards,
            value_eur=excluded.value_eur,
            value_usd=excluded.value_usd""",
        (today, stats["total_cards"], stats["unique_cards"],
         stats["total_value_eur"], stats["total_value_usd"]),
    )
    await db.commit()
