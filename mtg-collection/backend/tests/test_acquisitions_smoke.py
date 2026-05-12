"""Smoke test: /api/acquisitions/pending and /api/acquisitions/stats must return 200 even with empty DB."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


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
