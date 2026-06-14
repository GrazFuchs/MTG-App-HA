"""Shared query functions used by both API routers and MCP tools."""
import json
import re
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
# Colour-identity filtering
#
# `cards.color_identity` SHOULD be stored as a JSON array (e.g. ["W","U"]), but
# historically it has also been seen as CSV ("W,U"), space-separated ("W U"),
# bare ("W") or concatenated ("WU") — the frontend (utils/colors.ts) already
# parses all of these defensively. The old SQL filters matched the literal JSON
# form `LIKE '%"W"%'`, so any non-JSON row silently dropped out → single-colour
# filters returned nothing (multicolour still matched via the comma-based test).
#
# These helpers match on the bare colour letter instead. `color_identity` only
# ever contains the letters WUBRG plus punctuation, so `LIKE '%R%'` is reliable
# regardless of delimiter format. Mono/multi/colourless are derived by counting
# how many distinct WUBRG letters are present, which is format-independent.
# ---------------------------------------------------------------------------
_WUBRG = ("W", "U", "B", "R", "G")


def parse_color_identity(raw: Any) -> list[str]:
    """Parse a stored color_identity value into a list of colour letters.

    Robust to every format the data has been seen in: JSON (["W","U"]), CSV
    ("W,U"), space-separated ("W U"), bare ("W") and concatenated ("WU").
    Mirrors the frontend's defensive parser (utils/colors.ts) so the backend
    never crashes on a non-JSON row. Returns [] for null/empty/garbage.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    s = str(raw).strip()
    if not s or s == "[]":
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            return [str(x) for x in parsed] if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    if "," in s or " " in s:
        return [p.strip() for p in re.split(r"[,\s]+", s) if p.strip()]
    if all(ch in "WUBRG" for ch in s):
        return list(s)
    return [s]


def _ci_col(alias: str) -> str:
    """The color_identity column, optionally table-qualified (alias='' = bare)."""
    return f"{alias}.color_identity" if alias else "color_identity"


def _ci_has(alias: str, letter: str) -> str:
    """Boolean: does the colour identity contain this WUBRG letter?"""
    return f"COALESCE({_ci_col(alias)}, '') LIKE '%{letter}%'"


def _ci_distinct_count(alias: str) -> str:
    """SQL expression: number of distinct WUBRG colours in the identity (0-5)."""
    return " + ".join(f"({_ci_has(alias, l)})" for l in _WUBRG)


def color_order_case_sql(alias: str = "c", land_rank: int | None = None) -> str:
    """CASE expression ranking rows by colour for ORDER BY (W,U,B,R,G, then
    multicolour, colourless, then everything else). Pass land_rank to rank land
    cards separately. Format-robust (see color_identity_condition)."""
    type_col = f"{alias}.type_line" if alias else "type_line"
    count = _ci_distinct_count(alias)
    lines = ["CASE"]
    if land_rank is not None:
        lines.append(f"    WHEN {type_col} LIKE '%Land%' THEN {land_rank}")
    lines.append(f"    WHEN ({count}) = 0 THEN 7")
    lines.append(f"    WHEN ({count}) >= 2 THEN 6")
    for i, letter in enumerate(_WUBRG, start=1):
        lines.append(f"    WHEN {_ci_has(alias, letter)} THEN {i}")
    lines.append("    ELSE 9")
    lines.append("END")
    return "\n".join(lines)


def color_identity_condition(
    token: str, alias: str = "c", mono_singles: bool = True
) -> str | None:
    """Return a SQL boolean for a colour-filter token, robust to storage format.

    Tokens (case-insensitive):
      W/U/B/R/G  single colour. With mono_singles=True this means *mono* of that
                 colour (matches the Inbox/Wishlist single-colour buckets); with
                 mono_singles=False it means *includes* that colour (mono OR
                 multicolour containing it — the Duplicates "includes" semantics).
      MONO       exactly one colour (any).
      M/MULTI    two or more colours.
      C/COLORLESS no colour.
      L/LAND     land cards (by type line).

    The colour letters are fixed constants (no user input), so inlining them in
    the SQL is safe. Returns None for an unrecognised token.
    """
    t = token.strip().upper()
    count = _ci_distinct_count(alias)
    if t in _WUBRG:
        if mono_singles:
            others = " AND ".join(f"NOT {_ci_has(alias, l)}" for l in _WUBRG if l != t)
            return f"({_ci_has(alias, t)} AND {others})"
        return f"({_ci_has(alias, t)})"
    if t == "MONO":
        return f"(({count}) = 1)"
    if t in ("M", "MULTI"):
        return f"(({count}) >= 2)"
    if t in ("C", "COLORLESS"):
        return f"(({count}) = 0)"
    if t in ("L", "LAND"):
        return f"{alias}.type_line LIKE '%Land%'"
    return None

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
