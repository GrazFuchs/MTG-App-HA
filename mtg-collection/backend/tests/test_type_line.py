"""Sprint 02: one canonical type-line form, whichever source wrote the card.

Archidekt hands the type line out as three lists and the parser used to
comma-join them: `Legendary, Creature — Pirate, Shark` where Scryfall writes
`Legendary Creature — Pirate Shark`. The card-type filter matches a substring of
the part before the em dash, so both forms answered it and the difference stayed
invisible — until something spells two type words in a row.
"""
import pytest
from _helpers import add_collection, insert_card, names
from httpx import ASGITransport, AsyncClient

from app.clients.archidekt import _type_line, parse_archidekt_card
from app.database import get_db
from app.main import app
from app.services.queries import normalize_type_line
from app.services.sync_service import upsert_card


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize(
    "stored,canonical",
    [
        ("Legendary, Creature — Pirate, Shark", "Legendary Creature — Pirate Shark"),
        ("Legendary, Enchantment", "Legendary Enchantment"),
        ("Basic, Land — Plains", "Basic Land — Plains"),
        ("Artifact, Creature — Golem", "Artifact Creature — Golem"),
        # Already canonical, from Scryfall — must come back untouched.
        ("Legendary Creature — Human Wizard", "Legendary Creature — Human Wizard"),
        ("Instant // Land", "Instant // Land"),
        ("Sorcery", "Sorcery"),
        # Leftovers of the old assembly: a types-only line kept its dangling dash.
        ("Legendary, Creature — ", "Legendary Creature"),
        ("  Creature  —  Bear ", "Creature — Bear"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalize_type_line(stored, canonical):
    assert normalize_type_line(stored) == canonical


@pytest.mark.parametrize(
    "oracle,expected",
    [
        (
            {"superTypes": ["Legendary"], "types": ["Creature"],
             "subTypes": ["Pirate", "Shark"]},
            "Legendary Creature — Pirate Shark",
        ),
        ({"superTypes": ["Basic"], "types": ["Land"], "subTypes": ["Plains"]},
         "Basic Land — Plains"),
        ({"types": ["Sorcery"], "subTypes": []}, "Sorcery"),
        ({"superTypes": [], "types": ["Artifact", "Creature"], "subTypes": ["Golem"]},
         "Artifact Creature — Golem"),
        # Archidekt sends these as null on a thin entry, not as [].
        ({"superTypes": None, "types": None, "subTypes": None}, ""),
        ({}, ""),
    ],
)
def test_archidekt_assembles_the_scryfall_form(oracle, expected):
    assert _type_line(oracle) == expected


def test_parse_archidekt_card_carries_the_canonical_form():
    parsed = parse_archidekt_card({
        "card": {
            "uid": "abc123",
            "oracleCard": {
                "name": "Ancient Copper Dragon",
                "superTypes": ["Legendary"],
                "types": ["Creature"],
                "subTypes": ["Dragon"],
            },
            "edition": {},
            "prices": {},
        },
        "quantity": 1,
    })
    assert parsed["card"]["type_line"] == "Legendary Creature — Dragon"


@pytest.mark.anyio
async def test_the_write_path_canonicalises_whatever_it_is_handed():
    """The same arrangement colours have: one write path, one stored form, so a
    payload from an older parser cannot reintroduce the comma spelling."""
    db = await get_db()
    card_id = await upsert_card(db, {
        "scryfall_id": "legacy-1",
        "name": "Old Payload",
        "type_line": "Basic, Land — Plains",
    })
    await db.commit()

    cursor = await db.execute("SELECT type_line FROM cards WHERE id = ?", (card_id,))
    assert (await cursor.fetchone())[0] == "Basic Land — Plains"


@pytest.mark.anyio
async def test_the_canonical_form_still_answers_the_card_type_filter(client):
    """Regression guard for the 0.34.0 behaviour: the filter matches only the
    head of the type line, and it has to keep doing so in the new spelling."""
    db = await get_db()
    for name, type_line in [
        ("Canonical Saga", "Legendary Enchantment — Saga"),
        ("Canonical Walker", "Legendary Planeswalker — Bear"),
        ("Canonical Artificer", "Creature — Human Artificer"),
    ]:
        card_id = await insert_card(db, name, type_line=type_line)
        await add_collection(db, card_id, quantity=1)

    async with client:
        enchantments = await client.get("/api/collection/?card_type=Enchantment")
        creatures = await client.get("/api/collection/?card_type=Creature")
        artifacts = await client.get("/api/collection/?card_type=Artifact")

    assert names(enchantments.json()["items"]) == {"Canonical Saga"}
    assert names(creatures.json()["items"]) == {"Canonical Artificer"}
    # The Artificer subtype must not answer an Artifact filter.
    assert artifacts.json()["total"] == 0


@pytest.mark.anyio
async def test_a_basic_land_is_now_excluded_by_type_line_too():
    """What the comma form actually broke.

    `type_line NOT LIKE '%Basic Land%'` never matched `Basic, Land — Plains`, so
    every filter phrased that way let basic lands through. In the price-alert
    query a second, name-based exclusion carried it; the MTGStocks near-ATH
    query has no second half.
    """
    db = await get_db()
    await upsert_card(db, {
        "scryfall_id": "plains-1",
        "name": "Plains",
        "type_line": "Basic, Land — Plains",
    })
    await db.commit()

    cursor = await db.execute(
        "SELECT COUNT(*) FROM cards WHERE type_line NOT LIKE '%Basic Land%'"
    )
    assert (await cursor.fetchone())[0] == 0, "the type-line exclusion misses the card"
