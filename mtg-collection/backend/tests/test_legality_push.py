"""A deck that is being built is not illegal — the question does not apply yet.

The first full legality run over the real collection found three decks, and two
of them were drafts sitting in "Work in Progress": 43 cards and 2 cards. Neither
is a fault, and announcing them as one is how a checker loses its credibility —
the same lesson the Rat Colony exemption carries, one layer up.

Built as the second folder rule, deliberately not as a second use of the first:
a work-in-progress deck **does** tie up its cards and still should not push.
"""
import json

import pytest
from _helpers import insert_card, insert_deck

from app.database import DEFAULT_NO_LEGALITY_PUSH_FOLDERS, get_db
from app.services import legality
from app.services.sync_service import (
    apply_binding_from_folder,
    apply_legality_push_from_folder,
)

WIP = DEFAULT_NO_LEGALITY_PUSH_FOLDERS[0]


def _legalities(**kwargs) -> str:
    base = {k: "not_legal" for k in ("standard", "premodern", "commander")}
    base.update(kwargs)
    return json.dumps(base)


async def _draft(name: str, folder: str, *, cards: int = 5) -> int:
    """A Standard deck far too small to be legal, in the given folder."""
    db = await get_db()
    deck_id = await insert_deck(db, name, deck_format="Standard", folder=folder)
    for i in range(cards):
        card_id = await insert_card(db, f"{name} card {i}")
        await db.execute("UPDATE cards SET legalities = ? WHERE id = ?",
                         (_legalities(standard="legal"), card_id))
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,?,'main')",
            (deck_id, card_id, 1),
        )
    # The folder is a string on the row until a sync reads it — the derivation
    # is an action, not a column default.
    await apply_legality_push_from_folder(db, deck_id, folder)
    await apply_binding_from_folder(db, deck_id, folder)
    await db.commit()
    return deck_id


@pytest.fixture
def posted(monkeypatch):
    from app.services import notifications

    sent: list[dict] = []

    async def fake_notify(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(notifications, "send_persistent_notification", fake_notify)
    return sent


@pytest.mark.anyio
async def test_a_work_in_progress_deck_is_still_checked_but_never_announced(posted):
    """The check runs, the violation is real, the push does not happen.

    This is the whole point: silencing the notification must not silence the
    check. A deck page that stopped showing violations would be a checker that
    quietly stopped checking.
    """
    from app.services import notifications

    wip = await _draft("Half a deck", WIP)
    done = await _draft("Ready but broken", "Maxi")

    results = {r["deck_id"]: r for r in (await legality.check_all_decks())["results"]}
    assert results[wip]["legal"] is False, "the check must still run on a draft"
    assert results[wip]["violations"], "and still report what is wrong"

    assert await notifications.notify_newly_illegal_decks() == 1
    assert [p["notification_id"] for p in posted] == [f"stoerung_mtg_deck_illegal_{done}"]


@pytest.mark.anyio
async def test_a_deck_whose_cards_are_back_in_the_box_is_never_announced(posted):
    """The second gate, promised in the docstring since 0.48.0 and only wired
    once `binds_copies` existed. A disassembled deck going illegal is not news."""
    from app.services import notifications

    db = await get_db()
    shelved = await _draft("Taken apart", "Disassembled")
    # Belt and braces: the folder list for binding is its own setting.
    await db.execute("UPDATE decks SET binds_copies = 0 WHERE id = ?", (shelved,))
    await db.commit()

    await legality.check_all_decks()
    assert await notifications.notify_newly_illegal_decks() == 0
    assert posted == []


@pytest.mark.anyio
async def test_the_override_survives_a_sync_and_the_folder_does_not(client=None):
    """Same three states as `binds_copies`, and for the same reason: a sync
    re-derives the folder value on every run and must never undo a decision."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    db = await get_db()
    deck_id = await _draft("Nearly there", WIP)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        deck = (await ac.get(f"/api/decks/{deck_id}")).json()
        assert deck["legality_push"] is False
        assert deck["legality_push_override"] is None

        # "No, tell me about this one anyway."
        deck = (await ac.put(f"/api/decks/{deck_id}/user-fields",
                             json={"legality_push_override": True})).json()
        assert deck["legality_push"] is True

        await apply_legality_push_from_folder(db, deck_id, WIP)
        await db.commit()
        deck = (await ac.get(f"/api/decks/{deck_id}")).json()
        assert deck["legality_push"] is True, "the sync overwrote a hand-set decision"

        # Clearing hands the deck back to its folder rather than freezing the
        # current value — those are different statements about who decides.
        deck = (await ac.put(f"/api/decks/{deck_id}/user-fields",
                             json={"legality_push_override": None})).json()
        assert deck["legality_push_override"] is None
        assert deck["legality_push"] is False


@pytest.mark.anyio
async def test_silencing_one_deck_by_hand_does_not_touch_the_other(posted):
    """The per-deck option is the point of the two columns: the folder is a
    habit, the override is a decision about one deck."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.services import notifications

    noisy = await _draft("Broken and active", "Maxi")
    quiet = await _draft("Broken, leave me alone", "Maxi")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        await ac.put(f"/api/decks/{quiet}/user-fields",
                     json={"legality_push_override": False})

    await legality.check_all_decks()
    assert await notifications.notify_newly_illegal_decks() == 1
    assert posted[0]["notification_id"] == f"stoerung_mtg_deck_illegal_{noisy}"


@pytest.mark.anyio
async def test_the_deck_list_and_the_deck_page_agree_about_the_push():
    """The bracket disagreed between these two readers for a whole deploy
    (0.47.0 -> 0.47.1). One helper, asked twice."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    deck_id = await _draft("Building", WIP)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        page = (await ac.get(f"/api/decks/{deck_id}")).json()
        listed = next(d for d in (await ac.get("/api/decks/")).json() if d["id"] == deck_id)

    assert page["legality_push"] == listed["legality_push"] is False


@pytest.mark.anyio
async def test_the_ha_sensor_reports_the_violation_even_when_silenced():
    """Silencing hides the interruption, never the number. A template that
    reads `violations` must still see it, or the fault would simply vanish."""
    from app.services.ha_metrics import deck_stats

    deck_id = await _draft("Quiet but broken", WIP)
    await legality.check_all_decks()

    db = await get_db()
    stats = {d["deck_id"]: d for d in await deck_stats(db)}
    assert stats[deck_id]["legal"] is False
    assert stats[deck_id]["violations"] >= 1
    assert stats[deck_id]["legality_push"] is False
