"""Sprint 03: combo coverage, and saying what is actually missing.

The cache held 433 combos across 4 of 21 decks, and not one of the 418 partial
ones named the card it was short of. Two separate causes, both reproduced here:
a deck the incremental sync skipped never reached the combo call at all, and
`missingCards` — the field the extractor looked for — does not exist in the
Spellbook response.
"""
import json

import pytest
from _helpers import insert_card, insert_deck
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services import combo_sync
from app.services.combo_sync import (
    _extract_combo_fields,
    sync_combos_for_deck,
    sync_combos_for_stale_decks,
)


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    monkeypatch.setattr(combo_sync, "BULK_PACING_SECONDS", 0)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _combo(combo_id: str, uses: list[str], **extra) -> dict:
    """A combo in the shape the live API returns (checked 2026-08-28)."""
    return {
        "id": combo_id,
        "uses": [{"card": {"name": n}, "quantity": 1} for n in uses],
        "produces": [{"feature": {"name": "Infinite combat phases"}}],
        "identity": "UR",
        "description": "Do the thing, then do it again.",
        **extra,
    }


async def _deck_with_cards(names: list[str], commander: str | None = None) -> int:
    db = await get_db()
    deck_id = await insert_deck(db, "Sharknado")
    for name in names:
        card_id = await insert_card(db, name)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,?)",
            (deck_id, card_id, 1),
        )
    if commander:
        card_id = await insert_card(db, commander)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, is_commander) VALUES (?,?,?,1)",
            (deck_id, card_id, 1),
        )
        await db.execute(
            "UPDATE decks SET commander_name = ? WHERE id = ?", (commander, deck_id)
        )
    await db.commit()
    return deck_id


def _patch_spellbook(monkeypatch, included: list[dict], almost: list[dict]):
    async def fake(card_names, commander_name=None):
        return {"included": included, "almost_included": almost}

    from app.clients import spellbook as spellbook_module
    monkeypatch.setattr(spellbook_module.spellbook, "find_combos_in_decklist", fake)


# ---------------------------------------------------------------------------
# What is missing
# ---------------------------------------------------------------------------

def test_missing_cards_are_derived_from_uses_minus_the_deck():
    """The response has no `missingCards`; it has to be worked out."""
    combo = _combo("513-5034--46", ["Anger", "Breath of Fury"])
    fields = _extract_combo_fields(combo, is_partial=True, deck_keys={"anger", "sol ring"})
    assert json.loads(fields["missing_cards_json"]) == ["Breath of Fury"]


def test_a_complete_combo_names_nothing_as_missing():
    combo = _combo("1", ["Anger", "Breath of Fury"])
    fields = _extract_combo_fields(combo, is_partial=False, deck_keys=set())
    assert json.loads(fields["missing_cards_json"]) == []


def test_a_double_faced_card_counts_as_present_under_either_face():
    combo = _combo("2", ["Valakut Awakening"])
    deck = {"valakut awakening // valakut stoneforge", "valakut awakening"}
    fields = _extract_combo_fields(combo, is_partial=True, deck_keys=deck)
    assert json.loads(fields["missing_cards_json"]) == []


def test_when_no_named_card_is_missing_the_template_is_named():
    """Some combos are one *template* short ("any creature with flying"). An
    empty list there would read as "this combo is complete"."""
    combo = _combo(
        "3", ["Sol Ring"],
        requires=[{"template": {"name": "Creature with flying"}, "quantity": 1}],
    )
    fields = _extract_combo_fields(combo, is_partial=True, deck_keys={"sol ring"})
    assert json.loads(fields["missing_cards_json"]) == ["Creature with flying"]


# ---------------------------------------------------------------------------
# Asking, and knowing that you asked
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sync_stores_both_buckets_and_stamps_the_deck(monkeypatch):
    deck_id = await _deck_with_cards(["Anger", "Sol Ring"], commander="Captain Howler")
    _patch_spellbook(
        monkeypatch,
        included=[_combo("full-1", ["Anger", "Sol Ring"])],
        almost=[_combo("part-1", ["Anger", "Breath of Fury"])],
    )

    assert await sync_combos_for_deck(deck_id) == 2

    db = await get_db()
    cursor = await db.execute(
        "SELECT combo_id, is_partial, missing_cards_json FROM deck_combos WHERE deck_id = ? ORDER BY combo_id",
        (deck_id,),
    )
    rows = await cursor.fetchall()
    assert [(r[0], r[1]) for r in rows] == [("full-1", 0), ("part-1", 1)]
    assert json.loads(rows[1][2]) == ["Breath of Fury"]

    cursor = await db.execute("SELECT combos_synced_at FROM decks WHERE id = ?", (deck_id,))
    assert (await cursor.fetchone())[0] is not None


@pytest.mark.anyio
async def test_a_deck_with_no_combos_is_still_stamped(monkeypatch):
    """"Asked, none found" and "never asked" both leave zero rows in
    `deck_combos`. Only the stamp tells them apart — without it the top-up
    would re-ask the same deck every single night."""
    deck_id = await _deck_with_cards(["Forest", "Island"])
    _patch_spellbook(monkeypatch, included=[], almost=[])

    assert await sync_combos_for_deck(deck_id) == 0

    db = await get_db()
    cursor = await db.execute("SELECT combos_synced_at FROM decks WHERE id = ?", (deck_id,))
    assert (await cursor.fetchone())[0] is not None
    assert (await sync_combos_for_stale_decks())["decks"] == 0


@pytest.mark.anyio
async def test_a_spellbook_failure_raises_instead_of_reporting_zero(monkeypatch):
    """The old code caught the error and returned 0, so an outage was
    indistinguishable from a deck without combos — and the deck kept its stamp
    free rather than claiming a result it never got."""
    deck_id = await _deck_with_cards(["Anger"])

    async def boom(card_names, commander_name=None):
        raise RuntimeError("Spellbook 503")

    from app.clients import spellbook as spellbook_module
    monkeypatch.setattr(spellbook_module.spellbook, "find_combos_in_decklist", boom)

    with pytest.raises(RuntimeError):
        await sync_combos_for_deck(deck_id)

    db = await get_db()
    cursor = await db.execute("SELECT combos_synced_at FROM decks WHERE id = ?", (deck_id,))
    assert (await cursor.fetchone())[0] is None, "a failed ask must not count as asked"


@pytest.mark.anyio
async def test_the_cached_combos_survive_until_the_replacement_is_in(monkeypatch):
    """The sync deletes before it inserts, so a failure between the two would
    leave the deck empty. It must not get that far."""
    deck_id = await _deck_with_cards(["Anger"])
    _patch_spellbook(monkeypatch, included=[_combo("keep-me", ["Anger"])], almost=[])
    await sync_combos_for_deck(deck_id)

    async def boom(card_names, commander_name=None):
        raise RuntimeError("Spellbook 503")

    from app.clients import spellbook as spellbook_module
    monkeypatch.setattr(spellbook_module.spellbook, "find_combos_in_decklist", boom)
    with pytest.raises(RuntimeError):
        await sync_combos_for_deck(deck_id)

    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM deck_combos WHERE deck_id = ?", (deck_id,)
    )
    assert (await cursor.fetchone())[0] == 1


# ---------------------------------------------------------------------------
# Coverage across the shelf
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_the_topup_asks_about_every_deck_that_was_never_asked(monkeypatch):
    """The reason 17 of 21 decks held nothing: the incremental sync skips an
    unchanged deck, and the combo call sat inside the branch it skipped."""
    first = await _deck_with_cards(["Anger"])
    second = await _deck_with_cards(["Sol Ring"])
    _patch_spellbook(monkeypatch, included=[], almost=[_combo("p", ["Anger", "Kiki-Jiki"])])

    result = await sync_combos_for_stale_decks()

    assert result["decks"] == 2 and result["failed"] == 0
    assert {r["deck_id"] for r in result["results"]} == {first, second}
    assert (await sync_combos_for_stale_decks())["decks"] == 0, "fresh decks are left alone"


@pytest.mark.anyio
async def test_a_stale_deck_comes_up_again(monkeypatch):
    deck_id = await _deck_with_cards(["Anger"])
    _patch_spellbook(monkeypatch, included=[], almost=[])
    await sync_combos_for_deck(deck_id)

    db = await get_db()
    await db.execute(
        "UPDATE decks SET combos_synced_at = datetime('now', '-99 days') WHERE id = ?",
        (deck_id,),
    )
    await db.commit()

    assert (await sync_combos_for_stale_decks())["decks"] == 1


@pytest.mark.anyio
async def test_one_failing_deck_does_not_stop_the_others(monkeypatch):
    good = await _deck_with_cards(["Anger"])
    bad = await _deck_with_cards(["Sol Ring"])

    async def selective(card_names, commander_name=None):
        if "Sol Ring" in card_names:
            raise RuntimeError("Spellbook 503")
        return {"included": [_combo("ok", ["Anger"])], "almost_included": []}

    from app.clients import spellbook as spellbook_module
    monkeypatch.setattr(spellbook_module.spellbook, "find_combos_in_decklist", selective)

    result = await sync_combos_for_stale_decks()

    assert result["decks"] == 2 and result["failed"] == 1 and result["combos"] == 1
    by_deck = {r["deck_id"]: r for r in result["results"]}
    assert by_deck[good]["combos"] == 1
    assert "Spellbook 503" in by_deck[bad]["error"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sync_all_route_is_not_read_as_a_deck_id(client, monkeypatch):
    """`/combos/sync-all` sits next to `/{deck_id}/combos`; declaring it after
    the parameterised routes would make FastAPI try "combos" as a deck id."""
    await _deck_with_cards(["Anger"])
    _patch_spellbook(monkeypatch, included=[], almost=[])

    async with client:
        resp = await client.post("/api/decks/combos/sync-all")

    assert resp.status_code == 200
    assert resp.json()["decks"] == 1


@pytest.mark.anyio
async def test_a_failed_single_deck_sync_answers_502_not_zero(client, monkeypatch):
    deck_id = await _deck_with_cards(["Anger"])

    async def boom(card_names, commander_name=None):
        raise RuntimeError("Spellbook 503")

    from app.clients import spellbook as spellbook_module
    monkeypatch.setattr(spellbook_module.spellbook, "find_combos_in_decklist", boom)

    async with client:
        resp = await client.post(f"/api/decks/{deck_id}/combos/sync")

    assert resp.status_code == 502
    assert "Spellbook" in resp.json()["detail"]
