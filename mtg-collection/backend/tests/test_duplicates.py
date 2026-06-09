"""Sprint 18: Duplicates basic-land exclusion + color filter behaviour."""
import pytest
from _helpers import add_collection, insert_card, names
from app.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


async def _seed():
    db = await get_db()
    # Basic lands that must NEVER appear in duplicates:
    plains = await insert_card(db, "Plains", type_line="Basic Land — Plains")
    snow = await insert_card(db, "Snow-Covered Island", type_line="Basic Snow Land — Island")
    # Forest with an EMPTY type_line (e.g. imported via Cardmarket, not enriched):
    forest = await insert_card(db, "Forest", type_line="")
    wastes = await insert_card(db, "Wastes", type_line="Basic Land")
    # Real duplicates:
    mono = await insert_card(db, "Mono White Card", type_line="Creature", color_identity=["W"])
    azorius = await insert_card(db, "Azorius Card", type_line="Creature", color_identity=["U", "W"])
    for cid in (plains, snow, forest, wastes, mono, azorius):
        await add_collection(db, cid, quantity=5)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _get(client, query=""):
    resp = await client.get(f"/api/collection/duplicates{query}")
    assert resp.status_code == 200, resp.text
    return names(resp.json()["items"])


async def test_basic_lands_excluded(client):
    await _seed()
    async with client:
        found = await _get(client)
    assert "Plains" not in found
    assert "Snow-Covered Island" not in found
    assert "Forest" not in found  # empty type_line still excluded by name
    assert "Wastes" not in found
    assert {"Mono White Card", "Azorius Card"} <= found


async def test_color_includes_white(client):
    await _seed()
    async with client:
        found = await _get(client, "?color=W")
    # "Includes white" → both the mono and the multicolor card.
    assert "Mono White Card" in found
    assert "Azorius Card" in found


async def test_monocolor_excludes_multicolor(client):
    await _seed()
    async with client:
        found = await _get(client, "?color=MONO")
    assert "Mono White Card" in found
    assert "Azorius Card" not in found


async def test_multicolor_filter(client):
    await _seed()
    async with client:
        found = await _get(client, "?color=M")
    assert "Azorius Card" in found
    assert "Mono White Card" not in found
