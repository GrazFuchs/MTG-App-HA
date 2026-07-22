"""Sprint 30: logging games from outside the UI + deck performance metrics."""
import pytest
from _helpers import insert_deck
from app.database import get_db
from app.services import ha_metrics
from app.services.game_log import DeckLookupError, log_game, resolve_deck
from pydantic import ValidationError


async def _add_game(db, deck_id: int, result: str = "win", played_at: str = "2026-07-01"):
    await db.execute(
        "INSERT INTO deck_games (deck_id, played_at, result) VALUES (?,?,?)",
        (deck_id, played_at, result),
    )
    await db.commit()


# --- deck resolution --------------------------------------------------------


@pytest.mark.anyio
async def test_resolve_deck_by_id():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa Superfriends")

    assert await resolve_deck(db, deck_id=deck_id) == (deck_id, "Atraxa Superfriends")
    assert await resolve_deck(db, deck=deck_id) == (deck_id, "Atraxa Superfriends")
    # A numeric string is an id too — voice assistants pass everything as text
    assert await resolve_deck(db, deck=str(deck_id)) == (deck_id, "Atraxa Superfriends")


@pytest.mark.anyio
async def test_resolve_deck_by_name_is_case_insensitive():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa Superfriends")

    assert await resolve_deck(db, deck="atraxa superfriends") == (deck_id, "Atraxa Superfriends")


@pytest.mark.anyio
async def test_resolve_deck_by_unique_substring():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa Superfriends")
    await insert_deck(db, "Krenko Goblins")

    assert await resolve_deck(db, deck="atraxa") == (deck_id, "Atraxa Superfriends")


@pytest.mark.anyio
async def test_exact_match_wins_over_substring():
    db = await get_db()
    exact = await insert_deck(db, "Krenko")
    await insert_deck(db, "Krenko Goblins")

    assert await resolve_deck(db, deck="Krenko") == (exact, "Krenko")


@pytest.mark.anyio
async def test_ambiguous_name_raises_with_candidates():
    db = await get_db()
    await insert_deck(db, "Krenko Goblins")
    await insert_deck(db, "Krenko Mob Boss")

    with pytest.raises(DeckLookupError) as exc:
        await resolve_deck(db, deck="krenko")

    assert "matches 2 decks" in str(exc.value)
    assert set(exc.value.candidates) == {"Krenko Goblins", "Krenko Mob Boss"}


@pytest.mark.anyio
async def test_unknown_name_lists_known_decks():
    db = await get_db()
    await insert_deck(db, "Atraxa")

    with pytest.raises(DeckLookupError) as exc:
        await resolve_deck(db, deck="Yuriko")

    assert exc.value.candidates == ["Atraxa"]


@pytest.mark.anyio
async def test_unknown_id_raises():
    db = await get_db()
    with pytest.raises(DeckLookupError):
        await resolve_deck(db, deck_id=999)


@pytest.mark.anyio
async def test_missing_deck_raises():
    db = await get_db()
    with pytest.raises(DeckLookupError):
        await resolve_deck(db)


# --- logging ----------------------------------------------------------------


@pytest.mark.anyio
async def test_log_game_by_name():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")

    result = await log_game(db, {"deck": "Atraxa", "result": "win", "turns": 9})

    assert result["status"] == "logged"
    assert result["deck_id"] == deck_id
    assert result["result"] == "win"

    cursor = await db.execute("SELECT * FROM deck_games WHERE id = ?", (result["game_id"],))
    row = await cursor.fetchone()
    assert row["deck_id"] == deck_id
    assert row["turns"] == 9


@pytest.mark.anyio
async def test_log_game_defaults_played_at_to_today():
    from datetime import date

    db = await get_db()
    await insert_deck(db, "Atraxa")

    result = await log_game(db, {"deck": "Atraxa", "result": "loss"})
    assert result["played_at"] == date.today().isoformat()


@pytest.mark.anyio
async def test_log_game_rejects_invalid_values():
    db = await get_db()
    await insert_deck(db, "Atraxa")

    with pytest.raises(ValidationError):
        await log_game(db, {"deck": "Atraxa", "result": "victory"})
    with pytest.raises(ValidationError):
        await log_game(db, {"deck": "Atraxa", "pod_size": 99})


@pytest.mark.anyio
async def test_log_game_checks_the_deck_before_inserting():
    db = await get_db()
    with pytest.raises(DeckLookupError):
        await log_game(db, {"deck": "Nonexistent", "result": "win"})

    cursor = await db.execute("SELECT COUNT(*) FROM deck_games")
    assert (await cursor.fetchone())[0] == 0


# --- deck performance metrics -----------------------------------------------


@pytest.mark.anyio
async def test_deck_performance_metrics_empty():
    db = await get_db()
    m = await ha_metrics.deck_performance_metrics(db)

    assert m.states["games_30d"] == 0
    assert m.states["winrate_30d"] == 0.0
    # None → not published at all, so the timestamp sensor stays unknown
    assert m.states["last_game_at"] is None
    assert m.states["last_game_result"] == "none"


@pytest.mark.anyio
async def test_deck_performance_window_and_winrate():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")
    for offset, result in ((1, "win"), (2, "win"), (3, "loss"), (60, "loss")):
        await db.execute(
            "INSERT INTO deck_games (deck_id, played_at, result)"
            " VALUES (?, date('now', ?), ?)",
            (deck_id, f"-{offset} days", result),
        )
    await db.commit()

    m = await ha_metrics.deck_performance_metrics(db)

    # The 60-day-old game falls outside the window
    assert m.states["games_30d"] == 3
    assert m.states["winrate_30d"] == pytest.approx(66.7)
    assert m.attributes["winrate_30d"]["wins"] == 2


@pytest.mark.anyio
async def test_last_game_is_an_iso_timestamp():
    """device_class timestamp cannot parse a bare date."""
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")
    await _add_game(db, deck_id, "draw", "2026-07-20")

    m = await ha_metrics.deck_performance_metrics(db)

    assert m.states["last_game_at"] == "2026-07-20T00:00:00+00:00"
    assert m.states["last_game_result"] == "draw"
    assert m.attributes["last_game_result"]["deck_name"] == "Atraxa"


@pytest.mark.anyio
async def test_deck_stats_marks_recently_played_decks_active():
    db = await get_db()
    active = await insert_deck(db, "Atraxa")
    stale = await insert_deck(db, "Old Deck")
    never = await insert_deck(db, "Never Played")

    await db.execute(
        "INSERT INTO deck_games (deck_id, played_at, result)"
        " VALUES (?, date('now','-5 days'), 'win')",
        (active,),
    )
    await db.execute(
        "INSERT INTO deck_games (deck_id, played_at, result)"
        " VALUES (?, date('now','-200 days'), 'win')",
        (stale,),
    )
    await db.commit()

    stats = {d["deck_id"]: d for d in await ha_metrics.deck_stats(db)}

    assert stats[active]["is_active"] is True
    assert stats[stale]["is_active"] is False
    assert stats[never]["is_active"] is False
    # Inactive decks are still reported so their sensors can be cleared
    assert len(stats) == 3


@pytest.mark.anyio
async def test_deck_stats_win_rate():
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")
    for result in ("win", "win", "win", "loss"):
        await db.execute(
            "INSERT INTO deck_games (deck_id, played_at, result)"
            " VALUES (?, date('now','-1 days'), ?)",
            (deck_id, result),
        )
    await db.commit()

    stats = (await ha_metrics.deck_stats(db))[0]

    assert stats["games"] == 4
    assert stats["wins"] == 3
    assert stats["losses"] == 1
    assert stats["win_rate"] == 75.0
