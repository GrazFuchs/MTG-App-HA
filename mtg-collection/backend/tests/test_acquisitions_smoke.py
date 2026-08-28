"""Smoke test: /api/acquisitions/pending and /api/acquisitions/stats must return 200 even with empty DB.

Sprint 08 adds the bulk-triage tests at the bottom.
"""
import pytest
from _helpers import add_acquisition_event, insert_card
from httpx import AsyncClient, ASGITransport

from app.database import get_db
from app.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_acquisitions_pending_returns_200_empty_db():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/acquisitions/pending?page=1&page_size=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_acquisitions_stats_returns_200_empty_db():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/acquisitions/stats")
    assert resp.status_code == 200
    assert "pending_count" in resp.json()


# ---------------------------------------------------------------------------
# Bulk triage (Sprint 08)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_bulk_dismiss_decides_every_card_in_one_call(client):
    """The shape this inbox actually has: 137 cards arrived on one day, 127 of
    them worth under 50 cents. One card at a time was never the wrong
    interface, it was the wrong unit."""
    db = await get_db()
    ids = []
    for i in range(5):
        card = await insert_card(db, f"Bulk Card {i}", price_eur="0.05")
        ids.append(await add_acquisition_event(db, card))

    async with client:
        resp = await client.post(
            "/api/acquisitions/bulk-decide",
            json={"event_ids": ids, "action": "dismiss"},
        )
        stats = await client.get("/api/acquisitions/stats")

    assert resp.status_code == 200
    assert resp.json() == {"decided": 5, "failed": [], "event_ids": ids}
    assert stats.json()["pending_count"] == 0


@pytest.mark.anyio
async def test_one_bad_card_does_not_take_the_batch_down(client):
    """136 successful decisions rolled back because one card had gone stale is
    the worse failure — the batch reports the casualty and carries on."""
    db = await get_db()
    good = await add_acquisition_event(db, await insert_card(db, "Fine"))

    async with client:
        resp = await client.post(
            "/api/acquisitions/bulk-decide",
            json={"event_ids": [good, 999999], "action": "keep"},
        )

    body = resp.json()
    assert body["decided"] == 1 and body["event_ids"] == [good]
    assert body["failed"][0]["event_id"] == 999999


@pytest.mark.anyio
async def test_bulk_selling_is_not_offered(client):
    """Selling needs a price, a condition and a listing per card. A bulk
    variant would either invent those or refuse half the batch."""
    async with client:
        resp = await client.post(
            "/api/acquisitions/bulk-decide",
            json={"event_ids": [1], "action": "sold_new"},
        )

    assert resp.status_code == 422


@pytest.mark.anyio
async def test_a_decision_can_be_undone(client):
    """`POST /undo` was implemented and had no caller at all — 964 decisions a
    month with no way back."""
    db = await get_db()
    event_id = await add_acquisition_event(db, await insert_card(db, "Second Thoughts"))

    async with client:
        await client.post(
            "/api/acquisitions/bulk-decide",
            json={"event_ids": [event_id], "action": "dismiss"},
        )
        undo = await client.post(f"/api/acquisitions/{event_id}/undo")
        stats = await client.get("/api/acquisitions/stats")

    assert undo.status_code == 200
    assert undo.json()["triage_state"] == "pending"
    assert stats.json()["pending_count"] == 1
