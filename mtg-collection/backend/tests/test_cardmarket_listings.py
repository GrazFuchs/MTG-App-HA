"""Sprint 21: Cardmarket Active Listings must show imported/manual listings,
without row multiplication when a card has multiple printings."""
import pytest
from _helpers import add_listing, insert_card
from app.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_listings_are_returned(client):
    db = await get_db()
    await insert_card(db, "Sol Ring", set_code="c21", set_name="Commander 2021")
    await add_listing(db, "Sol Ring", set_code="c21", set_name="Commander 2021", source="import")
    await add_listing(db, "Mana Vault", set_code="vma", set_name="Vintage Masters", source="manual")

    async with client:
        resp = await client.get("/api/cardmarket/listings")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert {i["card_name"] for i in body["items"]} == {"Sol Ring", "Mana Vault"}


async def test_no_row_multiplication_with_multiple_printings(client):
    db = await get_db()
    # Same card name exists as several printings...
    await insert_card(db, "Sol Ring", set_code="c21", set_name="Commander 2021")
    await insert_card(db, "Sol Ring", set_code="ltc", set_name="LotR Commander")
    await insert_card(db, "Sol Ring", set_code="cmm", set_name="Commander Masters")
    # ...but there is exactly ONE listing for it.
    await add_listing(db, "Sol Ring", set_code="c21", source="import")

    async with client:
        resp = await client.get("/api/cardmarket/listings")
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    # The listing is joined to a single card.
    assert body["items"][0]["card"] is not None


async def test_source_filter(client):
    db = await get_db()
    await add_listing(db, "A", source="import")
    await add_listing(db, "B", source="manual")

    async with client:
        resp = await client.get("/api/cardmarket/listings?source=manual")
    body = resp.json()
    assert {i["card_name"] for i in body["items"]} == {"B"}
