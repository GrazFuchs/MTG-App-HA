"""Sprint 05: the edhpowerlevel port.

The original runs in a browser, so the only way to check this port from here is
against its published behaviour, step by step. Every expected number below is
worked out by hand from the specification rather than copied from a run — which
is why the arithmetic is written out in the comments: a test that just asserts
whatever the code returned would confirm nothing.
"""
import json

import pytest
from _helpers import insert_card, insert_deck
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services.power_level import (
    FACTORS,
    compute_power_for_all_decks,
    compute_power_level,
    de,
    reference_url,
)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _deck(cards: list[dict], name: str = "Test Deck") -> int:
    db = await get_db()
    deck_id = await insert_deck(db, name)
    for spec in cards:
        spec = dict(spec)
        quantity = spec.pop("quantity", 1)
        commander = spec.pop("commander", False)
        card_id = await insert_card(db, **spec)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, is_commander) VALUES (?,?,?,?)",
            (deck_id, card_id, quantity, int(commander)),
        )
    await db.commit()
    return deck_id


# ---------------------------------------------------------------------------
# The interpolator
# ---------------------------------------------------------------------------

def test_de_returns_the_decile_index_at_a_boundary():
    # priceCurve[5] is 10, so a $10 card sits exactly on the sixth boundary.
    assert de(10.0, FACTORS["priceCurve"]) == 5.0


def test_de_interpolates_linearly_inside_a_decile():
    # Halfway between priceCurve[5]=10 and [6]=15.
    assert de(12.5, FACTORS["priceCurve"]) == pytest.approx(5.5)


def test_de_weights_the_decile_but_not_the_fraction():
    """The quirk that decides whether this port matches the original.

    At weight 1.25 the boundary moves to 5 x 1.25 = 6.25, but the half-decile
    on top stays 0.5 rather than becoming 0.625. Implementing this "properly"
    is the most likely way to drift.
    """
    assert de(12.5, FACTORS["priceCurve"], 1.25) == pytest.approx(6.25 + 0.5)


def test_de_floors_and_caps():
    assert de(0, FACTORS["priceCurve"]) == 0.0
    assert de(-5, FACTORS["priceCurve"]) == 0.0
    # Above the last stop the weighted maximum is returned flat.
    assert de(1000, FACTORS["priceCurve"], 1.25) == pytest.approx(10 * 1.25)


# ---------------------------------------------------------------------------
# One card at a time
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_a_single_card_scores_what_the_chain_says_it_should():
    """Worked through by hand:

    price 10.00 -> de(10, priceCurve, 1.25) = 5 x 1.25          = 6.25
    rank 100    -> popularity 27000-100 = 26900, decile 9,
                   de(...) = 9 x 0.75 + 200/300                 = 7.4166…
    impact = 13.6666…, and the Forest is a flat 2.
    avg cost 2, tipping point 2, midpoint 2
    efficiency = (6-2)/4.25 = 0.941…, scale = 0.65 + 0.45 x that = 1.0735…
    score = 15.6666… x 1.0735… = 16.82
    """
    deck_id = await _deck([
        {"name": "Test Spell", "type_line": "Instant", "cmc": 2,
         "price_usd": "10.00", "edhrec_rank": 100},
        {"name": "Forest", "type_line": "Basic Land — Forest"},
    ])

    result = await compute_power_level(deck_id)

    assert result["detail"]["total_impact"] == pytest.approx(15.7, abs=0.05)
    assert result["detail"]["avg_cost"] == pytest.approx(2.0)
    assert result["detail"]["tipping_point"] == 2
    assert result["detail"]["efficiency"] == pytest.approx(9.41, abs=0.01)
    assert result["score"] == pytest.approx(16.82, abs=0.05)


@pytest.mark.anyio
async def test_a_basic_land_gets_a_flat_floor_after_the_land_factor():
    """Two basics are worth 4, whatever they would have scored on price."""
    deck_id = await _deck([
        {"name": "Island", "type_line": "Basic Land — Island",
         "price_usd": "99.00", "edhrec_rank": 1, "quantity": 2},
    ])

    detail = (await compute_power_level(deck_id))["detail"]

    assert detail["total_impact"] == pytest.approx(4.0)


@pytest.mark.anyio
async def test_a_nonbasic_land_keeps_its_price_but_is_damped():
    deck_id = await _deck([
        {"name": "Command Tower", "type_line": "Land",
         "price_usd": "10.00", "edhrec_rank": 100},
    ])

    detail = (await compute_power_level(deck_id))["detail"]

    # The same 13.666… as the spell above, times the 0.6 land factor.
    assert detail["total_impact"] == pytest.approx(13.6667 * 0.6, abs=0.01)
    assert detail["lands"] == 1


@pytest.mark.anyio
async def test_a_reserved_list_card_has_its_price_damped_before_the_curve():
    """$100 x 0.2 = $20, which is decile 6 rather than the cap."""
    deck_id = await _deck([
        {"name": "Old Rare", "type_line": "Artifact", "cmc": 2,
         "price_usd": "100.00", "reserved": 1},
    ])

    detail = (await compute_power_level(deck_id))["detail"]

    # de(20, priceCurve, 1.25): decile 6 (15..25) -> 6 x 1.25 + 5/10 = 8.0
    assert detail["total_impact"] == pytest.approx(8.0, abs=0.01)


@pytest.mark.anyio
async def test_a_modal_double_faced_card_counts_as_a_land():
    """It is damped like a land *and* drops out of the average mana cost —
    the third of the porting traps."""
    deck_id = await _deck([
        {"name": "Agadeem's Awakening", "type_line": "Sorcery", "cmc": 6,
         "layout": "modal_dfc", "price_usd": "10.00", "edhrec_rank": 100},
        {"name": "Test Spell", "type_line": "Instant", "cmc": 2,
         "price_usd": "10.00", "edhrec_rank": 100},
    ])

    detail = (await compute_power_level(deck_id))["detail"]

    assert detail["lands"] == 1
    # Only the instant is costed, so the six-mana face does not raise the curve.
    assert detail["avg_cost"] == pytest.approx(2.0)


@pytest.mark.anyio
async def test_a_free_spell_is_costed_at_zero():
    deck_id = await _deck([
        {"name": "Force of Will", "type_line": "Instant", "cmc": 5,
         "price_usd": "10.00", "edhrec_rank": 100},
    ])

    assert (await compute_power_level(deck_id))["detail"]["avg_cost"] == 0.0


@pytest.mark.anyio
async def test_the_commander_bonus_needs_the_card_to_be_the_commander():
    """The fifth trap: the multiplier is not a property of the card."""
    as_commander = await _deck([
        {"name": "Kinnan, Bonder Prodigy", "type_line": "Legendary Creature — Human Druid",
         "cmc": 2, "price_usd": "10.00", "edhrec_rank": 100, "commander": True},
    ], name="Commander")
    in_the_99 = await _deck([
        {"name": "Kinnan, Bonder Prodigy", "type_line": "Legendary Creature — Human Druid",
         "cmc": 2, "price_usd": "10.00", "edhrec_rank": 100},
    ], name="Ninety-nine")

    lead = (await compute_power_level(as_commander))["detail"]["total_impact"]
    plain = (await compute_power_level(in_the_99))["detail"]["total_impact"]

    # `rel`, not `abs`: total_impact is stored rounded to 0.1, so 13.67 x 4
    # and 13.7 x 4 differ in the last digit without anything being wrong.
    assert lead == pytest.approx(plain * 4.0, rel=0.01)


@pytest.mark.anyio
async def test_a_price_override_moves_the_card_up_the_curve():
    """Sol Ring is cheap and everywhere; the original multiplies its price by 8
    so the score reflects what it does rather than what it costs."""
    sol = await _deck([
        {"name": "Sol Ring", "type_line": "Artifact", "cmc": 1, "price_usd": "2.00"},
    ], name="Sol")
    other = await _deck([
        {"name": "Plain Rock", "type_line": "Artifact", "cmc": 1, "price_usd": "2.00"},
    ], name="Other")

    sol_impact = (await compute_power_level(sol))["detail"]["total_impact"]
    other_impact = (await compute_power_level(other))["detail"]["total_impact"]

    assert sol_impact > other_impact


@pytest.mark.anyio
async def test_efficiency_is_not_clamped_at_either_end():
    """The second trap. A deck cheaper than the floor scores above 10, and the
    site does the same — clamping it would quietly change extreme decks."""
    cheap = await _deck([
        {"name": "One Drop", "type_line": "Creature — Bear", "cmc": 1,
         "price_usd": "1.00", "edhrec_rank": 5000},
    ], name="Cheap")

    detail = (await compute_power_level(cheap))["detail"]

    # midpoint 1 -> (6-1)/4.25 = 1.176… -> displayed as 11.76
    assert detail["efficiency"] == pytest.approx(11.76, abs=0.01)


# ---------------------------------------------------------------------------
# Deck level
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_the_result_is_stored_with_its_working(client):
    deck_id = await _deck([
        {"name": "Test Spell", "type_line": "Instant", "cmc": 2,
         "price_usd": "10.00", "edhrec_rank": 100},
    ])
    await compute_power_level(deck_id)

    db = await get_db()
    cursor = await db.execute(
        "SELECT power_score, power_level, power_detail, power_computed_at FROM decks WHERE id = ?",
        (deck_id,),
    )
    row = await cursor.fetchone()
    detail = json.loads(row[2])
    assert row[0] > 0 and row[3] is not None
    assert detail["top_cards"][0]["name"] == "Test Spell"
    assert detail["pop_curve_derived"] == "2024-09"
    assert "synergy" in detail["caveat"]


@pytest.mark.anyio
async def test_a_cheap_deck_scores_below_an_expensive_one():
    """The score is a comparison between real decks; this is the property that
    has to hold even when the absolute numbers are debatable."""
    precon = await _deck([
        {"name": f"Common {i}", "type_line": "Creature — Bear", "cmc": 4,
         "price_usd": "0.20", "edhrec_rank": 20000} for i in range(10)
    ], name="Precon")
    tuned = await _deck([
        {"name": f"Staple {i}", "type_line": "Artifact", "cmc": 1,
         "price_usd": "40.00", "edhrec_rank": 200} for i in range(10)
    ], name="Tuned")

    assert (await compute_power_level(tuned))["score"] > (
        await compute_power_level(precon))["score"]


@pytest.mark.anyio
async def test_recompute_all_and_the_routes(client):
    deck_id = await _deck([
        {"name": "Test Spell", "type_line": "Instant", "cmc": 2,
         "price_usd": "10.00", "edhrec_rank": 100},
    ])

    every = await compute_power_for_all_decks()
    assert every["decks"] == 1 and every["computed"] == 1

    async with client:
        single = await client.post(f"/api/decks/{deck_id}/power/recompute")
        listed = await client.get("/api/decks/")
        detail = await client.get(f"/api/decks/{deck_id}")

    assert single.status_code == 200
    # 13.6666… x 1.0735… — this deck has no land, so it is the spell alone.
    assert listed.json()[0]["power_score"] == pytest.approx(14.67, abs=0.05)
    assert detail.json()["power_detail"]["tipping_point"] == 2


@pytest.mark.anyio
async def test_the_reference_url_is_shaped_the_way_the_site_expects():
    """Newlines become `~`, spaces `+`, and `~Z~` closes it — without the
    terminator the site rejects the link as truncated. `[Commander]` is kept,
    as the site's own internal encoder does, because the commander multiplier
    depends on it."""
    deck_id = await _deck([
        {"name": "Kinnan, Bonder Prodigy", "type_line": "Legendary Creature",
         "commander": True},
        {"name": "Sol Ring", "type_line": "Artifact"},
    ])

    url = await reference_url(deck_id)

    assert url.startswith("https://edhpowerlevel.com?d=")
    assert url.endswith("~Z~")
    assert "1+Kinnan%2C+Bonder+Prodigy+%5BCommander%5D" in url
    assert "~1+Sol+Ring" in url
