"""Sprint 29: inbox / sell metrics behind the HA sensors."""
import pytest
from _helpers import (
    add_acquisition_event,
    add_collection,
    add_listing,
    insert_card,
    insert_deck,
)
from app.database import get_db
from app.services import ha_metrics


async def _add_deck_card(db, deck_id: int, card_id: int, quantity: int = 1):
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,?)",
        (deck_id, card_id, quantity),
    )
    await db.commit()


# --- inbox ------------------------------------------------------------------


@pytest.mark.anyio
async def test_inbox_metrics_empty():
    db = await get_db()
    m = await ha_metrics.inbox_metrics(db)

    assert m.states["inbox_pending"] == 0
    assert m.states["inbox_pending_value_eur"] == 0
    assert m.states["inbox_oldest_age_days"] == 0
    assert m.states["inbox_has_pending"] == "OFF"
    assert m.attributes["inbox_pending"]["items"] == []


@pytest.mark.anyio
async def test_inbox_counts_value_and_binary_state():
    db = await get_db()
    sol = await insert_card(db, "Sol Ring", price_eur="1.50", price_eur_foil="5.00")
    mox = await insert_card(db, "Mox Diamond", price_eur="400.00")

    await add_acquisition_event(db, sol, qty_delta=2)
    await add_acquisition_event(db, mox, qty_delta=1)

    m = await ha_metrics.inbox_metrics(db)

    assert m.states["inbox_pending"] == 2
    assert m.states["inbox_pending_value_eur"] == 403.0  # 2 × 1.50 + 400
    assert m.states["inbox_has_pending"] == "ON"
    assert len(m.attributes["inbox_pending"]["items"]) == 2


@pytest.mark.anyio
async def test_inbox_uses_foil_price_for_foil_events():
    db = await get_db()
    sol = await insert_card(db, "Sol Ring", price_eur="1.50", price_eur_foil="5.00")
    await add_acquisition_event(db, sol, qty_delta=1, is_foil=1)

    m = await ha_metrics.inbox_metrics(db)
    assert m.states["inbox_pending_value_eur"] == 5.0


@pytest.mark.anyio
async def test_inbox_excludes_basic_lands_and_decided_events():
    db = await get_db()
    island = await insert_card(db, "Island", type_line="Basic Land — Island")
    snow = await insert_card(db, "Snow-Covered Forest", type_line="Basic Snow Land")
    sol = await insert_card(db, "Sol Ring")

    await add_acquisition_event(db, island)
    await add_acquisition_event(db, snow)
    await add_acquisition_event(db, sol)
    await add_acquisition_event(db, sol, triage_state="keep")

    m = await ha_metrics.inbox_metrics(db)
    assert m.states["inbox_pending"] == 1


@pytest.mark.anyio
async def test_inbox_suggestion_split():
    """A second copy of an owned card is a sell candidate; a new card is a keep."""
    db = await get_db()
    owned = await insert_card(db, "Lightning Bolt", set_code="lea", price_eur="10.00")
    await add_collection(db, owned, quantity=1)
    dupe = await insert_card(db, "Lightning Bolt", set_code="m11", price_eur="2.00")
    fresh = await insert_card(db, "Counterspell", price_eur="1.00")

    await add_acquisition_event(db, dupe, qty_delta=1)
    await add_acquisition_event(db, fresh, qty_delta=1)

    m = await ha_metrics.inbox_metrics(db)

    assert m.states["inbox_pending"] == 2
    assert m.states["inbox_needs_sell"] == 1
    assert m.states["inbox_needs_keep"] == 1

    actions = {i["card_name"]: i["suggestion"] for i in m.attributes["inbox_pending"]["items"]}
    assert actions["Lightning Bolt"] == "sold_new"
    assert actions["Counterspell"] == "keep"


@pytest.mark.anyio
async def test_inbox_attribute_list_is_capped(monkeypatch):
    db = await get_db()
    for i in range(ha_metrics.TOP_N + 5):
        card = await insert_card(db, f"Card {i}")
        await add_acquisition_event(db, card)

    m = await ha_metrics.inbox_metrics(db)

    assert m.states["inbox_pending"] == ha_metrics.TOP_N + 5
    assert len(m.attributes["inbox_pending"]["items"]) == ha_metrics.TOP_N


@pytest.mark.anyio
async def test_inbox_suggestion_scan_is_bounded(monkeypatch):
    """The count stays exact even when the suggestion scan is truncated."""
    monkeypatch.setattr(ha_metrics, "MAX_SUGGESTION_SCAN", 2)
    db = await get_db()
    for i in range(5):
        card = await insert_card(db, f"Card {i}")
        await add_acquisition_event(db, card)

    m = await ha_metrics.inbox_metrics(db)

    assert m.states["inbox_pending"] == 5
    assert m.attributes["inbox_pending"]["suggestions_scanned"] == 2
    assert m.attributes["inbox_pending"]["suggestions_truncated"] is True
    assert m.states["inbox_needs_keep"] + m.states["inbox_needs_sell"] == 2


@pytest.mark.anyio
async def test_inbox_decided_30d_by_state():
    db = await get_db()
    card = await insert_card(db, "Sol Ring")
    for state in ("keep", "keep", "sold_new"):
        event_id = await add_acquisition_event(db, card, triage_state=state)
        await db.execute(
            "UPDATE acquisition_events SET triage_decision_at = datetime('now', '-1 day')"
            " WHERE id = ?",
            (event_id,),
        )
    # Older than the window → must not count
    old = await add_acquisition_event(db, card, triage_state="keep")
    await db.execute(
        "UPDATE acquisition_events SET triage_decision_at = datetime('now', '-60 days')"
        " WHERE id = ?",
        (old,),
    )
    await db.commit()

    m = await ha_metrics.inbox_metrics(db)

    assert m.states["inbox_decided_30d"] == 3
    assert m.attributes["inbox_decided_30d"]["by_state"] == {"keep": 2, "sold_new": 1}


# --- sell -------------------------------------------------------------------


@pytest.mark.anyio
async def test_sell_metrics_empty():
    db = await get_db()
    m = await ha_metrics.sell_metrics(db)

    assert m.states["sell_candidates"] == 0
    assert m.states["sell_potential_eur"] == 0
    assert m.states["duplicates_surplus_cards"] == 0
    assert m.states["unlisted_value_eur"] == 0


@pytest.mark.anyio
async def test_duplicates_surplus_counts_unused_copies():
    db = await get_db()
    sol = await insert_card(db, "Sol Ring", price_eur="2.00")
    await add_collection(db, sol, quantity=4)
    deck = await insert_deck(db)
    await _add_deck_card(db, deck, sol, quantity=1)

    m = await ha_metrics.sell_metrics(db)

    assert m.states["duplicates_surplus_cards"] == 4
    assert m.states["duplicates_surplus_value_eur"] == 8.0
    assert m.states["unlisted_value_eur"] == 8.0
    assert m.attributes["unlisted_value_eur"]["items"][0]["card_name"] == "Sol Ring"


@pytest.mark.anyio
async def test_listed_copies_drop_out_of_the_unlisted_backlog():
    db = await get_db()
    sol = await insert_card(db, "Sol Ring", price_eur="2.00")
    await add_collection(db, sol, quantity=4)
    await add_listing(db, "Sol Ring", quantity=4)

    m = await ha_metrics.sell_metrics(db)

    assert m.states["unlisted_value_eur"] == 0
    assert m.attributes["unlisted_value_eur"]["items"] == []


@pytest.mark.anyio
async def test_cards_in_no_deck_are_sell_candidates():
    """Regression: a bare `in_decks` in HAVING bound to the NULL join column,
    which dropped every card that is not in any deck — the best candidates."""
    from app.services.sell_advisor import suggest_sells

    db = await get_db()
    card = await insert_card(db, "Rhystic Study", price_eur="30.00")
    await add_collection(db, card, quantity=2)
    await db.execute(
        "INSERT INTO cardmarket_products (cm_product_id, card_name, card_id) VALUES (?,?,?)",
        (1, "Rhystic Study", card),
    )
    await db.execute(
        "INSERT INTO cardmarket_price_history (cm_product_id, date, trend, avg30)"
        " VALUES (?, date('now'), ?, ?)",
        (1, 30.0, 30.0),
    )
    await db.commit()

    suggestions = await suggest_sells()

    assert [s["card_name"] for s in suggestions] == ["Rhystic Study"]
    assert suggestions[0]["unused_copies"] == 2
    assert "nicht in Decks" in suggestions[0]["reason"]


@pytest.mark.anyio
async def test_sell_candidates_offer_every_unused_copy():
    """With no target amount the advisor must not stop at the default €50."""
    db = await get_db()
    card = await insert_card(db, "Dockside Extortionist", price_eur="60.00")
    await add_collection(db, card, quantity=3)
    await db.execute(
        "INSERT INTO cardmarket_products (cm_product_id, card_name, card_id) VALUES (?,?,?)",
        (1, "Dockside Extortionist", card),
    )
    await db.execute(
        "INSERT INTO cardmarket_price_history (cm_product_id, date, trend, avg30)"
        " VALUES (?, date('now'), ?, ?)",
        (1, 60.0, 50.0),
    )
    await db.commit()

    m = await ha_metrics.sell_metrics(db)

    assert m.states["sell_candidates"] == 1
    assert m.states["sell_potential_eur"] == 180.0  # all 3 copies, not just one
    top = m.attributes["sell_candidates"]["items"][0]
    assert top["copies_to_sell"] == 3
