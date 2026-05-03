"""Card resolution helper: find or fetch+upsert a card by name/scryfall_id."""
import logging

import aiosqlite

from ..clients.scryfall import scryfall, parse_scryfall_card

logger = logging.getLogger(__name__)


async def resolve_card(
    db: aiosqlite.Connection,
    card_name: str | None = None,
    scryfall_id: str | None = None,
    set_code: str | None = None,
) -> dict | None:
    """Find or fetch+upsert a card.

    Strategy:
    1. If scryfall_id: lookup in cards table -> if not found, fetch from Scryfall + upsert
    2. If card_name + set_code: lookup by name+set -> fetch specific printing if missing
    3. If card_name only: lookup by name (any set) -> fetch default printing if missing

    Returns: card row dict (id, name, scryfall_id, set_code, ...) or None.
    """
    if not card_name and not scryfall_id:
        return None

    # 1. Lookup by scryfall_id
    if scryfall_id:
        cursor = await db.execute(
            "SELECT id, name, scryfall_id, set_code, set_name, image_uri FROM cards WHERE scryfall_id = ?",
            (scryfall_id,),
        )
        row = await cursor.fetchone()
        if row:
            return _row_to_dict(row)
        # Fetch from Scryfall and upsert
        card = await _fetch_and_upsert(db, scryfall_id=scryfall_id)
        return card

    # 2. Lookup by card_name + set_code
    if card_name and set_code:
        cursor = await db.execute(
            "SELECT id, name, scryfall_id, set_code, set_name, image_uri FROM cards WHERE LOWER(name) = LOWER(?) AND set_code = ?",
            (card_name.strip(), set_code),
        )
        row = await cursor.fetchone()
        if row:
            return _row_to_dict(row)
        # Fetch specific printing from Scryfall
        card = await _fetch_and_upsert(db, card_name=card_name, set_code=set_code)
        return card

    # 3. Lookup by card_name only (any set)
    if card_name:
        cursor = await db.execute(
            "SELECT id, name, scryfall_id, set_code, set_name, image_uri FROM cards WHERE LOWER(name) = LOWER(?)",
            (card_name.strip(),),
        )
        row = await cursor.fetchone()
        if row:
            return _row_to_dict(row)
        # Fetch default printing from Scryfall
        card = await _fetch_and_upsert(db, card_name=card_name)
        return card

    return None


async def _fetch_and_upsert(
    db: aiosqlite.Connection,
    scryfall_id: str | None = None,
    card_name: str | None = None,
    set_code: str | None = None,
) -> dict | None:
    """Fetch a card from Scryfall and upsert into DB."""
    try:
        if scryfall_id:
            data = await scryfall.get_card_by_id(scryfall_id)
        elif card_name and set_code:
            # Search for exact name in specific set
            data = await scryfall.search_cards(f'!"{card_name}" set:{set_code}')
            cards = data.get("data", [])
            if not cards:
                return None
            data = cards[0]
        elif card_name:
            data = await scryfall.get_card_by_name(card_name, exact=True)
        else:
            return None
    except Exception as e:
        logger.warning("Scryfall fetch failed: %s", e)
        return None

    parsed = parse_scryfall_card(data)

    # Upsert into cards table
    columns = list(parsed.keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    update_clause = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "scryfall_id")

    await db.execute(
        f"INSERT INTO cards ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT(scryfall_id) DO UPDATE SET {update_clause}",
        list(parsed.values()),
    )
    await db.commit()

    # Retrieve the inserted/updated row
    cursor = await db.execute(
        "SELECT id, name, scryfall_id, set_code, set_name, image_uri FROM cards WHERE scryfall_id = ?",
        (parsed["scryfall_id"],),
    )
    row = await cursor.fetchone()
    return _row_to_dict(row) if row else None


def _row_to_dict(row) -> dict:
    """Convert an aiosqlite Row to a plain dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "scryfall_id": row["scryfall_id"],
        "set_code": row["set_code"],
        "set_name": row["set_name"],
        "image_uri": row["image_uri"],
    }
