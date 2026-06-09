"""Sprint 19: Inbox /pending search/color/sort filters + colour backfill."""
import pytest
from _helpers import add_acquisition_event, insert_card
from app.database import get_db
from app.main import app
from app.routers import acquisitions
from httpx import ASGITransport, AsyncClient


async def _seed():
    db = await get_db()
    red = await insert_card(db, "Lightning Bolt", type_line="Instant",
                            color_identity=["R"], set_name="Alpha", set_code="lea")
    blue = await insert_card(db, "Counterspell", type_line="Instant",
                             color_identity=["U"], set_name="Zeta", set_code="zzz")
    azorius = await insert_card(db, "Azorius Charm", type_line="Instant",
                                color_identity=["U", "W"], set_name="Mid", set_code="mmm")
    artifact = await insert_card(db, "Sol Ring", type_line="Artifact",
                                 color_identity=[], set_name="Beta", set_code="leb")
    plains = await insert_card(db, "Plains", type_line="Basic Land — Plains")
    for cid in (red, blue, azorius, artifact, plains):
        await add_acquisition_event(db, cid)
    return {"red": red, "blue": blue, "azorius": azorius, "artifact": artifact}


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _names(items):
    return {i["card"]["name"] for i in items}


async def test_basic_lands_excluded(client):
    await _seed()
    async with client:
        resp = await client.get("/api/acquisitions/pending?page=1&page_size=50")
    assert resp.status_code == 200, resp.text
    found = _names(resp.json()["items"])
    assert "Plains" not in found
    assert {"Lightning Bolt", "Counterspell", "Azorius Charm", "Sol Ring"} <= found


async def test_search_by_name(client):
    await _seed()
    async with client:
        resp = await client.get("/api/acquisitions/pending?search=Bolt")
    assert _names(resp.json()["items"]) == {"Lightning Bolt"}


async def test_color_mono_filter(client):
    await _seed()
    async with client:
        resp = await client.get("/api/acquisitions/pending?color=R")
    assert _names(resp.json()["items"]) == {"Lightning Bolt"}


async def test_color_multi_filter(client):
    await _seed()
    async with client:
        resp = await client.get("/api/acquisitions/pending?color=Multi")
    assert _names(resp.json()["items"]) == {"Azorius Charm"}


async def test_color_colorless_filter(client):
    await _seed()
    async with client:
        resp = await client.get("/api/acquisitions/pending?color=Colorless")
    found = _names(resp.json()["items"])
    assert found == {"Sol Ring"}  # basics excluded, only the artifact remains


async def test_sort_by_set(client):
    await _seed()
    async with client:
        resp = await client.get("/api/acquisitions/pending?sort=set")
    sets = [i["card"]["set_name"] for i in resp.json()["items"]]
    assert sets == sorted(sets)
    assert sets[0] == "Alpha"


async def test_backfill_colors(client, monkeypatch):
    db = await get_db()
    # A card that arrived with empty colour identity but has a scryfall id.
    cid = await insert_card(db, "Goblin Guide", type_line="Creature", color_identity=[])
    await add_acquisition_event(db, cid)

    async def fake_get(scryfall_id):
        return {"id": scryfall_id, "name": "Goblin Guide", "color_identity": ["R"],
                "set": "zen", "set_name": "Zendikar"}

    monkeypatch.setattr(acquisitions.scryfall, "get_card_by_id", fake_get)

    async with client:
        resp = await client.post("/api/acquisitions/backfill-colors")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"] >= 1
    assert body["enriched"] >= 1

    cur = await db.execute("SELECT color_identity FROM cards WHERE id=?", (cid,))
    assert (await cur.fetchone())[0] == '["R"]'
