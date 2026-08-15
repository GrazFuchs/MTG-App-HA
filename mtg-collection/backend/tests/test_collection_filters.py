"""Collection page: card-type filter and multi-colour selection with modes."""
import pytest
from _helpers import add_collection, insert_card, names
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(db):
    """A small collection spanning the colour and type combinations."""
    cards = {
        "Mono Green Bear": (["G"], "Creature — Bear"),
        "Mono Blue Wizard": (["U"], "Creature — Wizard"),
        "Simic Merfolk": (["G", "U"], "Creature — Merfolk"),
        "Simic Ritual": (["G", "U"], "Sorcery"),
        "Golgari Charm": (["B", "G"], "Instant"),
        "Red Bolt": (["R"], "Instant"),
        "Colorless Rock": ([], "Artifact"),
        "Green Aura": (["G"], "Enchantment — Aura"),
        "Simic Land": (["G", "U"], "Land"),
        "Bear Walker": (["G"], "Legendary Planeswalker — Bear"),
    }
    for name, (identity, type_line) in cards.items():
        card_id = await insert_card(
            db, name, type_line=type_line, color_identity=identity
        )
        await add_collection(db, card_id, quantity=1)


# --------------------------------------------------------------------------
# Card type
# --------------------------------------------------------------------------

async def test_type_filter_single(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?card_type=Instant")
    assert names(resp.json()["items"]) == {"Golgari Charm", "Red Bolt"}


async def test_type_filter_multiple_is_or(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?card_type=Instant,Sorcery")
    assert names(resp.json()["items"]) == {
        "Golgari Charm", "Red Bolt", "Simic Ritual"
    }


async def test_type_filter_ignores_subtypes(client):
    """"Creature — Bear" must not answer a Planeswalker filter, and the
    Planeswalker whose *subtype* is Bear must not answer a creature one."""
    db = await get_db()
    await _seed(db)
    async with client:
        walkers = await client.get("/api/collection/?card_type=Planeswalker")
        creatures = await client.get("/api/collection/?card_type=Creature")
    assert names(walkers.json()["items"]) == {"Bear Walker"}
    assert "Bear Walker" not in names(creatures.json()["items"])


async def test_type_filter_matches_supertyped_lines(client):
    db = await get_db()
    card_id = await insert_card(
        db, "Legendary Bear", type_line="Legendary Creature — Bear",
        color_identity=["G"],
    )
    await add_collection(db, card_id, quantity=1)
    async with client:
        resp = await client.get("/api/collection/?card_type=Creature")
    assert names(resp.json()["items"]) == {"Legendary Bear"}


async def test_type_filter_matches_archidekt_comma_form(client):
    """The Archidekt parser writes "Basic, Land — Plains"."""
    db = await get_db()
    card_id = await insert_card(
        db, "Comma Enchantment", type_line="Legendary, Enchantment — Saga",
        color_identity=["W"],
    )
    await add_collection(db, card_id, quantity=1)
    async with client:
        resp = await client.get("/api/collection/?card_type=Enchantment")
    assert names(resp.json()["items"]) == {"Comma Enchantment"}


async def test_unknown_type_is_ignored_not_fatal(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?card_type=Wizard")
    assert resp.status_code == 200
    assert resp.json()["total"] == 10  # filter dropped, nothing narrowed


# --------------------------------------------------------------------------
# Colour modes
# --------------------------------------------------------------------------

async def test_color_mode_any(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?color=G,U&color_mode=any")
    assert names(resp.json()["items"]) == {
        "Mono Green Bear", "Mono Blue Wizard", "Simic Merfolk", "Simic Ritual",
        "Golgari Charm", "Green Aura", "Simic Land", "Bear Walker",
    }


async def test_color_mode_all(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?color=G,U&color_mode=all")
    assert names(resp.json()["items"]) == {
        "Simic Merfolk", "Simic Ritual", "Simic Land"
    }


async def test_color_mode_exact(client):
    """Exact excludes a card that merely contains the selection."""
    db = await get_db()
    await _seed(db)
    async with client:
        both = await client.get("/api/collection/?color=G,U&color_mode=exact")
        mono = await client.get("/api/collection/?color=G&color_mode=exact")
    assert names(both.json()["items"]) == {
        "Simic Merfolk", "Simic Ritual", "Simic Land"
    }
    assert names(mono.json()["items"]) == {
        "Mono Green Bear", "Green Aura", "Bear Walker"
    }


async def test_color_mode_exclude(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?color=G,U&color_mode=exclude")
    assert names(resp.json()["items"]) == {
        "Red Bolt", "Colorless Rock"
    }


async def test_color_mode_any_and_exclude_partition_the_collection(client):
    db = await get_db()
    await _seed(db)
    async with client:
        inc = await client.get("/api/collection/?color=G,U&color_mode=any")
        exc = await client.get("/api/collection/?color=G,U&color_mode=exclude")
    assert inc.json()["total"] + exc.json()["total"] == 10


async def test_colorless_token(client):
    db = await get_db()
    await _seed(db)
    async with client:
        only = await client.get("/api/collection/?color=C&color_mode=any")
        without = await client.get("/api/collection/?color=C&color_mode=exclude")
    assert names(only.json()["items"]) == {"Colorless Rock"}
    assert "Colorless Rock" not in names(without.json()["items"])
    assert without.json()["total"] == 9


async def test_unknown_color_mode_falls_back_to_any(client):
    db = await get_db()
    await _seed(db)
    async with client:
        bogus = await client.get("/api/collection/?color=R&color_mode=sideways")
    assert names(bogus.json()["items"]) == {"Red Bolt"}


async def test_color_and_type_combine(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get(
            "/api/collection/?color=G,U&color_mode=all&card_type=Sorcery,Land"
        )
    assert names(resp.json()["items"]) == {"Simic Ritual", "Simic Land"}


async def test_no_color_selection_filters_nothing(client):
    db = await get_db()
    await _seed(db)
    async with client:
        resp = await client.get("/api/collection/?color=&color_mode=exclude")
    assert resp.json()["total"] == 10
