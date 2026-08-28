"""Sprint 04: the computed WotC bracket.

Every deck in the database reported bracket 0, because the only source was an
Archidekt field that is null on all of them. The bracket is now worked out from
what the deck contains — and the point of the exercise is the evidence, so most
of these tests assert on *why* a bracket came out, not only on the number.
"""
import json

import pytest
from _helpers import insert_card, insert_deck
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services.bracket import (
    BASE_BRACKET,
    compute_bracket,
    compute_brackets_for_all_decks,
    effective_bracket,
)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _deck(cards: list[dict] | None = None, name: str = "Test Deck") -> int:
    db = await get_db()
    deck_id = await insert_deck(db, name)
    for spec in cards or []:
        card_id = await insert_card(db, **spec)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,1)",
            (deck_id, card_id),
        )
    await db.commit()
    return deck_id


async def _add_combo(
    deck_id: int, cards: list[str], *, is_partial: int = 0,
    mana_value_needed: float | None = 0, results: list[str] | None = None,
    combo_id: str = "",
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO deck_combos
        (deck_id, combo_id, name, cards_json, result_json, is_partial, mana_value_needed)
        VALUES (?,?,?,?,?,?,?)""",
        (deck_id, combo_id or "+".join(cards), " + ".join(cards), json.dumps(cards),
         json.dumps(results or ["Infinite creature tokens"]), is_partial, mana_value_needed),
    )
    await db.commit()


def _rules(detail: dict) -> set[str]:
    return {r["rule"] for r in detail["reasons"]}


# ---------------------------------------------------------------------------
# The scale itself
# ---------------------------------------------------------------------------

def test_the_display_order_is_hand_then_computed_then_import():
    assert effective_bracket(3, 4, 2) == 3, "a hand-set value wins"
    assert effective_bracket(None, 4, 2) == 4, "then the computation"
    assert effective_bracket(None, None, 2) == 2, "then the Archidekt mirror"
    assert effective_bracket(None, None, 0) is None, "0 is 'unset', not bracket 0"


@pytest.mark.anyio
async def test_a_plain_deck_lands_on_the_base_bracket():
    """A precon with no game changers, no combos and no land denial.

    It comes out 2 rather than 1: bracket 1 (Exhibition) describes a deck built
    around a bit, which nothing in a decklist can show.
    """
    deck_id = await _deck([{"name": "Forest"}, {"name": "Llanowar Elves"}], name="Precon")

    result = await compute_bracket(deck_id)

    assert result["bracket"] == BASE_BRACKET == 2
    assert result["detail"]["reasons"] == []
    assert "Exhibition" in result["detail"]["scale"]


# ---------------------------------------------------------------------------
# Game changers
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_one_game_changer_lifts_the_deck_to_three():
    deck_id = await _deck([
        {"name": "Rhystic Study", "game_changer": 1},
        {"name": "Forest"},
    ])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 3
    assert _rules(result["detail"]) == {"game_changers"}
    assert result["detail"]["reasons"][0]["evidence"] == ["Rhystic Study"]


@pytest.mark.anyio
async def test_a_fourth_game_changer_lifts_it_to_four():
    """Bracket 3 allows three. The fourth is the whole rule."""
    deck_id = await _deck([
        {"name": n, "game_changer": 1}
        for n in ("Rhystic Study", "Demonic Tutor", "Cyclonic Rift", "Smothering Tithe")
    ])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 4
    assert _rules(result["detail"]) == {"game_changers_over_limit"}
    assert len(result["detail"]["reasons"][0]["evidence"]) == 4


@pytest.mark.anyio
async def test_a_card_that_was_never_enriched_is_not_counted_as_clean():
    """`game_changer` is NULL until Scryfall has been asked. NULL is not 0, and
    the detail says how many cards are in that state so the answer can be read
    with the right amount of confidence."""
    deck_id = await _deck([{"name": "Unknown Card"}])

    detail = (await compute_bracket(deck_id))["detail"]

    assert detail["counts"]["game_changers"] == 0
    assert detail["coverage"]["cards_never_enriched_from_scryfall"] == 1


# ---------------------------------------------------------------------------
# Two-card infinite combos
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_an_early_two_card_combo_is_bracket_four():
    deck_id = await _deck([
        {"name": "Kiki-Jiki, Mirror Breaker", "cmc": 5},
        {"name": "Deceiver Exarch", "cmc": 3},
    ])
    await _add_combo(deck_id, ["Kiki-Jiki, Mirror Breaker", "Deceiver Exarch"],
                     mana_value_needed=0)

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 4
    assert _rules(result["detail"]) == {"two_card_combo_early"}
    assert result["detail"]["reasons"][0]["evidence"] == [
        "Kiki-Jiki, Mirror Breaker + Deceiver Exarch"
    ]


@pytest.mark.anyio
async def test_an_expensive_two_card_combo_is_only_bracket_three():
    """Same shape, but too expensive to assemble by turn seven — the line
    between bracket 4 and bracket 3 for two-card infinites."""
    deck_id = await _deck([
        {"name": "Expensive Thing", "cmc": 8},
        {"name": "Other Thing", "cmc": 4},
    ])
    await _add_combo(deck_id, ["Expensive Thing", "Other Thing"], mana_value_needed=2)

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 3
    assert _rules(result["detail"]) == {"two_card_combo_late"}


@pytest.mark.anyio
async def test_a_three_card_combo_does_not_trigger_the_two_card_rule():
    deck_id = await _deck([{"name": n, "cmc": 1} for n in ("A", "B", "C")])
    await _add_combo(deck_id, ["A", "B", "C"], mana_value_needed=0)

    result = await compute_bracket(deck_id)

    # Not bracket 4 — but not Core either: the deck still wins on the spot.
    assert result["bracket"] == 3
    assert _rules(result["detail"]) == {"infinite_combo"}
    assert result["detail"]["counts"]["complete_combos"] == 1
    assert result["detail"]["counts"]["two_card_combos_early"] == 0


@pytest.mark.anyio
async def test_a_combo_the_deck_is_still_missing_a_card_for_does_not_count():
    deck_id = await _deck([{"name": "Anger", "cmc": 4}])
    await _add_combo(deck_id, ["Anger", "Breath of Fury"], is_partial=1, mana_value_needed=0)

    result = await compute_bracket(deck_id)

    assert result["bracket"] == BASE_BRACKET
    assert result["detail"]["counts"]["complete_combos"] == 0


# ---------------------------------------------------------------------------
# Mass land denial and extra turns
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_mass_land_denial_is_bracket_four():
    deck_id = await _deck([{"name": "Death Cloud", "mass_land_denial": 1}])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 4
    assert result["detail"]["reasons"][0]["evidence"] == ["Death Cloud"]


@pytest.mark.anyio
async def test_an_unclassified_card_still_gets_caught_by_its_rules_text():
    """Spellbook only classifies cards in its combo database — 49 of 88 on a
    real deck. The oracle fallback covers the plainest wording so a card it
    does not know is not silently clean."""
    deck_id = await _deck([
        {"name": "Armageddon", "oracle_text": "Destroy all lands."},
    ])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 4
    assert result["detail"]["reasons"][0]["rule"] == "mass_land_denial"
    assert result["detail"]["coverage"]["cards_not_classified_by_spellbook"] == 1


@pytest.mark.anyio
async def test_a_classified_no_beats_the_text_fallback():
    """A card Spellbook has looked at and cleared is not second-guessed by a
    regex — otherwise the fallback would overrule the better source."""
    deck_id = await _deck([{
        "name": "Innocent Card",
        "mass_land_denial": 0,
        "oracle_text": "Destroy all lands you control? No: this is flavour text.",
    }])

    assert (await compute_bracket(deck_id))["bracket"] == BASE_BRACKET


@pytest.mark.anyio
async def test_three_extra_turn_cards_read_as_a_plan():
    deck_id = await _deck([
        {"name": n, "extra_turn": 1} for n in ("Time Warp", "Temporal Manipulation", "Capture of Jingzhou")
    ])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 3
    assert _rules(result["detail"]) == {"extra_turn_cards"}


@pytest.mark.anyio
async def test_two_extra_turn_cards_are_still_a_trick():
    deck_id = await _deck([{"name": n, "extra_turn": 1} for n in ("Time Warp", "Nexus of Fate")])

    assert (await compute_bracket(deck_id))["bracket"] == BASE_BRACKET


@pytest.mark.anyio
async def test_a_combo_that_loops_the_turns_is_bracket_four():
    """Chaining is the line the bracket guidance draws, not owning the cards."""
    deck_id = await _deck([
        {"name": "Time Warp", "extra_turn": 1, "cmc": 5},
        {"name": "Archaeomancer", "cmc": 4},
    ])
    await _add_combo(deck_id, ["Time Warp", "Archaeomancer"],
                     mana_value_needed=6, results=["Infinite turns"])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == 4
    assert "extra_turns_chained" in _rules(result["detail"])


# ---------------------------------------------------------------------------
# The whole thing
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_the_highest_floor_wins_and_every_reason_is_kept():
    deck_id = await _deck([
        {"name": "Rhystic Study", "game_changer": 1},
        {"name": "Death Cloud", "mass_land_denial": 1},
        {"name": "Kiki-Jiki, Mirror Breaker", "cmc": 5},
        {"name": "Deceiver Exarch", "cmc": 3},
    ])
    await _add_combo(deck_id, ["Kiki-Jiki, Mirror Breaker", "Deceiver Exarch"],
                     mana_value_needed=0)

    detail = (await compute_bracket(deck_id))["detail"]

    assert detail["bracket"] == 4
    assert _rules(detail) == {"game_changers", "mass_land_denial", "two_card_combo_early"}
    assert min(r["minimum"] for r in detail["reasons"]) == 3, (
        "the bracket-3 reason is kept even though a bracket-4 one outranks it"
    )


@pytest.mark.anyio
async def test_the_verdict_is_stored_with_its_evidence():
    deck_id = await _deck([{"name": "Rhystic Study", "game_changer": 1}])
    await compute_bracket(deck_id)

    db = await get_db()
    cursor = await db.execute(
        "SELECT computed_bracket, computed_bracket_detail, computed_bracket_at FROM decks WHERE id = ?",
        (deck_id,),
    )
    row = await cursor.fetchone()
    assert row[0] == 3
    assert json.loads(row[1])["reasons"][0]["evidence"] == ["Rhystic Study"]
    assert row[2] is not None


@pytest.mark.anyio
async def test_recompute_all_reports_every_deck(client):
    await _deck([{"name": "Rhystic Study", "game_changer": 1}], name="One")
    await _deck([{"name": "Forest"}], name="Two")

    result = await compute_brackets_for_all_decks()

    assert result["decks"] == 2 and result["computed"] == 2
    assert sorted(r["bracket"] for r in result["results"]) == [2, 3]


@pytest.mark.anyio
async def test_the_routes_recompute_and_hand_back_the_reasoning(client):
    deck_id = await _deck([{"name": "Death Cloud", "mass_land_denial": 1}])

    async with client:
        single = await client.post(f"/api/decks/{deck_id}/bracket/recompute")
        listed = await client.get("/api/decks/")
        detail = await client.get(f"/api/decks/{deck_id}")
        every = await client.post("/api/decks/bracket/recompute-all")

    assert single.status_code == 200 and single.json()["bracket"] == 4
    assert listed.json()[0]["effective_bracket"] == 4
    assert detail.json()["computed_bracket_detail"]["reasons"][0]["rule"] == "mass_land_denial"
    assert every.status_code == 200 and every.json()["computed"] == 1


@pytest.mark.anyio
async def test_a_hand_set_bracket_wins_over_the_computed_one(client):
    """The deciding property of the whole feature: the computation is a
    suggestion, and a person overrules it."""
    deck_id = await _deck([{"name": "Death Cloud", "mass_land_denial": 1}])
    await compute_bracket(deck_id)

    async with client:
        await client.put(f"/api/decks/{deck_id}/user-fields", json={"user_bracket": 2})
        detail = (await client.get(f"/api/decks/{deck_id}")).json()
        listed = (await client.get("/api/decks/")).json()

    assert detail["computed_bracket"] == 4
    assert detail["user_bracket"] == 2
    assert detail["effective_bracket"] == 2
    assert listed[0]["effective_bracket"] == 2


@pytest.mark.anyio
async def test_a_two_card_combo_does_not_also_report_the_generic_infinite():
    """The specific reason replaces the general one rather than joining it —
    otherwise every two-card combo would list its rule twice."""
    deck_id = await _deck([{"name": "A", "cmc": 1}, {"name": "B", "cmc": 1}])
    await _add_combo(deck_id, ["A", "B"], mana_value_needed=0)

    result = await compute_bracket(deck_id)

    assert _rules(result["detail"]) == {"two_card_combo_early"}


@pytest.mark.anyio
async def test_a_four_piece_engine_is_not_a_bracket_three_signal():
    """The bracket rules are aimed at combos that end a game out of nowhere.

    "Squirreled Away" holds a four-card loop that makes infinite Food tokens
    and wins nothing by itself; Commander Spellbook files that deck as
    Exhibition. The piece limit is what keeps the generic infinite rule from
    overruling both.
    """
    deck_id = await _deck([{"name": n, "cmc": 2} for n in ("A", "B", "C", "D")])
    await _add_combo(deck_id, ["A", "B", "C", "D"], mana_value_needed=0,
                     results=["Infinite Food tokens"])

    result = await compute_bracket(deck_id)

    assert result["bracket"] == BASE_BRACKET
    assert result["detail"]["counts"]["complete_combos"] == 1
