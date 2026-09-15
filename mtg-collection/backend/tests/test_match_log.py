"""Sprint 15: 1v1 defaults that follow the deck, and best-of-three as a match.

Two decisions shape every test here.

**Defaults follow the deck.** A pod size of four is right for Commander and
wrong for every 1v1 format. Correcting it by hand on every Standard game is how
a log stops being kept, so the format answers when nobody says otherwise.

**A match costs no extra typing.** Three bookings in a row against the same
opponent are a match; the grouping comes from the clock, not from a field. The
90-minute window is a judgement and will occasionally group two separate games
wrongly — that is the deliberate error, because a wrong grouping is one click
to fix and an extra mandatory field is a logging path that goes unused
(the fetchlog measurement: 8 walks through a one-tap tag, 0 meals through a
form).
"""
import pytest
from _helpers import insert_deck

from app.database import get_db
from app.services import game_log
from app.services.deck_performance import compute_performance_stats


async def _log(deck_id: int, result: str, **kw) -> dict:
    db = await get_db()
    payload = {"deck_id": deck_id, "result": result}
    payload.update(kw)
    return await game_log.log_game(db, payload)


async def _games(deck_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM deck_games WHERE deck_id = ? ORDER BY id", (deck_id,)
    )
    return [dict(r) for r in await cursor.fetchall()]


# --- Part A: the default follows the deck --------------------------------

@pytest.mark.anyio
async def test_a_standard_game_seats_two_and_a_commander_game_four():
    """The booking that carries no pod size is the common one — the MQTT
    command, a voice line, a script. It used to land on 4 every time."""
    db = await get_db()
    standard = await insert_deck(db, "Sligh", deck_format="Standard")
    commander = await insert_deck(db, "Atraxa", deck_format="Commander")

    await _log(standard, "win")
    await _log(commander, "loss")

    assert (await _games(standard))[0]["pod_size"] == 2
    assert (await _games(commander))[0]["pod_size"] == 4


@pytest.mark.anyio
async def test_a_pod_size_given_by_hand_always_wins():
    """Three-player Standard is unusual, not impossible. The default is a
    default, not a rule."""
    db = await get_db()
    deck_id = await insert_deck(db, "Odd night", deck_format="Standard")
    await _log(deck_id, "win", pod_size=3)
    assert (await _games(deck_id))[0]["pod_size"] == 3


@pytest.mark.anyio
async def test_picking_a_deck_in_the_ha_form_moves_the_pod_size():
    """The form is the path that has a button, so it is the one that matters."""
    from app.services import ha_form

    db = await get_db()
    await insert_deck(db, "Mono Red", deck_format="Standard")
    await insert_deck(db, "Atraxa Superfriends", deck_format="Commander")
    labels, _ = await ha_form.deck_options(db)

    standard_label = next(lbl for lbl in labels if "Mono Red" in lbl)
    commander_label = next(lbl for lbl in labels if "Atraxa" in lbl)

    await ha_form.set_field(db, "deck", standard_label)
    assert (await ha_form.load_state(db))["pod_size"] == "2"

    await ha_form.set_field(db, "deck", commander_label)
    assert (await ha_form.load_state(db))["pod_size"] == "4"

    # A value set by hand afterwards stands until the next deck is picked —
    # otherwise the field could not be used at all.
    await ha_form.set_field(db, "pod_size", "3")
    assert (await ha_form.load_state(db))["pod_size"] == "3"


# --- Part B: the match ----------------------------------------------------

@pytest.mark.anyio
async def test_three_bookings_against_the_same_opponent_are_one_match():
    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")

    first = await _log(deck_id, "win", opponents="The Rock")
    # The first game is not a match yet — nothing to group it with.
    assert first["match_id"] is None

    second = await _log(deck_id, "loss", opponents="the rock")  # casing differs
    third = await _log(deck_id, "win", opponents="  The Rock  ")  # spacing differs

    assert second["match_id"] is not None
    assert third["match_id"] == second["match_id"]
    assert second["game_in_match"] == 2
    assert third["game_in_match"] == 3
    assert third["match_score"] == "2-1"

    # The second game created the match and adopted the first.
    games = await _games(deck_id)
    assert [g["game_in_match"] for g in games] == [1, 2, 3]
    assert len({g["match_id"] for g in games}) == 1


@pytest.mark.anyio
async def test_a_booking_outside_the_window_starts_a_new_match():
    """The window is the whole mechanism; without it every game against a
    regular opponent would end up in one endless match."""
    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")

    await _log(deck_id, "win", opponents="The Rock")
    await _log(deck_id, "loss", opponents="The Rock")
    first_match = (await _games(deck_id))[0]["match_id"]

    # Age the two games past the window. `created_at` is what the rule reads —
    # `played_at` is a date and holds no time at all.
    await db.execute(
        "UPDATE deck_games SET created_at = datetime('now', ?) WHERE deck_id = ?",
        (f"-{game_log.MATCH_WINDOW_MINUTES + 30} minutes", deck_id),
    )
    await db.commit()

    later = await _log(deck_id, "win", opponents="The Rock")
    assert later["match_id"] is None, "a game two hours later is a new match"
    assert (await _games(deck_id))[0]["match_id"] == first_match


@pytest.mark.anyio
async def test_a_different_opponent_is_a_different_match():
    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")
    await _log(deck_id, "win", opponents="The Rock")
    other = await _log(deck_id, "win", opponents="Goblins")
    assert other["match_id"] is None


@pytest.mark.anyio
async def test_a_game_without_an_opponent_name_is_never_grouped():
    """Guessing from the timestamp alone would merge two unrelated games
    booked back to back — the one error nobody notices afterwards."""
    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")
    await _log(deck_id, "win")
    second = await _log(deck_id, "win")
    assert second["match_id"] is None


@pytest.mark.anyio
async def test_commander_games_stay_single_and_their_stats_do_not_move():
    """The 22 Commander decks must not notice this sprint at all."""
    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa", deck_format="Commander")
    await _log(deck_id, "win", opponents="Maxi, Carina")
    await _log(deck_id, "loss", opponents="Maxi, Carina")

    games = await _games(deck_id)
    assert all(g["pod_size"] == 4 for g in games)
    # Commander has no sideboard and no best-of-three, but the grouping rule is
    # about the clock and the opponent, not the format — so a pod that plays
    # two games in an evening does get grouped. The statistics block is what is
    # format-gated (`format_rules.matches`), not the column.
    stats = compute_performance_stats([
        {"result": g["result"], "on_play": g["on_play"], "played_at": g["played_at"],
         "match_id": g["match_id"], "game_in_match": g["game_in_match"]}
        for g in reversed(games)
    ])
    assert stats["games"] == 2
    assert stats["win_rate"] == 50.0


@pytest.mark.anyio
async def test_an_explicit_null_starts_a_fresh_match():
    """How a wrong grouping is undone at the moment of booking."""
    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")
    await _log(deck_id, "win", opponents="The Rock")
    second = await _log(deck_id, "win", opponents="The Rock", match_id=None)
    assert second["match_id"] is None


@pytest.mark.anyio
async def test_regrouping_by_hand_renumbers_both_matches():
    """The 90 minutes are a judgement, and this is the click that corrects it.
    A match left holding one game dissolves back into a single game."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")
    await _log(deck_id, "win", opponents="The Rock")
    await _log(deck_id, "loss", opponents="The Rock")
    games = await _games(deck_id)
    stray = games[1]["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.patch(f"/api/decks/{deck_id}/games/{stray}",
                              json={"match_id": ""})
        assert resp.status_code == 200
        assert resp.json()["match_id"] is None

    after = await _games(deck_id)
    assert all(g["match_id"] is None for g in after), (
        "a match of one is just a game"
    )
    assert all(g["game_in_match"] is None for g in after)


@pytest.mark.anyio
async def test_the_statistics_count_matches_and_the_games_after_sideboarding():
    """`game_2_3_win_rate` is what makes the sideboard notes worth writing: a
    deck that wins game one and loses the match has a sideboard problem."""
    games = [
        # newest first, as the endpoint returns them
        {"result": "loss", "match_id": "m1", "game_in_match": 3, "on_play": 0, "played_at": "2026-09-15"},
        {"result": "win", "match_id": "m1", "game_in_match": 2, "on_play": 1, "played_at": "2026-09-15"},
        {"result": "win", "match_id": "m1", "game_in_match": 1, "on_play": 1, "played_at": "2026-09-15"},
        {"result": "loss", "match_id": None, "game_in_match": None, "on_play": 0, "played_at": "2026-09-14"},
    ]
    stats = compute_performance_stats(games)

    assert stats["games"] == 4
    # One real match plus one standalone game, which in a Bo3 format is a Bo1
    # match rather than nothing.
    assert stats["matches"] == 2
    assert stats["match_wins"] == 1
    assert stats["match_losses"] == 1
    assert stats["match_win_rate"] == 50.0
    # Games two and three only.
    assert stats["sideboard_games"] == 2
    assert stats["game_2_3_win_rate"] == 50.0


@pytest.mark.anyio
async def test_an_unfinished_match_is_a_draw_not_a_loss():
    """1-1 and abandoned is exactly what it looks like. Counting it as a loss
    would be inventing an outcome nobody played."""
    stats = compute_performance_stats([
        {"result": "loss", "match_id": "m", "game_in_match": 2, "on_play": 0, "played_at": "2026-09-15"},
        {"result": "win", "match_id": "m", "game_in_match": 1, "on_play": 0, "played_at": "2026-09-15"},
    ])
    assert stats["matches"] == 1
    assert stats["match_wins"] == 0
    assert stats["match_losses"] == 0


@pytest.mark.anyio
async def test_the_ha_status_line_says_the_grouping_took():
    """The rule works off a clock nobody can see. Saying so is how you find out
    it grouped something it should not have, while you can still undo it."""
    from app.services import ha_form

    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")
    await _log(deck_id, "win", opponents="The Rock")
    second = await _log(deck_id, "loss", opponents="The Rock")

    line = ha_form.status_text(second)
    assert "game 2 of the match" in line
    assert "1-1" in line
    # A standalone game says nothing about matches at all.
    solo = await _log(deck_id, "win")
    assert "match" not in ha_form.status_text(solo)


# --- the guard -----------------------------------------------------------

@pytest.mark.anyio
async def test_nothing_writes_a_game_except_the_one_insert():
    """Two booking paths that drift apart is this codebase's most expensive
    recurring mistake: two of them in 0.45.0, two surplus readings before
    0.42.0, three bracket readers in 0.47.0. The pod-size default and the match
    grouping live in `insert_game`; a second INSERT anywhere would be a second
    set of rules that nobody notices is missing."""
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.name == "database.py":  # the schema itself
            continue
        text = path.read_text(encoding="utf-8")
        if "INSERT INTO deck_games" not in text:
            continue
        if path.name != "game_log.py":
            offenders.append(str(path.relative_to(app_dir)))

    assert not offenders, (
        f"a second way to write a game: {offenders}. "
        "Route it through game_log.insert_game instead."
    )


@pytest.mark.anyio
async def test_the_form_publishes_every_field_the_command_moved():
    """Picking a deck also moves the pod size — and a value the add-on stores
    without publishing is a value Home Assistant never learns about.

    Found by clicking the real dropdown against the real add-on: the database
    said 2, the dashboard kept showing 4, and the next submit would have taken
    the number nobody could see. The earlier tests were green because they read
    the database. Same class as the `json_attributes` trap in the HA packages:
    the state changed, nothing announced it, everything looked fine.
    """
    from app.services import ha_form

    db = await get_db()
    await insert_deck(db, "Sligh", deck_format="Premodern")
    labels, _ = await ha_form.deck_options(db)
    label = next(lbl for lbl in labels if "Sligh" in lbl)

    changed = await ha_form.apply_command(db, "deck", label)
    assert changed.get("deck") == label
    assert changed.get("pod_size") == "2", (
        "the pod size moved in the database but was not reported for publishing"
    )

    # A command that moves nothing else reports only itself.
    assert set(await ha_form.apply_command(db, "turns", "5")) == {"turns"}


@pytest.mark.anyio
async def test_the_mqtt_handler_echoes_the_pod_size_back_to_home_assistant(monkeypatch):
    """The call site, not the helper.

    ⚠️ The first version of this guard tested `apply_command` alone and stayed
    green when the publisher was reverted to echoing a single field — which was
    the actual bug. A test that covers the rule but not the place it is used
    proves nothing about the thing that broke.
    """
    from app.services import ha_form, ha_mqtt, ha_publisher

    db = await get_db()
    await insert_deck(db, "Sligh", deck_format="Premodern")
    labels, _ = await ha_form.deck_options(db)
    label = next(lbl for lbl in labels if "Sligh" in lbl)

    published: dict[str, str] = {}

    async def fake_publish(topic, payload, retain=False, qos=0):
        published[topic] = payload

    monkeypatch.setattr(ha_mqtt, "publish", fake_publish)
    monkeypatch.setattr(ha_mqtt, "topic_prefix", lambda: "mtg-collection")

    await ha_publisher._on_form_message("mtg-collection/form/deck/set", label.encode())

    assert published.get("mtg-collection/form/deck") == label
    assert published.get("mtg-collection/form/pod_size") == "2", (
        "the pod size changed in the database but was never published — "
        "HA would keep showing the old number"
    )
