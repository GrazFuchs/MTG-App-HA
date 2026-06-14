"""Sprint 26: MCP batch tools — get_cards / find_cards_in_collection /
bulk_add_to_wishlist / analyze_deck / get_acquisition_history."""
import json

from _helpers import add_collection, insert_card, insert_deck
from app import mcp_server
from app.clients import scryfall as scry_mod
from app.database import get_db


async def test_find_cards_in_collection_batch():
    db = await get_db()
    sol = await insert_card(db, "Sol Ring", type_line="Artifact")
    await add_collection(db, sol, quantity=2)

    res = json.loads(await mcp_server.find_cards_in_collection(["Sol Ring", "Nope Card"]))
    by = {c["card_name"]: c for c in res["cards"]}
    assert by["Sol Ring"]["found"] is True
    assert by["Sol Ring"]["total_owned"] == 2
    assert by["Nope Card"]["found"] is False


async def test_get_cards_local_and_remote(monkeypatch):
    db = await get_db()
    await insert_card(db, "Local Card", type_line="Instant", color_identity=["R"], price_eur="1.50")

    async def fake_collection(identifiers):
        names = {i.get("name") for i in identifiers}
        cards = []
        if "Remote Card" in names:
            cards.append({"name": "Remote Card", "type_line": "Creature", "cmc": 2,
                          "colors": ["U"], "color_identity": ["U"],
                          "prices": {"eur": "0.25", "usd": "0.30"}})
        return cards, [{"name": "Ghost Card"}]

    monkeypatch.setattr(scry_mod.scryfall, "get_cards_collection", fake_collection)

    res = json.loads(await mcp_server.get_cards(["Local Card", "Remote Card", "Ghost Card"]))
    names = {c["name"] for c in res["cards"]}
    assert "Local Card" in names
    assert "Remote Card" in names
    assert res["not_found"] == ["Ghost Card"]
    # Local hit must not trigger a Scryfall fetch for that name.
    assert next(c for c in res["cards"] if c["name"] == "Local Card")["source"] == "local"


async def test_bulk_add_to_wishlist_local():
    db = await get_db()
    await insert_card(db, "Wishlist Me", type_line="Instant", color_identity=["G"])

    res = json.loads(await mcp_server.bulk_add_to_wishlist(["Wishlist Me"], priority=4, tags="batch"))
    assert res["added_count"] == 1
    cur = await db.execute("SELECT priority, tags FROM wishlist")
    row = await cur.fetchone()
    assert row["priority"] == 4 and row["tags"] == "batch"


async def test_analyze_deck_structure():
    db = await get_db()
    deck = await insert_deck(db, "Curve Deck")
    bear = await insert_card(db, "Grizzly Bears", type_line="Creature — Bear")
    island = await insert_card(db, "Island", type_line="Basic Land — Island")
    for cid, cat in ((bear, "Creature"), (island, "Land")):
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, category) VALUES (?,?,?,?)",
            (deck, cid, 1, cat),
        )
    await db.commit()

    res = json.loads(await mcp_server.analyze_deck(deck))
    assert res["lands"] == 1
    assert res["nonland_cards"] == 1
    assert res["type_breakdown"].get("Creature") == 1
    assert "mana_curve" in res and "color_pips" in res


async def test_acquisition_history_empty():
    res = json.loads(await mcp_server.get_acquisition_history())
    assert res["count"] == 0
    assert res["events"] == []
