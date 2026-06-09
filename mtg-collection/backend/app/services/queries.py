"""Shared query functions used by both API routers and MCP tools."""
from typing import Any

import aiosqlite

# ---------------------------------------------------------------------------
# Basic-land exclusion
#
# Several views (Duplicates, Inbox) must hide basic lands. Filtering on
# `type_line NOT LIKE '%Basic Land%'` is unreliable because:
#   - Snow-Covered basics have type "Basic Snow Land — …" (no "Basic Land")
#   - Cards imported via Cardmarket CSV may have an EMPTY type_line and so slip
#     through the type-line filter entirely.
# A name-based exclusion is deterministic regardless of how the card was added.
# ---------------------------------------------------------------------------
_BASIC_LAND_ROOTS = ["Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"]
BASIC_LAND_NAMES: list[str] = _BASIC_LAND_ROOTS + [
    f"Snow-Covered {name}" for name in _BASIC_LAND_ROOTS
]


def basic_land_exclusion_sql(alias: str = "c") -> str:
    """Return a SQL boolean excluding basic lands by name.

    The names are fixed constants (no user input), so inlining them is safe.
    """
    names = ", ".join(f"'{n}'" for n in BASIC_LAND_NAMES)
    return f"{alias}.name NOT IN ({names})"

# ---------------------------------------------------------------------------
# Canonical definitions (used everywhere — keep these in sync with the UI labels)
#
#   "Total Cards"         = SUM(quantity + foil_quantity) across all collection entries
#                           → how many physical cards you own in total
#   "Unique Cards"        = COUNT(DISTINCT card_id) where quantity+foil_quantity > 0
#                           → how many distinct Scryfall cards you own (NM + LP of the
#                             same Scryfall card still counts as 1)
#   "Collection Entries"  = COUNT(*) FROM collection
#                           → number of rows in the collection table; can exceed
#                             Unique Cards when the same Scryfall card is stored in
#                             multiple conditions/languages as separate rows
# ---------------------------------------------------------------------------


async def get_total_collection_entries(db: aiosqlite.Connection) -> int:
    """Return the number of collection rows that have a matching card.

    This equals the row-count shown in the Collection page's pagination total.
    It may be HIGHER than get_unique_card_count() when the same Scryfall card
    appears as multiple entries (e.g. different languages or conditions).
    """
    cursor = await db.execute(
        "SELECT COUNT(*) FROM collection col JOIN cards c ON c.id = col.card_id"
    )
    return (await cursor.fetchone())[0]


async def get_unique_card_count(db: aiosqlite.Connection) -> int:
    """Return the number of distinct Scryfall cards owned.

    Two collection entries for the same Scryfall card_id (e.g. NM + LP copies
    stored separately) count as ONE unique card here.
    This is the number shown as "Unique Cards" on the Dashboard.
    """
    cursor = await db.execute(
        "SELECT COUNT(DISTINCT col.card_id) FROM collection col JOIN cards c ON c.id = col.card_id"
    )
    return (await cursor.fetchone())[0]


async def get_total_cards(db: aiosqlite.Connection) -> int:
    """Return the total physical card count (SUM of quantity + foil_quantity).

    This is the "Total Cards" shown on the Dashboard — it counts every physical
    copy, so owning 4x Lightning Bolt contributes 4 here.
    """
    cursor = await db.execute(
        "SELECT COALESCE(SUM(col.quantity + col.foil_quantity), 0) FROM collection col JOIN cards c ON c.id = col.card_id"
    )
    return (await cursor.fetchone())[0]


async def query_collection_stats(db: aiosqlite.Connection) -> dict[str, Any]:
    """Get collection statistics.

    Returns:
        total_cards:  SUM(quantity + foil_quantity)  — physical card count
        unique_cards: COUNT(DISTINCT card_id)         — distinct Scryfall cards
        See module-level canonical definitions for the distinction.
    """
    total_cards = await get_total_cards(db)
    unique_cards = await get_unique_card_count(db)

    cursor = await db.execute(
        """SELECT
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
        "total_cards": total_cards,
        "unique_cards": unique_cards,
        "total_value_eur": round(row[0], 2),
        "total_value_usd": round(row[1], 2),
        "total_decks": deck_count,
        "total_cardmarket_listings": cm[0],
        "cardmarket_total_value": round(cm[1], 2),
    }


async def query_all_decks(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """List all decks with card counts."""
    cursor = await db.execute(
        """SELECT d.id, d.archidekt_id, d.name, d.format, d.commander_name,
        d.featured_image, d.last_synced, COALESCE(SUM(dc.quantity), 0) as card_count,
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
        "card_count": sum(c["quantity"] for c in cards), "cards": cards,
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


async def query_spending_stats_30d(db: aiosqlite.Connection) -> dict[str, Any]:
    """Return acquisition spending totals for the last 30 days.

    Returns:
        count:                   number of acquired items in the window
        total_spent_eur:         sum of paid_price_eur for those items
        total_current_value_eur: current market value (Cardmarket trend or Scryfall price)
    """
    cursor = await db.execute(
        """
        SELECT
            COUNT(*) AS count,
            COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS total_spent,
            COALESCE(SUM(
                COALESCE(
                    (SELECT ph.trend FROM cardmarket_products cp
                     JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                     WHERE LOWER(cp.card_name) = LOWER(c.name)
                     ORDER BY ph.date DESC LIMIT 1),
                    CAST(NULLIF(c.price_eur, '') AS REAL),
                    0
                ) * w.quantity
            ), 0) AS total_current_value
        FROM wishlist w
        LEFT JOIN cards c ON c.id = w.card_id
        WHERE w.removed_at IS NULL
          AND w.status = 'acquired'
          AND w.acquired_at >= datetime('now', '-30 days')
        """
    )
    row = await cursor.fetchone()
    return {
        "count": int(row[0]),
        "total_spent_eur": round(float(row[1]), 2),
        "total_current_value_eur": round(float(row[2]), 2),
    }
