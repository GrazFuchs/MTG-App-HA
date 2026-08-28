"""Sprint 18: Duplicates basic-land exclusion + color filter behaviour.

Sprint 09 adds the surplus tests at the bottom: what counts as a spare copy,
and that the tool and the page agree about it.
"""
import json

import pytest
from _helpers import add_collection, add_listing, insert_card, insert_deck, names
from app.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


async def _seed():
    db = await get_db()
    # Basic lands that must NEVER appear in duplicates:
    plains = await insert_card(db, "Plains", type_line="Basic Land — Plains")
    snow = await insert_card(db, "Snow-Covered Island", type_line="Basic Snow Land — Island")
    # Forest with an EMPTY type_line (e.g. imported via Cardmarket, not enriched):
    forest = await insert_card(db, "Forest", type_line="")
    wastes = await insert_card(db, "Wastes", type_line="Basic Land")
    # Real duplicates:
    mono = await insert_card(db, "Mono White Card", type_line="Creature", color_identity=["W"])
    azorius = await insert_card(db, "Azorius Card", type_line="Creature", color_identity=["U", "W"])
    for cid in (plains, snow, forest, wastes, mono, azorius):
        await add_collection(db, cid, quantity=5)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _get(client, query=""):
    resp = await client.get(f"/api/collection/duplicates{query}")
    assert resp.status_code == 200, resp.text
    return names(resp.json()["items"])


async def test_basic_lands_excluded(client):
    await _seed()
    async with client:
        found = await _get(client)
    assert "Plains" not in found
    assert "Snow-Covered Island" not in found
    assert "Forest" not in found  # empty type_line still excluded by name
    assert "Wastes" not in found
    assert {"Mono White Card", "Azorius Card"} <= found


async def test_color_includes_white(client):
    await _seed()
    async with client:
        found = await _get(client, "?color=W")
    # "Includes white" → both the mono and the multicolor card.
    assert "Mono White Card" in found
    assert "Azorius Card" in found


async def test_monocolor_excludes_multicolor(client):
    await _seed()
    async with client:
        found = await _get(client, "?color=MONO")
    assert "Mono White Card" in found
    assert "Azorius Card" not in found


async def test_multicolor_filter(client):
    await _seed()
    async with client:
        found = await _get(client, "?color=M")
    assert "Azorius Card" in found
    assert "Mono White Card" not in found


# ---------------------------------------------------------------------------
# Surplus (W5)
# ---------------------------------------------------------------------------

async def _duplicates(client, query=""):
    resp = await client.get(f"/api/collection/duplicates{query}")
    assert resp.status_code == 200, resp.text
    return {i["card_name"]: i for i in resp.json()["items"]}


async def test_copies_inside_a_deck_are_not_surplus(client):
    """The bug this replaces: `extras` was the printing's own copy count, so a
    playset entirely inside a deck counted as four spare cards — and the sell
    dialog would offer copies that are in play."""
    db = await get_db()
    card = await insert_card(db, "Played Card", type_line="Creature")
    await add_collection(db, card, quantity=4)
    deck = await insert_deck(db, "Uses Them")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,3)", (deck, card)
    )
    await db.commit()

    async with client:
        found = await _duplicates(client)

    assert found["Played Card"]["extras_after_listings"] == 1


async def test_a_card_in_two_printings_is_not_counted_twice(client):
    """The error the obvious fix would have introduced. Deck usage is counted
    per card, the rows are per printing — so handing every row the card's full
    surplus would double it in any sum."""
    db = await get_db()
    a = await insert_card(db, "Two Printings", type_line="Creature", set_code="aaa")
    b = await insert_card(db, "Two Printings", type_line="Creature", set_code="bbb")
    await add_collection(db, a, quantity=3)
    await add_collection(db, b, quantity=3)
    deck = await insert_deck(db, "Uses One")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,2)", (deck, a)
    )
    await db.commit()

    async with client:
        items = (await client.get("/api/collection/duplicates")).json()["items"]

    rows = [i for i in items if i["card_name"] == "Two Printings"]
    assert len(rows) == 2, "one row per printing"
    # Owned 6, two in decks -> four spare, however they are spread over the
    # two printings.
    assert sum(r["extras_after_listings"] for r in rows) == 4


async def test_a_listing_only_counts_against_its_own_printing(client):
    """Matching listings by name let a listing of one printing cancel out the
    spare copies of another — the same name-versus-printing confusion the
    price join was fixed for in 0.33.0."""
    db = await get_db()
    a = await insert_card(db, "Listed Elsewhere", type_line="Creature", set_code="aaa")
    b = await insert_card(db, "Listed Elsewhere", type_line="Creature", set_code="bbb")
    await add_collection(db, a, quantity=2)
    await add_collection(db, b, quantity=2)
    await add_listing(db, "Listed Elsewhere", set_code="aaa", quantity=2, card_id=a)
    await db.commit()

    async with client:
        items = (await client.get("/api/collection/duplicates")).json()["items"]

    by_set = {i["set_code"]: i for i in items if i["card_name"] == "Listed Elsewhere"}
    # A fully listed printing drops out of the view entirely (the page hides
    # rows with nothing left to sell), so its absence *is* the assertion.
    assert "aaa" not in by_set, "its own listing cancels it"
    assert by_set["bbb"]["extras_after_listings"] == 2, "the other printing is untouched"


@pytest.mark.anyio
async def test_the_mcp_tool_agrees_with_the_page():
    """Two copies of the same query live in the tree — `queries.py` for the UI
    and `mcp_server.py` for the tool. They share the tricky half through
    `duplicates_extras_sql`; this is the guard that they stay in step."""
    from app.mcp_server import get_duplicates
    from app.services.queries import DUPLICATES_CTE, DUPLICATES_FINAL_CTE, basic_land_exclusion_sql

    db = await get_db()
    card = await insert_card(db, "Shared Card", type_line="Creature")
    await add_collection(db, card, quantity=5)
    deck = await insert_deck(db, "Uses Two")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?,?,2)", (deck, card)
    )
    await db.commit()

    cte = DUPLICATES_CTE.replace("{where}", basic_land_exclusion_sql("c"))
    cursor = await db.execute(
        f"{cte}, {DUPLICATES_FINAL_CTE} SELECT SUM(extras_after_listings) FROM final"
    )
    page_total = (await cursor.fetchone())[0]

    tool = json.loads(await get_duplicates())
    tool_total = sum(r["extras_after_listings"] for r in tool["items"])

    assert page_total == tool_total == 3
