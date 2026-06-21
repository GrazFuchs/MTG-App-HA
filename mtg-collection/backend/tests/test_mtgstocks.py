"""MTGStocks integration tests with a faked client (no network).

Covers the tricky parts: per-printing matching via sets[], daily price snapshot,
collection-mover matching, buy/sell signal thresholds, and long-term history.
"""
import time

import pytest

from app.database import get_db
from app.clients import mtgstocks as mc
from app.services import mtgstocks_prices as M

pytestmark = pytest.mark.asyncio


def _print(pid, name, set_abbr, num, scryfall, ath, atl, market, *, sets=None):
    """Build a realistic /prints/{id} payload."""
    return {
        "id": pid, "name": name, "collector_number": num, "scryfallId": scryfall,
        "card_set": {"name": f"{set_abbr} set", "abbreviation": set_abbr},
        "all_time_high": {"avg": ath, "date": 1483833600000},
        "all_time_low": {"avg": atl, "date": 1511913600000},
        "tcgplayer": {"latestPrice": {"low": market - 2, "avg": market + 1, "high": market + 5,
                                      "market": market, "marketFoil": market * 2, "lowFoil": None}},
        "cardmarket": {"latestPrice": {"low": market - 3, "avg": market, "foil": None}},
        "sets": sets if sets is not None else [
            {"id": pid, "abbreviation": set_abbr, "collector_number": num,
             "set_name": f"{set_abbr} set", "latest_price": market, "latest_price_mkm": market}
        ],
    }


@pytest.fixture
def fake_mtgstocks(monkeypatch):
    """Patch the singleton client with deterministic in-memory responses."""
    # Ragavan: canonical print 100 (some other printing); owned printing is MH2 #138 -> 101.
    rag_detail_101 = _print(101, "Ragavan, Nimble Pilferer", "MH2", 138, "rag-sid",
                            ath=190.0, atl=23.71, market=185.0)
    rag_detail_100 = _print(100, "Ragavan, Nimble Pilferer", "MH1", 1, "rag-other",
                            ath=190.0, atl=23.71, market=50.0,
                            sets=[
                                {"id": 100, "abbreviation": "MH1", "collector_number": 1, "set_name": "MH1"},
                                {"id": 101, "abbreviation": "MH2", "collector_number": 138, "set_name": "MH2"},
                            ])
    sol_detail_200 = _print(200, "Sol Ring", "LEA", 263, "sol-sid",
                            ath=3000.0, atl=170.0, market=180.0)  # near ATL -> buy

    prints = {100: rag_detail_100, 101: rag_detail_101, 200: sol_detail_200}

    async def fake_search(name):
        n = name.lower()
        if n.startswith("ragavan"):
            return [{"id": 100, "type": "print", "name": "Ragavan, Nimble Pilferer", "slug": "100-ragavan"}]
        if n == "sol ring":
            return [{"id": 200, "type": "print", "name": "Sol Ring", "slug": "200-sol-ring"}]
        return []

    async def fake_get_print(pid):
        return prints.get(pid)

    async def fake_get_interests(kind, foil):
        if kind == "market" and not foil:
            return {"date": "2026-06-21", "interests": [
                {"foil": False, "percentage": 25.0, "interest_type": "week",
                 "present_price": 185.0, "past_price": 148.0,
                 "print": {"id": 101, "name": "Ragavan, Nimble Pilferer",
                           "set_code": "MH2", "set_name": "MH2 set", "number": 138}},
                {"foil": False, "percentage": 999.0, "interest_type": "week",
                 "present_price": 5, "past_price": 1,
                 "print": {"id": 77777, "name": "Some Card We Do Not Own",
                           "set_code": "XYZ", "set_name": "X", "number": 1}},
            ]}
        return {"date": "2026-06-21", "interests": []}

    async def fake_get_price_history(pid):
        now_ms = time.time() * 1000
        day = 86400000
        return {"market": [[now_ms - 3 * day, 170.0], [now_ms - 2 * day, 178.0],
                           [now_ms - day, 182.0], [now_ms, 185.0]]}

    monkeypatch.setattr(mc.mtgstocks, "search", fake_search)
    monkeypatch.setattr(mc.mtgstocks, "get_print", fake_get_print)
    monkeypatch.setattr(mc.mtgstocks, "get_interests", fake_get_interests)
    monkeypatch.setattr(mc.mtgstocks, "get_price_history", fake_get_price_history)


async def _seed():
    db = await get_db()

    async def add_card(sid, name, sc, num, tl="Artifact"):
        cur = await db.execute(
            "INSERT INTO cards (scryfall_id,name,set_code,set_name,collector_number,type_line) VALUES (?,?,?,?,?,?)",
            (sid, name, sc, sc, num, tl))
        return cur.lastrowid

    rag = await add_card("rag-sid", "Ragavan, Nimble Pilferer", "MH2", "138", "Legendary Creature")
    sol = await add_card("sol-sid", "Sol Ring", "LEA", "263")
    await db.execute("INSERT INTO collection (card_id, quantity) VALUES (?, 2)", (rag,))
    await db.execute("INSERT INTO wishlist (card_id, status) VALUES (?, 'wanted')", (sol,))
    await db.commit()
    return rag, sol


async def test_print_matching_picks_owned_printing(fake_mtgstocks):
    rag, sol = await _seed()
    res = await M.sync_mtgstocks_prints()
    assert res["resolved"] == 2 and res["failed"] == 0

    db = await get_db()
    row = await (await db.execute(
        "SELECT mtgstocks_print_id, all_time_high, all_time_low FROM mtgstocks_prints WHERE card_id=?", (rag,)
    )).fetchone()
    # Must map to the MH2 printing (101), not the canonical search hit (100).
    assert row["mtgstocks_print_id"] == 101
    assert row["all_time_high"] == 190.0 and row["all_time_low"] == 23.71


async def test_price_snapshot_written(fake_mtgstocks):
    await _seed()
    await M.sync_mtgstocks_prints()
    res = await M.sync_mtgstocks_prices()
    assert res["snapshots"] == 2
    db = await get_db()
    n = (await (await db.execute("SELECT COUNT(*) FROM mtgstocks_price_history")).fetchone())[0]
    assert n == 2


async def test_collection_movers_only_owned(fake_mtgstocks):
    await _seed()
    await M.sync_mtgstocks_prints()
    stored = await M.sync_mtgstocks_interests()
    assert stored["stored"] == 1  # the unowned card is filtered out
    movers = await M.get_collection_movers()
    assert len(movers) == 1
    assert movers[0]["card_name"] == "Ragavan, Nimble Pilferer"
    assert movers[0]["direction"] == "up" and movers[0]["percentage"] == 25.0


async def test_buy_and_sell_signals(fake_mtgstocks):
    await _seed()
    await M.sync_mtgstocks_prints()
    await M.sync_mtgstocks_prices()
    sig = await M.get_buy_sell_signals()
    # Sol Ring (wishlist) is near its all-time low -> buy.
    assert any(b["card_name"] == "Sol Ring" for b in sig["buy"])
    # Ragavan (owned, 2 unused copies) is near its all-time high -> sell.
    sells = [s for s in sig["sell"] if s["card_name"] == "Ragavan, Nimble Pilferer"]
    assert sells and sells[0]["unused_copies"] == 2


async def test_long_term_history(fake_mtgstocks):
    rag, _ = await _seed()
    await M.sync_mtgstocks_prints()
    h = await M.get_long_term_history(rag, days=30)
    assert h["currency"] == "USD"
    assert len(h["series"]) == 4
    assert h["all_time_high"] == 190.0 and h["all_time_low"] == 23.71
