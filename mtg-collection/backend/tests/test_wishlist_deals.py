"""Sprint 06: noticing that a wanted card got cheap.

`is_deal` was a state — "under the target right now" — and states do not
announce themselves. What is tested here is the crossing: the price was above
the target at the last check and is not any more. Everything else about this
feature follows from getting that one distinction right.
"""
import pytest
from _helpers import add_wishlist, insert_card, insert_deck
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services import wishlist_deals
from app.services.wishlist_deals import check_wishlist_deals


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _no_notifications(monkeypatch):
    """Record what would have been sent instead of calling Home Assistant."""
    sent: list[dict] = []

    async def fake(title, message, deep_link=None, notification_id=None):
        sent.append({"title": title, "message": message, "id": notification_id})

    monkeypatch.setattr(wishlist_deals, "send_persistent_notification", fake)
    return sent


@pytest.fixture
def sent(_no_notifications):
    return _no_notifications


async def _wanted(name: str, price_eur: str, target: float, **kw) -> int:
    db = await get_db()
    card_id = await insert_card(db, name, price_eur=price_eur)
    item_id = await add_wishlist(db, card_id, **kw)
    await db.execute(
        "UPDATE wishlist SET target_price_eur = ? WHERE id = ?", (target, item_id)
    )
    await db.commit()
    return item_id


async def _set_price(item_id: int, price: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE cards SET price_eur = ? WHERE id = (SELECT card_id FROM wishlist WHERE id = ?)",
        (price, item_id),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# The crossing
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_the_first_run_records_but_does_not_announce():
    """There is nothing to compare against yet. Announcing here would mean
    every card already under its target shouts on the day the feature ships."""
    await _wanted("Rhystic Study", "30.00", target=35.0)

    result = await check_wishlist_deals()

    assert result["deals"] == []
    db = await get_db()
    cursor = await db.execute("SELECT last_price_eur FROM wishlist")
    assert (await cursor.fetchone())[0] == pytest.approx(30.0)


@pytest.mark.anyio
async def test_a_price_crossing_the_target_is_announced_once(sent):
    item_id = await _wanted("Rhystic Study", "40.00", target=35.0)
    await check_wishlist_deals()          # above target: records 40
    await _set_price(item_id, "34.50")

    first = await check_wishlist_deals()
    second = await check_wishlist_deals()  # still 34.50, no new crossing

    assert len(first["deals"]) == 1
    assert first["deals"][0]["card_name"] == "Rhystic Study"
    assert first["deals"][0]["price_eur"] == pytest.approx(34.5)
    assert first["deals"][0]["previous_price_eur"] == pytest.approx(40.0)
    assert second["deals"] == []
    assert len(sent) == 1
    assert "34.50" in sent[0]["message"] and "35.00" in sent[0]["message"]


@pytest.mark.anyio
async def test_staying_below_the_target_is_not_a_new_deal():
    """The state was already true. Only the transition is news."""
    item_id = await _wanted("Cheap Card", "10.00", target=35.0)
    await check_wishlist_deals()
    await _set_price(item_id, "9.00")

    assert (await check_wishlist_deals())["deals"] == []


@pytest.mark.anyio
async def test_a_price_exactly_on_the_target_counts_as_reached():
    item_id = await _wanted("Exact Card", "40.00", target=35.0)
    await check_wishlist_deals()
    await _set_price(item_id, "35.00")

    assert len((await check_wishlist_deals())["deals"]) == 1


@pytest.mark.anyio
async def test_an_oscillating_price_is_announced_only_once_a_week(sent):
    """Edge detection alone would fire every second day on a price that
    wobbles across the target."""
    item_id = await _wanted("Wobbler", "40.00", target=35.0)
    await check_wishlist_deals()
    await _set_price(item_id, "34.00")
    await check_wishlist_deals()          # crossing: announced
    await _set_price(item_id, "36.00")
    await check_wishlist_deals()          # back above
    await _set_price(item_id, "34.00")

    again = await check_wishlist_deals()  # crossing again, within the week

    assert again["deals"] == []
    assert len(sent) == 1


@pytest.mark.anyio
async def test_an_entry_without_a_target_is_counted_not_announced():
    """A target of 0 means "no target set". Four of the most expensive cards on
    the real list are in that state, so they have to be visible somewhere —
    but there is no price they could have fallen below."""
    item_id = await _wanted("No Target", "40.00", target=0.0)
    await check_wishlist_deals()
    await _set_price(item_id, "1.00")

    result = await check_wishlist_deals()

    assert result["deals"] == []
    assert result["without_target"] == 1


@pytest.mark.anyio
async def test_a_card_without_any_price_is_reported_as_such():
    await _wanted("Unpriced", "", target=35.0)

    result = await check_wishlist_deals()

    assert result["without_price"] == 1 and result["checked"] == 0


@pytest.mark.anyio
async def test_an_acquired_entry_is_left_alone():
    db = await get_db()
    item_id = await _wanted("Bought Already", "40.00", target=35.0)
    await check_wishlist_deals()
    await db.execute("UPDATE wishlist SET status = 'acquired' WHERE id = ?", (item_id,))
    await db.commit()
    await _set_price(item_id, "10.00")

    assert (await check_wishlist_deals())["checked"] == 0


# ---------------------------------------------------------------------------
# What the list says about a card
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_a_game_changer_is_flagged_and_a_missing_target_is_visible(client):
    db = await get_db()
    gc = await insert_card(db, "Rhystic Study", price_eur="30.00", game_changer=1)
    await add_wishlist(db, gc)  # target defaults to 0
    await db.commit()

    async with client:
        items = (await client.get("/api/wishlist/")).json()
        no_target = (await client.get("/api/wishlist/?no_target_only=true")).json()

    assert items[0]["is_game_changer"] is True
    assert items[0]["has_target"] is False
    assert [i["card_name"] for i in no_target] == ["Rhystic Study"]


@pytest.mark.anyio
async def test_a_card_that_completes_an_infinite_says_which_deck(client):
    """The bridge Sprint 03 made possible: `missing_cards` finally names a
    card, so the wishlist can point at the deck it would finish."""
    db = await get_db()
    deck_id = await insert_deck(db, "Sharknado")
    card_id = await insert_card(db, "Breath of Fury", price_eur="5.00")
    await add_wishlist(db, card_id)
    await db.execute(
        """INSERT INTO deck_combos (deck_id, combo_id, name, cards_json, is_partial,
        missing_cards_json) VALUES (?,?,?,?,1,?)""",
        (deck_id, "c1", "Breath of Fury + Anger",
         '["Anger", "Breath of Fury"]', '["Breath of Fury"]'),
    )
    await db.commit()

    async with client:
        items = (await client.get("/api/wishlist/")).json()

    assert items[0]["completes_combo_in"] == ["Sharknado"]


@pytest.mark.anyio
async def test_a_similar_name_does_not_claim_the_combo(client):
    """"Anger" must not answer for "Anger of the Gods" — the match is on the
    quoted name inside the JSON array, not a substring of it."""
    db = await get_db()
    deck_id = await insert_deck(db, "Sharknado")
    card_id = await insert_card(db, "Anger", price_eur="1.00")
    await add_wishlist(db, card_id)
    await db.execute(
        """INSERT INTO deck_combos (deck_id, combo_id, name, cards_json, is_partial,
        missing_cards_json) VALUES (?,?,?,?,1,?)""",
        (deck_id, "c1", "Combo", '["X", "Anger of the Gods"]', '["Anger of the Gods"]'),
    )
    await db.commit()

    async with client:
        items = (await client.get("/api/wishlist/")).json()

    assert items[0]["completes_combo_in"] == []


@pytest.mark.anyio
async def test_a_game_changer_assigned_to_a_deck_shows_what_it_would_do(client):
    """Three game changers are allowed at bracket 3; a fourth is bracket 4.
    The comparison runs the deck through the rules twice, because the card only
    matters in the company of the ones already there."""
    db = await get_db()
    deck_id = await insert_deck(db, "Almost There")
    for name in ("Rhystic Study", "Demonic Tutor", "Cyclonic Rift"):
        card_id = await insert_card(db, name, game_changer=1)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,1)",
            (deck_id, card_id),
        )
    fourth = await insert_card(db, "Smothering Tithe", price_eur="30.00", game_changer=1)
    item_id = await add_wishlist(db, fourth)
    await db.execute("UPDATE wishlist SET deck_id = ? WHERE id = ?", (deck_id, item_id))
    await db.commit()

    async with client:
        items = (await client.get("/api/wishlist/")).json()

    impact = items[0]["bracket_impact"]
    assert impact["from"] == 3 and impact["to"] == 4
    assert impact["reasons"][0]["rule"] == "game_changers_over_limit"


@pytest.mark.anyio
async def test_the_route_runs_the_check_without_sending_anything(client, sent):
    item_id = await _wanted("Rhystic Study", "40.00", target=35.0)
    await check_wishlist_deals()
    await _set_price(item_id, "30.00")

    async with client:
        result = (await client.post("/api/wishlist/check-deals?notify=false")).json()

    assert len(result["deals"]) == 1
    assert sent == [], "notify=false must stay silent"
