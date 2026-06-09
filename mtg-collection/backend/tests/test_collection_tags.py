"""Sprint 20: Collection tag filter + /tags endpoint."""
import pytest
from _helpers import add_collection, insert_card
from app.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


async def _seed():
    db = await get_db()
    a = await insert_card(db, "Cyclonic Rift")
    b = await insert_card(db, "Swords to Plowshares")
    c = await insert_card(db, "Llanowar Elves")
    await add_collection(db, a, archidekt_tags="Removal, Ramp")
    await add_collection(db, b, archidekt_tags="Removal")
    await add_collection(db, c, archidekt_tags="")


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _names(body):
    return {i["card"]["name"] for i in body["items"]}


async def test_tags_endpoint_returns_distinct_individual_tags(client):
    await _seed()
    async with client:
        resp = await client.get("/api/collection/tags")
    assert resp.status_code == 200, resp.text
    assert resp.json() == ["Ramp", "Removal"]


async def test_filter_by_unique_tag(client):
    await _seed()
    async with client:
        resp = await client.get("/api/collection/?collection_tag=Ramp")
    assert _names(resp.json()) == {"Cyclonic Rift"}


async def test_filter_by_shared_tag(client):
    await _seed()
    async with client:
        resp = await client.get("/api/collection/?collection_tag=Removal")
    assert _names(resp.json()) == {"Cyclonic Rift", "Swords to Plowshares"}
