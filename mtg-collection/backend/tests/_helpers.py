"""Seeding helpers for backend tests."""
import json
from typing import Any

import aiosqlite

_counter = {"n": 0}


async def insert_card(
    db: aiosqlite.Connection,
    name: str,
    *,
    type_line: str = "",
    color_identity: list[str] | None = None,
    set_code: str = "tst",
    set_name: str = "Test Set",
    collector_number: str | None = None,
    price_eur: str = "1.00",
    price_eur_foil: str = "2.00",
    rarity: str = "common",
    oracle_id: str | None = None,
    cardmarket_id: int | None = None,
    oracle_text: str = "",
    cmc: float = 0,
    game_changer: int | None = None,
    mass_land_denial: int | None = None,
    extra_turn: int | None = None,
) -> int:
    """Insert a card row and return its id.

    Pass the same `oracle_id` to two rows to model two printings of one card,
    and `cardmarket_id` to give a printing its Cardmarket product.
    """
    _counter["n"] += 1
    n = _counter["n"]
    cursor = await db.execute(
        """INSERT INTO cards
        (scryfall_id, oracle_id, name, type_line, color_identity, set_code,
         set_name, collector_number, rarity, price_eur, price_eur_foil,
         cardmarket_id, oracle_text, cmc, game_changer, mass_land_denial,
         extra_turn)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            f"sf-{n}",
            oracle_id or f"or-{n}",
            name,
            type_line,
            json.dumps(color_identity or []),
            set_code,
            set_name,
            collector_number or str(n),
            rarity,
            price_eur,
            price_eur_foil,
            cardmarket_id,
            oracle_text,
            cmc,
            game_changer,
            mass_land_denial,
            extra_turn,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def add_collection(
    db: aiosqlite.Connection,
    card_id: int,
    *,
    quantity: int = 1,
    foil_quantity: int = 0,
    archidekt_tags: str = "",
    condition: str = "NM",
    language: str = "en",
) -> int:
    cursor = await db.execute(
        """INSERT INTO collection
        (card_id, quantity, foil_quantity, condition, language, archidekt_tags)
        VALUES (?,?,?,?,?,?)""",
        (card_id, quantity, foil_quantity, condition, language, archidekt_tags),
    )
    await db.commit()
    return cursor.lastrowid


async def add_wishlist(
    db: aiosqlite.Connection,
    card_id: int,
    *,
    set_code: str | None = None,
    is_foil: int = 0,
    status: str = "wanted",
    quantity: int = 1,
) -> int:
    cursor = await db.execute(
        """INSERT INTO wishlist (card_id, set_code, is_foil, status, quantity)
        VALUES (?,?,?,?,?)""",
        (card_id, set_code, is_foil, status, quantity),
    )
    await db.commit()
    return cursor.lastrowid


async def insert_deck(db: aiosqlite.Connection, name: str = "Test Deck") -> int:
    cursor = await db.execute("INSERT INTO decks (name) VALUES (?)", (name,))
    await db.commit()
    return cursor.lastrowid


async def add_listing(
    db: aiosqlite.Connection,
    card_name: str,
    *,
    set_name: str = "",
    set_code: str = "",
    quantity: int = 1,
    price: float = 1.0,
    is_foil: int = 0,
    source: str = "import",
    card_id: int | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO cardmarket_listings
        (card_name, set_name, set_code, quantity, price, condition, language,
         is_foil, card_id, source)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (card_name, set_name, set_code, quantity, price, "NM", "English",
         is_foil, card_id, source),
    )
    await db.commit()
    return cursor.lastrowid


async def add_acquisition_event(
    db: aiosqlite.Connection,
    card_id: int,
    *,
    qty_delta: int = 1,
    is_foil: int = 0,
    triage_state: str = "pending",
    condition: str = "NM",
    language: str = "en",
) -> int:
    cursor = await db.execute(
        """INSERT INTO acquisition_events
        (card_id, condition, language, is_foil, qty_delta, triage_state)
        VALUES (?,?,?,?,?,?)""",
        (card_id, condition, language, is_foil, qty_delta, triage_state),
    )
    await db.commit()
    return cursor.lastrowid


def names(items: list[dict[str, Any]]) -> set[str]:
    """Collect card names from a list of duplicate/collection/inbox items."""
    out = set()
    for it in items:
        out.add(it.get("card_name") or it.get("name") or (it.get("card") or {}).get("name"))
    return out
