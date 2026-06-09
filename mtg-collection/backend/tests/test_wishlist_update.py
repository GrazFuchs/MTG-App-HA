"""Sprint 20: Wishlist set/version + foil editable via PATCH (any status)."""
import pytest
from _helpers import add_wishlist, insert_card
from app.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_patch_set_version_repoints_to_printing(client):
    db = await get_db()
    p1 = await insert_card(db, "Sol Ring", set_code="c21", set_name="Commander 2021")
    p2 = await insert_card(db, "Sol Ring", set_code="ltc", set_name="LotR Commander")
    item = await add_wishlist(db, p1, set_code="c21")

    async with client:
        resp = await client.patch(
            f"/api/wishlist/{item}", json={"set_code": "ltc", "is_foil": True}
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["set_code"] == "ltc"
    assert body["is_foil"] is True
    assert body["set_name"] == "LotR Commander"  # repointed to the chosen printing
    assert body["card_id"] == p2


async def test_patch_set_version_on_acquired_item(client):
    """Set/version must remain editable after the item is acquired."""
    db = await get_db()
    p1 = await insert_card(db, "Mana Crypt", set_code="2xm", set_name="Double Masters")
    p2 = await insert_card(db, "Mana Crypt", set_code="mp2", set_name="Mystery")
    item = await add_wishlist(db, p1, set_code="2xm", status="acquired")

    async with client:
        resp = await client.patch(f"/api/wishlist/{item}", json={"set_code": "mp2"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["set_name"] == "Mystery"
    assert body["card_id"] == p2  # repoint works even after acquisition


async def test_patch_unknown_set_keeps_set_code_without_repoint(client):
    db = await get_db()
    p1 = await insert_card(db, "Lightning Greaves", set_code="cmm", set_name="Masters")
    item = await add_wishlist(db, p1, set_code="cmm")

    async with client:
        resp = await client.patch(f"/api/wishlist/{item}", json={"set_code": "zzz"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["set_code"] == "zzz"            # stored even with no local printing
    assert body["card_id"] == p1               # card_id unchanged (no match to repoint)
