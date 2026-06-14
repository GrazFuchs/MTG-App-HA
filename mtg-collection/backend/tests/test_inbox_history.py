"""Sprint 24 (item 6): the Inbox booking archive records how each acquisition
was decided and how it was presented at confirmation time."""
import pytest
from _helpers import add_acquisition_event, add_collection, insert_card
from app.database import get_db
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_history_empty(client):
    async with client:
        resp = await client.get("/api/acquisitions/history")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_decide_records_history_snapshot(client):
    db = await get_db()
    cid = await insert_card(db, "History Card", type_line="Instant",
                            color_identity=["R"], price_eur="2.50")
    await add_collection(db, cid, quantity=1)
    ev_id = await add_acquisition_event(db, cid, qty_delta=1)

    async with client:
        decided = await client.post(
            f"/api/acquisitions/{ev_id}/decide",
            json={"action": "keep", "source": "cardmarket"},
        )
        assert decided.status_code == 200, decided.text

        hist = await client.get("/api/acquisitions/history")
    assert hist.status_code == 200
    body = hist.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["card_name"] == "History Card"
    assert item["triage_state"] == "keep"
    assert item["source"] == "cardmarket"
    assert item["snapshot"] is not None
    assert item["snapshot"]["decided_action"] == "keep"
    assert item["snapshot"]["card"]["name"] == "History Card"
    # Pending events are excluded from the archive.
    assert all(i["triage_state"] != "pending" for i in body["items"])
