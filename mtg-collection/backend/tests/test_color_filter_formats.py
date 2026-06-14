"""Sprint 24 (item 8): colour filters must work regardless of how
`cards.color_identity` is stored — JSON (["R"]), CSV ("R,U"), or bare ("R").

Regression for the bug where single-colour filters used `LIKE '%"R"%'` and so
silently dropped every non-JSON row (multicolour still matched via the comma
test), making Red/Blue/etc. return no hits in the Inbox and Duplicates tabs.
"""
import pytest
from _helpers import add_acquisition_event, add_collection
from app.database import get_db
from httpx import ASGITransport, AsyncClient

from app.main import app

_n = {"i": 1000}


async def _raw_card(db, name, color_identity_raw, type_line="Instant"):
    """Insert a card with RAW (not JSON-encoded) color_identity AND colors.

    Both columns get the non-JSON value on purpose: response builders parse
    `colors` too, so a non-JSON `colors` must not crash the endpoint either.
    """
    _n["i"] += 1
    i = _n["i"]
    cur = await db.execute(
        """INSERT INTO cards (scryfall_id, oracle_id, name, type_line,
            color_identity, colors, set_code, set_name, collector_number, rarity,
            price_eur, price_eur_foil)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"raw-{i}", f"or-{i}", name, type_line, color_identity_raw,
         color_identity_raw, "tst", "Test Set", str(i), "common", "1.00", "2.00"),
    )
    await db.commit()
    return cur.lastrowid


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_inbox_single_color_matches_non_json_formats(client):
    db = await get_db()
    json_red = await _raw_card(db, "Bolt JSON", '["R"]')
    csv_red = await _raw_card(db, "Bolt CSV", "R")
    azorius = await _raw_card(db, "Azorius CSV", "U,W")
    for cid in (json_red, csv_red, azorius):
        await add_acquisition_event(db, cid)

    async with client:
        resp = await client.get("/api/acquisitions/pending?color=R")
    assert resp.status_code == 200, resp.text
    found = {i["card"]["name"] for i in resp.json()["items"]}
    assert "Bolt JSON" in found
    assert "Bolt CSV" in found          # previously missing (the bug)
    assert "Azorius CSV" not in found   # mono filter excludes multicolour


async def test_duplicates_single_color_includes_non_json_formats(client):
    db = await get_db()
    csv_red = await _raw_card(db, "Dup CSV Red", "R")
    azorius = await _raw_card(db, "Dup Azorius", '["U","W"]')
    await add_collection(db, csv_red, quantity=3)
    await add_collection(db, azorius, quantity=3)

    async with client:
        resp = await client.get("/api/collection/duplicates?color=R")
    assert resp.status_code == 200, resp.text
    names = {i["card_name"] for i in resp.json()["items"]}
    assert "Dup CSV Red" in names       # previously missing (the bug)
    assert "Dup Azorius" not in names   # does not include red


async def test_inbox_lands_filter(client):
    db = await get_db()
    from _helpers import insert_card
    land = await insert_card(db, "Command Tower", type_line="Land",
                             color_identity=[], set_code="cmd")
    bolt = await _raw_card(db, "Bolt LF", "R")
    for cid in (land, bolt):
        await add_acquisition_event(db, cid)
    async with client:
        resp = await client.get("/api/acquisitions/pending?color=L")
    assert resp.status_code == 200, resp.text
    found = {i["card"]["name"] for i in resp.json()["items"]}
    assert found == {"Command Tower"}  # non-basic land only; Bolt excluded


async def test_duplicates_multi_and_colorless_formats(client):
    db = await get_db()
    azorius_csv = await _raw_card(db, "Multi CSV", "U,W")
    colorless = await _raw_card(db, "Colorless Card", "[]", type_line="Artifact")
    await add_collection(db, azorius_csv, quantity=2)
    await add_collection(db, colorless, quantity=2)

    async with client:
        multi = await client.get("/api/collection/duplicates?color=M")
        cless = await client.get("/api/collection/duplicates?color=C")
    assert "Multi CSV" in {i["card_name"] for i in multi.json()["items"]}
    assert "Colorless Card" in {i["card_name"] for i in cless.json()["items"]}
