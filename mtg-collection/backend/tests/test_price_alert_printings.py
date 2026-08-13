"""Price alerts must describe exactly one printing.

The bug these cover: Cardmarket products were matched to cards by name alone,
so all 31 "Terror" products — €0.08 bulk reprint through €1177 original —
collapsed onto one arbitrary `cards` row. A spike in the expensive printing was
then announced with the owned count of the cheap one beside it, and the whole
collection produced ~1987 alerts a morning.
"""
import pytest
from _helpers import add_collection, insert_card, insert_deck
from app.database import get_db
from app.services import ha_metrics
from app.services.cardmarket_prices import get_price_alerts


async def _price(db, cm_product_id: int, *, trend: float, avg30: float) -> None:
    await db.execute(
        "INSERT INTO cardmarket_price_history (cm_product_id, date, trend, avg30)"
        " VALUES (?, date('now'), ?, ?)",
        (cm_product_id, trend, avg30),
    )
    await db.commit()


async def _product(
    db, cm_product_id: int, name: str, card_id: int | None, set_name: str = ""
) -> None:
    await db.execute(
        "INSERT INTO cardmarket_products (cm_product_id, card_name, expansion_name, card_id)"
        " VALUES (?,?,?,?)",
        (cm_product_id, name, set_name, card_id),
    )
    await db.commit()


@pytest.mark.anyio
async def test_sync_links_each_product_to_its_own_printing(monkeypatch):
    """Root cause: the sync linked a product by name via `LIMIT 1`, so the
    €1177 Alpha product was tied to the €0.08 reprint that happened to be in
    the collection. Prices are now fetched per `cards.cardmarket_id`."""
    from app.services import cardmarket_prices

    db = await get_db()
    alpha = await insert_card(
        db, "Terror", oracle_id="terror", set_code="lea", set_name="Limited Edition Alpha",
        cardmarket_id=16762,
    )
    bulk = await insert_card(
        db, "Terror", oracle_id="terror", set_code="10e", set_name="Tenth Edition",
        cardmarket_id=79,
    )
    await add_collection(db, bulk, quantity=3)

    # The broken state a previous sync left behind: Alpha's product pointing at
    # the reprint we own.
    await _product(db, 16762, "Terror", bulk, "Limited Edition Alpha")

    async def fake_guide():
        return [
            {"idProduct": 16762, "idCategory": 1, "trend": 1177.41, "avg30": 258.23},
            {"idProduct": 79, "idCategory": 1, "trend": 0.08, "avg30": 0.08},
        ]

    monkeypatch.setattr(cardmarket_prices, "_fetch_price_guide", fake_guide)
    monkeypatch.setattr(
        cardmarket_prices, "backfill_cardmarket_ids", lambda *a, **k: _noop_backfill()
    )

    result = await cardmarket_prices.sync_cardmarket_prices()

    # Only the printing actually held is priced, and the stale mislink is gone.
    assert result["products_matched"] == 1
    cursor = await db.execute(
        "SELECT cm_product_id, card_id FROM cardmarket_products ORDER BY cm_product_id"
    )
    links = {row[0]: row[1] for row in await cursor.fetchall()}
    assert links[79] == bulk  # the reprint we own, linked to itself
    assert links[16762] is None  # Alpha is unowned, so it claims no card

    # And the €1177 spike is not announced against the €0.08 copies.
    assert await get_price_alerts() == []

    # The Alpha printing exists, but nothing in the collection points at it.
    cursor = await db.execute("SELECT COUNT(*) FROM collection WHERE card_id = ?", (alpha,))
    assert (await cursor.fetchone())[0] == 0


async def _noop_backfill():
    return {"status": "completed", "checked": 0, "linked": 0, "unavailable": 0}


@pytest.mark.anyio
async def test_price_guide_ignores_non_single_categories(monkeypatch):
    """`price_guide_1.json` is the Magic guide but carries 12 product
    categories; only category 1 ("Magic Single") is a card."""
    from app.services import cardmarket_prices

    db = await get_db()
    card = await insert_card(db, "Sol Ring", cardmarket_id=1000)
    await add_collection(db, card, quantity=1)

    async def fake_get(url):
        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "priceGuides": [
                        {"idProduct": 1000, "idCategory": 1, "trend": 2.0, "avg30": 1.5},
                        {"idProduct": 1000, "idCategory": 8, "trend": 999.0, "avg30": 1.0},
                    ]
                }

        return Resp()

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            return await fake_get(url)

    monkeypatch.setattr(cardmarket_prices.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        cardmarket_prices, "backfill_cardmarket_ids", lambda *a, **k: _noop_backfill()
    )

    await cardmarket_prices.sync_cardmarket_prices()

    cursor = await db.execute(
        "SELECT trend FROM cardmarket_price_history WHERE cm_product_id = 1000"
    )
    rows = await cursor.fetchall()
    assert [r[0] for r in rows] == [2.0]  # the sealed-product row is dropped


@pytest.mark.anyio
async def test_alert_names_the_printing_it_counted():
    """A spike in a printing we hold is reported, with that printing's set."""
    db = await get_db()
    alpha = await insert_card(
        db, "Terror", oracle_id="terror", set_code="lea", set_name="Limited Edition Alpha",
        cardmarket_id=16762,
    )
    await insert_card(
        db, "Terror", oracle_id="terror", set_code="10e", set_name="Tenth Edition",
        cardmarket_id=79,
    )
    await add_collection(db, alpha, quantity=2)

    await _product(db, 16762, "Terror", alpha, "Limited Edition Alpha")
    await _price(db, 16762, trend=1177.41, avg30=258.23)

    alerts = await get_price_alerts()

    assert len(alerts) == 1
    assert alerts[0]["card_name"] == "Terror"
    assert alerts[0]["set_name"] == "Limited Edition Alpha"
    assert alerts[0]["set_code"] == "lea"
    assert alerts[0]["total_owned"] == 2
    assert alerts[0]["unused_copies"] == 2
    assert "Limited Edition Alpha" in alerts[0]["suggestion"]


@pytest.mark.anyio
async def test_unlinked_product_raises_no_alert():
    """Rows left unlinked by the migration must not resurrect name matching."""
    db = await get_db()
    bulk = await insert_card(db, "Terror", set_code="10e", set_name="Tenth Edition")
    await add_collection(db, bulk, quantity=3)

    await _product(db, 16762, "Terror", None, "Limited Edition Alpha")
    await _price(db, 16762, trend=1177.41, avg30=258.23)

    assert await get_price_alerts() == []


@pytest.mark.anyio
async def test_deck_usage_counts_every_printing_of_the_card():
    """Any printing fills a deck slot, so a copy played from another edition
    must not be offered for sale."""
    db = await get_db()
    owned = await insert_card(
        db, "Lightning Bolt", oracle_id="bolt", set_code="lea", set_name="Alpha",
        cardmarket_id=500,
    )
    played = await insert_card(
        db, "Lightning Bolt", oracle_id="bolt", set_code="m11", set_name="Magic 2011",
        cardmarket_id=501,
    )
    await add_collection(db, owned, quantity=3)

    deck = await insert_deck(db, "Burn")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,?)",
        (deck, played, 1),
    )
    await db.commit()

    await _product(db, 500, "Lightning Bolt", owned, "Alpha")
    await _price(db, 500, trend=885.0, avg30=336.0)

    alerts = await get_price_alerts()

    assert len(alerts) == 1
    assert alerts[0]["in_decks"] == 1
    assert alerts[0]["unused_copies"] == 2


@pytest.mark.anyio
async def test_backfill_records_printings_without_a_cardmarket_product(monkeypatch):
    """A card Scryfall has no Cardmarket id for is marked 0, not left NULL —
    otherwise every nightly run asks about it again forever."""
    from app.clients import scryfall as scryfall_module
    from app.services import cardmarket_prices

    db = await get_db()
    priced = await insert_card(db, "Terror", set_code="dmr")
    token = await insert_card(db, "Beast Token", set_code="tdmr")

    cursor = await db.execute("SELECT scryfall_id FROM cards WHERE id = ?", (priced,))
    priced_sf = (await cursor.fetchone())[0]
    cursor = await db.execute("SELECT scryfall_id FROM cards WHERE id = ?", (token,))
    token_sf = (await cursor.fetchone())[0]

    async def fake_collection(identifiers):
        return (
            [
                {"id": priced_sf, "cardmarket_id": 688537},
                {"id": token_sf},  # Scryfall knows it, Cardmarket does not sell it
            ],
            [],
        )

    monkeypatch.setattr(
        scryfall_module.scryfall, "get_cards_collection", fake_collection
    )

    result = await cardmarket_prices.backfill_cardmarket_ids()

    assert result == {"status": "completed", "checked": 2, "linked": 1, "unavailable": 1}

    cursor = await db.execute("SELECT id, cardmarket_id FROM cards ORDER BY id")
    ids = dict(await cursor.fetchall())
    assert ids[priced] == 688537
    assert ids[token] == 0

    # Second run has nothing left to ask about.
    assert (await cardmarket_prices.backfill_cardmarket_ids())["checked"] == 0


@pytest.mark.anyio
async def test_sell_potential_is_not_multiplied_by_product_rows():
    """Regression: joining cardmarket_products fanned each collection row out
    once per matching product, so three copies were valued as nine."""
    db = await get_db()
    card = await insert_card(db, "Sol Ring", set_name="Commander", cardmarket_id=1000)
    await add_collection(db, card, quantity=3)

    for pid in (1000, 1001, 1002):
        await _product(db, pid, "Sol Ring", card, "Commander")
        await _price(db, pid, trend=10.0, avg30=10.0)

    suggestions = await ha_metrics._sell_candidates()
    count, potential, _top = suggestions

    assert count == 1
    assert potential == 30.0  # 3 copies × €10, not 9 × €10
