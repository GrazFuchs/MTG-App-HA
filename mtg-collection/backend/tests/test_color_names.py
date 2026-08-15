"""Archidekt reports colours by name, Scryfall by letter — one canonical form.

Regression for the bug that made the Inbox file every card under "Colorless"
and report mono-green cards as multicolour. Archidekt's `colorIdentity` is
`["Green"]` where Scryfall's is `["G"]`, and whatever arrived was stored
verbatim: 6625 of 7540 cards in the real collection held names.

Two independent failures followed, and both are pinned here:

  * the frontend classifier only knew letters, so a name matched nothing and
    every card fell into the colourless bucket;
  * the SQL filter tested a bare `LIKE '%G%'`, which "Green" satisfies twice —
    'G' and, because LIKE is case-insensitive, the 'r'. A green card therefore
    counted as two colours and read as multicolour, while the mono-green
    filter ("has G and not R") matched nothing at all. "Blue" broke the same
    way through its 'u' and 'B'; White/Black/Red contain exactly one colour
    letter each and so worked by accident, which is why this went unnoticed.
"""
import json

import pytest
from _helpers import add_acquisition_event, add_collection
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services.queries import normalize_color_identity
from app.services.sync_service import upsert_card


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


_n = {"i": 5000}


async def _named_card(db, name, identity_raw, type_line="Creature — Bear"):
    """Insert a card whose colour columns hold RAW values, bypassing upsert.

    Models rows written before normalisation existed, which is what migration
    20 has to repair.
    """
    _n["i"] += 1
    i = _n["i"]
    cur = await db.execute(
        """INSERT INTO cards (scryfall_id, oracle_id, name, type_line,
            color_identity, colors, set_code, set_name, collector_number,
            rarity, price_eur, price_eur_foil)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"named-{i}", f"or-{i}", name, type_line, identity_raw, identity_raw,
         "tst", "Test Set", str(i), "rare", "10.73", "31.33"),
    )
    await db.commit()
    return cur.lastrowid


# --------------------------------------------------------------------------
# The normaliser itself
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (["Green"], ["G"]),                       # Archidekt
    (["G"], ["G"]),                           # Scryfall
    ('["Green"]', ["G"]),                     # as stored
    ('["Black","Red"]', ["B", "R"]),
    (["Blue"], ["U"]),                        # the name/letter mismatch
    (["White", "Blue"], ["W", "U"]),
    ("Green", ["G"]),
    ("Green,Blue", ["U", "G"]),               # canonical order is WUBRG, not input order
    ("WU", ["W", "U"]),                       # concatenated letters
    (["Red", "Red"], ["R"]),                  # deduplicated
    (["Green", "White"], ["W", "G"]),         # always in WUBRG order
    ([], []),
    ("[]", []),
    (None, []),
    ("", []),
    (42, []),                                 # garbage never raises
    (["Puce"], []),                           # unmappable token is dropped
])
def test_normalize_color_identity(raw, expected):
    assert normalize_color_identity(raw) == expected


def test_blue_and_green_are_not_multicolour():
    """The two names whose letters overlap another colour's."""
    assert normalize_color_identity(["Blue"]) == ["U"]
    assert normalize_color_identity(["Green"]) == ["G"]


# --------------------------------------------------------------------------
# The write path
# --------------------------------------------------------------------------

async def test_upsert_card_stores_letters_for_archidekt_names():
    db = await get_db()
    card_id = await upsert_card(db, {
        "scryfall_id": "upsert-green",
        "name": "Beorn the Fierce",
        "colors": ["Green"],
        "color_identity": ["Green"],
    })
    row = await (await db.execute(
        "SELECT colors, color_identity FROM cards WHERE id = ?", (card_id,)
    )).fetchone()
    assert json.loads(row["colors"]) == ["G"]
    assert json.loads(row["color_identity"]) == ["G"]


async def test_upsert_card_leaves_scryfall_letters_alone():
    db = await get_db()
    card_id = await upsert_card(db, {
        "scryfall_id": "upsert-letters",
        "name": "Lightning Bolt",
        "colors": ["R"],
        "color_identity": ["R"],
    })
    row = await (await db.execute(
        "SELECT color_identity FROM cards WHERE id = ?", (card_id,)
    )).fetchone()
    assert json.loads(row["color_identity"]) == ["R"]


# --------------------------------------------------------------------------
# The migration
# --------------------------------------------------------------------------

async def test_migration_20_rewrites_stored_names():
    db = await get_db()
    card_id = await _named_card(db, "Migrated Bear", '["Green"]')

    from app.database import _migration_20
    await _migration_20(db)
    await db.commit()

    row = await (await db.execute(
        "SELECT colors, color_identity FROM cards WHERE id = ?", (card_id,)
    )).fetchone()
    assert json.loads(row["color_identity"]) == ["G"]
    assert json.loads(row["colors"]) == ["G"]


async def test_migration_20_is_idempotent():
    db = await get_db()
    card_id = await _named_card(db, "Twice Migrated", '["Blue","Red"]')

    from app.database import _migration_20
    await _migration_20(db)
    await db.commit()
    first = await (await db.execute(
        "SELECT color_identity FROM cards WHERE id = ?", (card_id,)
    )).fetchone()
    await _migration_20(db)
    await db.commit()
    second = await (await db.execute(
        "SELECT color_identity FROM cards WHERE id = ?", (card_id,)
    )).fetchone()

    assert json.loads(first["color_identity"]) == ["U", "R"]
    assert first["color_identity"] == second["color_identity"]


# --------------------------------------------------------------------------
# What the user actually saw
# --------------------------------------------------------------------------

async def test_inbox_reports_green_card_as_mono_green(client):
    """The reported symptom: a mono-green card filed under Multicolor."""
    db = await get_db()
    beorn = await _named_card(db, "Beorn the Fierce", '["Green"]')
    await add_acquisition_event(db, beorn)
    from app.database import _migration_20
    await _migration_20(db)
    await db.commit()

    async with client:
        green = await client.get("/api/acquisitions/pending?color=G")
        multi = await client.get("/api/acquisitions/pending?color=Multi")

    assert {i["card"]["name"] for i in green.json()["items"]} == {"Beorn the Fierce"}
    assert "Beorn the Fierce" not in {i["card"]["name"] for i in multi.json()["items"]}


async def test_inbox_payload_exposes_letters_not_names(client):
    """The frontend buckets on the payload, so it must carry letters."""
    db = await get_db()
    card = await _named_card(db, "Payload Bear", '["Green"]')
    await add_acquisition_event(db, card)

    async with client:
        resp = await client.get("/api/acquisitions/pending")
    item = next(i for i in resp.json()["items"] if i["card"]["name"] == "Payload Bear")
    assert item["card"]["color_identity"] == ["G"]


async def test_inbox_payload_reports_the_real_card_id(client):
    """`SELECT ae.*, c.*` shadows `cards.id` with the event's."""
    db = await get_db()
    card = await _named_card(db, "Identified Bear", '["G"]')
    event_id = await add_acquisition_event(db, card)

    async with client:
        resp = await client.get("/api/acquisitions/pending")
    item = next(i for i in resp.json()["items"] if i["card"]["name"] == "Identified Bear")
    assert item["card"]["id"] == card
    assert item["id"] == event_id


async def test_colour_name_never_reads_as_a_letter_it_contains(client):
    """Even unmigrated, a name must not invent colours it does not have."""
    db = await get_db()
    green = await _named_card(db, "Unmigrated Green", '["Green"]')
    await add_collection(db, green, quantity=2)

    async with client:
        red = await client.get("/api/collection/?color=R")
    # "Green" contains an 'r'; it must not answer a red filter.
    assert "Unmigrated Green" not in {
        i["card"]["name"] for i in red.json()["items"]
    }
