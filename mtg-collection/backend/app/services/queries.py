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
# Colour-identity storage and filtering
#
# The canonical storage form is a JSON array of WUBRG letters: ["W","U"].
# Getting there took a while, because the two ingest paths disagree:
#
#   Scryfall  "color_identity": ["G"]        <- letters
#   Archidekt "colorIdentity":  ["Green"]    <- full English names
#
# Archidekt is the bulk source, so 6625 of 7540 cards were stored as names.
# Every consumer then broke in a different way. The frontend classifier only
# knew letters, so every card fell into the "Colorless" bucket. The SQL filter
# matched a bare `LIKE '%G%'`, which "Green" satisfies twice over — 'G' *and*
# the 'r' (LIKE is case-insensitive) — so a green card counted as two colours
# and was reported as multicolour, while the mono-green filter, which demands
# "has G and not R", matched nothing at all. "Blue" broke identically via its
# 'u' and 'B'; White/Black/Red happened to contain exactly one colour letter
# and so worked by luck, which is why this survived so long.
#
# The fix is one canonical form enforced at the only write path
# (sync_service.upsert_card) plus a migration that rewrites existing rows, so
# `normalize_color_identity` is the single place that knows about names.
# Readers stay tolerant: `parse_color_identity` still accepts every historical
# format, and the SQL now matches the quoted JSON token `'%"G"%'` rather than a
# bare letter, so a name that somehow slips through reads as colourless — quiet
# and wrong-by-omission instead of loud and wrong-by-invention.
# ---------------------------------------------------------------------------
_WUBRG = ("W", "U", "B", "R", "G")

#: Every spelling of a colour we have seen in an ingest payload → its letter.
COLOR_NAME_TO_LETTER: dict[str, str] = {
    "W": "W", "WHITE": "W",
    "U": "U", "BLUE": "U",
    "B": "B", "BLACK": "B",
    "R": "R", "RED": "R",
    "G": "G", "GREEN": "G",
}


def parse_color_identity(raw: Any) -> list[str]:
    """Parse a stored color_identity value into canonical WUBRG letters.

    Robust to every format the data has been seen in: JSON (["W","U"]), CSV
    ("W,U"), space-separated ("W U"), bare ("W"), concatenated ("WU") and
    Archidekt's full colour names (["Green"]). Mirrors the frontend's
    defensive parser (utils/colors.ts). Returns [] for null/empty/garbage.
    """
    return normalize_color_identity(raw)


def _split_color_tokens(raw: Any) -> list[str]:
    """Split a stored colour value into raw tokens, without interpreting them."""
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


def normalize_color_identity(raw: Any) -> list[str]:
    """Canonicalise any stored/ingested colour value to WUBRG letters.

    Deduplicates and returns the letters in WUBRG order, so two cards with the
    same identity always compare and sort the same regardless of the order the
    source listed them in. Unrecognised tokens are dropped rather than passed
    through — a token we cannot map is not a colour we can filter on, and
    keeping it is what produced the "Green" = G+R misreading in the first place.
    """
    letters = {
        COLOR_NAME_TO_LETTER[t]
        for t in (str(tok).strip().upper() for tok in _split_color_tokens(raw))
        if t in COLOR_NAME_TO_LETTER
    }
    return [letter for letter in _WUBRG if letter in letters]


def _ci_col(alias: str) -> str:
    """The color_identity column, optionally table-qualified (alias='' = bare)."""
    return f"{alias}.color_identity" if alias else "color_identity"


def _ci_haystack(alias: str) -> str:
    """SQL expression reducing any stored colour value to `,TOKEN,TOKEN,`.

    Strips the JSON punctuation and fences the result in commas, so a token can
    be tested for as a whole. `["U","W"]`, `U,W` and `U W` all collapse to
    `,U,W,`; a bare `R` becomes `,R,`; an empty identity becomes `,,`.
    """
    stripped = f"COALESCE({_ci_col(alias)}, '')"
    for char in ("[", "]", '"', "'", " "):
        literal = char.replace("'", "''")  # an apostrophe doubles inside a SQL string
        stripped = f"REPLACE({stripped}, '{literal}', '')"
    return f"(',' || {stripped} || ',')"


def _ci_has(alias: str, letter: str) -> str:
    """Boolean: does the colour identity contain this WUBRG letter?

    Tests for a whole comma-delimited token, which is what keeps a colour
    *name* from being read as the letters it happens to contain: `,Green,`
    matches neither `,G,` nor `,R,`. Matching a bare `LIKE '%G%'` — as this did
    until 0.34.0 — is what made every green card read as multicolour.
    """
    return f"({_ci_haystack(alias)} LIKE '%,{letter},%')"


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
# Multi-colour filtering (Collection page)
#
# A single token answers "is it this colour?". Picking several colours raises a
# question a single token cannot: does the selection mean *any of these*, *all
# of these*, *exactly these* or *none of these*? Rather than guess, the caller
# names the mode. "exclude" is what makes the filter subtractive — "show me the
# collection without red and blue" — which is otherwise impossible to express.
# ---------------------------------------------------------------------------
COLOR_MODES = ("any", "all", "exact", "exclude")


def color_multi_condition(
    tokens: list[str], mode: str = "any", alias: str = "c"
) -> str | None:
    """Return a SQL boolean for a multi-colour selection.

    Tokens are WUBRG letters plus C/COLORLESS. Modes:
      any      identity contains at least one of the selected colours
      all      identity contains every selected colour (may contain others)
      exact    identity is precisely the selected set, nothing more
      exclude  identity contains none of the selected colours

    Returns None when nothing selectable was passed, so the caller can leave
    the filter out entirely rather than emit a tautology.
    """
    upper = [str(t).strip().upper() for t in tokens if str(t).strip()]
    letters = [t for t in upper if t in _WUBRG]
    wants_colorless = any(t in ("C", "COLORLESS") for t in upper)
    if not letters and not wants_colorless:
        return None

    count = _ci_distinct_count(alias)
    colorless = f"(({count}) = 0)"

    if mode == "exclude":
        parts = [f"NOT {_ci_has(alias, letter)}" for letter in letters]
        if wants_colorless:
            # "without colourless" = it must have at least one colour.
            parts.append(f"(({count}) > 0)")
        return "(" + " AND ".join(parts) + ")"

    if mode == "exact":
        if not letters:
            return colorless
        included = " AND ".join(_ci_has(alias, letter) for letter in letters)
        excluded = " AND ".join(
            f"NOT {_ci_has(alias, letter)}" for letter in _WUBRG if letter not in letters
        )
        exact = f"({included} AND {excluded})" if excluded else f"({included})"
        # Colourless alongside colours reads as "either", since no single card
        # can be both.
        return f"({exact} OR {colorless})" if wants_colorless else exact

    if mode == "all":
        if not letters:
            return colorless
        return "(" + " AND ".join(_ci_has(alias, letter) for letter in letters) + ")"

    parts = [_ci_has(alias, letter) for letter in letters]
    if wants_colorless:
        parts.append(colorless)
    return "(" + " OR ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Card-type filtering
#
# Only the part of the type line BEFORE the em dash names card types; what
# follows are subtypes. The distinction matters: "Creature — Human Artificer"
# would otherwise match an Artifact filter, and "Land — Urza's Mine" is not an
# instant just because a subtype spells one. Both ingest paths agree on the
# em dash — Scryfall writes "Legendary Creature — Human Wizard", the Archidekt
# parser assembles "Legendary, Creature — Human, Artificer" — so splitting on
# it is safe for either.
# ---------------------------------------------------------------------------
CARD_TYPES: tuple[str, ...] = (
    "Artifact", "Battle", "Creature", "Enchantment", "Instant",
    "Kindred", "Land", "Planeswalker", "Sorcery",
)

#: Types renamed by Wizards; both spellings live in the data.
_TYPE_ALIASES = {"KINDRED": ("Kindred", "Tribal"), "TRIBAL": ("Kindred", "Tribal")}


def type_line_head_sql(alias: str = "c") -> str:
    """SQL expression yielding the supertype/type part of the type line."""
    col = f"COALESCE({alias}.type_line, '')" if alias else "COALESCE(type_line, '')"
    return (
        f"CASE WHEN INSTR({col}, '—') > 0 "
        f"THEN SUBSTR({col}, 1, INSTR({col}, '—') - 1) ELSE {col} END"
    )


def card_type_condition(tokens: list[str], alias: str = "c") -> str | None:
    """Return a SQL boolean matching any of the given card types.

    Several types OR together — picking Instant and Sorcery means "either",
    which is what a type filter is asked for in practice. The type names are a
    fixed allowlist (no user input reaches the SQL), so inlining them is safe.
    """
    head = type_line_head_sql(alias)
    parts: list[str] = []
    for token in tokens:
        key = str(token).strip().upper()
        if key in _TYPE_ALIASES:
            spellings = _TYPE_ALIASES[key]
        else:
            match = next((t for t in CARD_TYPES if t.upper() == key), None)
            if match is None:
                continue
            spellings = (match,)
        parts.extend(f"{head} LIKE '%{s}%'" for s in spellings)
    if not parts:
        return None
    return "(" + " OR ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Duplicates
#
# One row per (card_id, set_code, is_foil) with the surplus columns computed.
# `{where}` is substituted per caller and appears in BOTH union legs, so the
# bound parameters have to be passed twice.  Used by the Duplicates API and by
# the HA surplus sensors, which must agree on what "surplus" means.
# ---------------------------------------------------------------------------
DUPLICATES_CTE = """
    WITH deck_usage AS (
        SELECT c2.name, SUM(dc.quantity) as in_decks
        FROM deck_cards dc JOIN cards c2 ON c2.id = dc.card_id
        GROUP BY c2.name
    ),
    global_owned AS (
        SELECT c3.name, SUM(col2.quantity + col2.foil_quantity) as total_global
        FROM collection col2 JOIN cards c3 ON c3.id = col2.card_id
        GROUP BY c3.name
    ),
    printing_rows AS (
        SELECT c.id as card_id, c.name, c.set_code, c.set_name, c.rarity,
               c.image_uri, c.price_eur, c.price_eur_foil, c.color_identity,
               c.type_line, c.collector_number,
               0 as is_foil,
               SUM(col.quantity) as total_copies,
               COALESCE(du.in_decks, 0) as in_decks,
               COALESCE(go.total_global, 0) as total_global
        FROM collection col
        JOIN cards c ON c.id = col.card_id
        LEFT JOIN deck_usage du ON du.name = c.name
        LEFT JOIN global_owned go ON go.name = c.name
        WHERE {where}
        GROUP BY c.id, c.set_code
        HAVING SUM(col.quantity) > 0

        UNION ALL

        SELECT c.id as card_id, c.name, c.set_code, c.set_name, c.rarity,
               c.image_uri, c.price_eur, c.price_eur_foil, c.color_identity,
               c.type_line, c.collector_number,
               1 as is_foil,
               SUM(col.foil_quantity) as total_copies,
               COALESCE(du.in_decks, 0) as in_decks,
               COALESCE(go.total_global, 0) as total_global
        FROM collection col
        JOIN cards c ON c.id = col.card_id
        LEFT JOIN deck_usage du ON du.name = c.name
        LEFT JOIN global_owned go ON go.name = c.name
        WHERE {where}
        GROUP BY c.id, c.set_code
        HAVING SUM(col.foil_quantity) > 0
    ),
    with_extras AS (
        SELECT pr.*,
               MAX(pr.total_global - pr.in_decks, 0) as extras_global,
               pr.total_copies as extras,
               COALESCE((
                   SELECT SUM(l.quantity) FROM cardmarket_listings l
                   WHERE LOWER(l.card_name) = LOWER(pr.name)
               ), 0) as listed_quantity
        FROM printing_rows pr
        WHERE pr.total_global > pr.in_decks AND pr.total_global > 1
    )
"""

# Surplus copies left after existing Cardmarket listings, and their value.
DUPLICATES_FINAL_CTE = """
    final AS (
        SELECT *,
            MAX(extras - listed_quantity, 0) as extras_after_listings,
            CAST(COALESCE(NULLIF(
                CASE WHEN is_foil THEN price_eur_foil ELSE price_eur END, ''), '0') AS REAL)
                * MAX(extras - listed_quantity, 0) as extra_value
        FROM with_extras
    )
"""

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
                     WHERE cp.card_id = c.id
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
