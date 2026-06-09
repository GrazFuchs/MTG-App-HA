"""Sprint 22: Deck Performance Tracker — CRUD + aggregation."""
import pytest
from _helpers import insert_deck
from app.database import get_db
from app.main import app
from app.services.deck_performance import compute_performance_stats
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_compute_stats_empty():
    s = compute_performance_stats([])
    assert s["games"] == 0
    assert s["win_rate"] == 0.0
    assert s["last_result"] is None


def test_compute_stats_sample():
    games = [
        {"result": "win", "on_play": True, "mulligans": 0, "missed_land_drops": 0,
         "turns": 8, "played_at": "2026-06-09"},
        {"result": "loss", "on_play": False, "mulligans": 2, "missed_land_drops": 1,
         "turns": 6, "played_at": "2026-06-08"},
        {"result": "win", "on_play": True, "mulligans": 1, "missed_land_drops": 0,
         "turns": 10, "played_at": "2026-06-07"},
        {"result": "draw", "on_play": False, "mulligans": 1, "missed_land_drops": 2,
         "turns": 12, "played_at": "2026-06-06"},
    ]
    s = compute_performance_stats(games)
    assert s["games"] == 4
    assert (s["wins"], s["losses"], s["draws"]) == (2, 1, 1)
    assert s["win_rate"] == 50.0
    assert s["on_play_games"] == 2
    assert s["on_play_win_rate"] == 100.0
    assert s["avg_mulligans"] == 1.0
    assert s["avg_missed_land_drops"] == 0.75
    assert s["last_played_at"] == "2026-06-09"
    assert s["last_result"] == "win"


async def test_crud_and_performance(client):
    db = await get_db()
    deck_id = await insert_deck(db, "Mono-Red Aggro")

    async with client:
        # No games yet
        resp = await client.get(f"/api/decks/{deck_id}/performance")
        assert resp.status_code == 200
        assert resp.json()["games"] == 0

        # Add two games
        r1 = await client.post(f"/api/decks/{deck_id}/games", json={
            "result": "win", "on_play": True, "mulligans": 1, "missed_land_drops": 0,
            "turns": 7, "what_worked": "fast start", "played_at": "2026-06-09",
        })
        assert r1.status_code == 200, r1.text
        game1 = r1.json()
        assert game1["result"] == "win"
        assert game1["on_play"] is True

        await client.post(f"/api/decks/{deck_id}/games", json={
            "result": "loss", "missed_land_drops": 2, "played_at": "2026-06-08",
        })

        # List newest-first
        games = (await client.get(f"/api/decks/{deck_id}/games")).json()
        assert [g["result"] for g in games] == ["win", "loss"]

        # Performance reflects both
        perf = (await client.get(f"/api/decks/{deck_id}/performance")).json()
        assert perf["games"] == 2
        assert perf["wins"] == 1
        assert perf["win_rate"] == 50.0
        assert perf["avg_missed_land_drops"] == 1.0

        # Patch the first game -> loss
        rp = await client.patch(
            f"/api/decks/{deck_id}/games/{game1['id']}", json={"result": "loss"}
        )
        assert rp.status_code == 200
        assert rp.json()["result"] == "loss"
        perf = (await client.get(f"/api/decks/{deck_id}/performance")).json()
        assert perf["wins"] == 0

        # Delete the second game
        games = (await client.get(f"/api/decks/{deck_id}/games")).json()
        rd = await client.delete(f"/api/decks/{deck_id}/games/{games[0]['id']}")
        assert rd.status_code == 200
        perf = (await client.get(f"/api/decks/{deck_id}/performance")).json()
        assert perf["games"] == 1


async def test_unknown_deck_404(client):
    async with client:
        resp = await client.get("/api/decks/99999/performance")
    assert resp.status_code == 404
