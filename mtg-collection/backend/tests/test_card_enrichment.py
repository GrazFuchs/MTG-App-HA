"""Sprint 02: the card facts only Scryfall has, and keeping them.

Two questions decide whether the bracket work of Sprint 04 stands on anything:
does the enrichment write the fields, and do they survive the next Archidekt
sync. The second one is the interesting half — Archidekt is the source for
nearly every card row and used to overwrite `legalities` with the literal `{}`
on every run.
"""
import json

import httpx
import pytest
from _helpers import insert_card
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services import card_enrichment
from app.services.card_enrichment import backfill_scryfall_fields, pending_count


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    """Skip the 2 requests/second pacing; it is not what these tests check."""
    monkeypatch.setattr(card_enrichment, "_CHUNK_PACING", 0)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _fake_collection(cards_by_id: dict[str, dict]):
    """Answer POST /cards/collection from a dict, like Scryfall would.

    Ids the dict does not know are simply absent from the response — which is
    how Scryfall reports a printing it cannot resolve.
    """
    async def fake(identifiers):
        found = [cards_by_id[i["id"]] for i in identifiers if i["id"] in cards_by_id]
        missing = [i for i in identifiers if i["id"] not in cards_by_id]
        return found, missing

    return fake


def _patch_scryfall(monkeypatch, cards_by_id: dict[str, dict]):
    from app.clients import scryfall as scryfall_module

    monkeypatch.setattr(
        scryfall_module.scryfall, "get_cards_collection", _fake_collection(cards_by_id)
    )


async def _scryfall_id(db, card_id: int) -> str:
    cursor = await db.execute("SELECT scryfall_id FROM cards WHERE id = ?", (card_id,))
    return (await cursor.fetchone())[0]


async def _row(db, card_id: int):
    cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
    return await cursor.fetchone()


@pytest.mark.anyio
async def test_enrichment_writes_the_scryfall_only_facts(monkeypatch):
    db = await get_db()
    study = await insert_card(db, "Rhystic Study", set_code="6ed")
    ring = await insert_card(db, "Sol Ring", set_code="c21")
    study_sf = await _scryfall_id(db, study)
    ring_sf = await _scryfall_id(db, ring)

    _patch_scryfall(monkeypatch, {
        study_sf: {
            "id": study_sf,
            "game_changer": True,
            "reserved": False,
            "legalities": {"commander": "legal", "modern": "not_legal"},
            "keywords": [],
            "edhrec_rank": 44,
            "cardmarket_id": 12345,
            "type_line": "Enchantment",
            "oracle_text": "Whenever an opponent casts a spell...",
            "cmc": 3.0,
            "mana_cost": "{2}{U}",
        },
        ring_sf: {
            "id": ring_sf,
            "game_changer": False,
            "reserved": False,
            "legalities": {"commander": "legal"},
            "keywords": [],
            "edhrec_rank": 1,
            "cardmarket_id": 999,
            "type_line": "Artifact",
        },
    })

    result = await backfill_scryfall_fields()

    assert result == {
        "status": "completed",
        "checked": 2,
        "enriched": 2,
        "unresolved": 0,
        "game_changers": 1,
    }

    row = await _row(db, study)
    assert row["game_changer"] == 1
    assert row["reserved"] == 0
    assert json.loads(row["legalities"])["commander"] == "legal"
    assert row["edhrec_rank"] == 44
    assert row["cardmarket_id"] == 12345
    assert row["scryfall_enriched_at"] is not None

    assert (await _row(db, ring))["game_changer"] == 0


@pytest.mark.anyio
async def test_a_card_is_asked_once_and_then_left_alone(monkeypatch):
    """Without the stamp a nightly run would re-crawl the whole collection."""
    db = await get_db()
    card = await insert_card(db, "Sol Ring")
    sf = await _scryfall_id(db, card)
    _patch_scryfall(monkeypatch, {sf: {"id": sf, "legalities": {"commander": "legal"}}})

    assert (await backfill_scryfall_fields())["enriched"] == 1
    assert await pending_count() == 0

    second = await backfill_scryfall_fields()
    assert second["checked"] == 0 and second["enriched"] == 0


@pytest.mark.anyio
async def test_an_unresolved_printing_is_stamped_but_keeps_null_flags(monkeypatch):
    """`game_changer = 0` would be an invented answer, and that flag is about
    to decide a bracket. Not knowing has to stay visible as NULL."""
    db = await get_db()
    token = await insert_card(db, "Beast Token", set_code="tdmr")
    _patch_scryfall(monkeypatch, {})  # Scryfall resolves nothing

    result = await backfill_scryfall_fields()

    assert result["enriched"] == 0 and result["unresolved"] == 1
    row = await _row(db, token)
    assert row["scryfall_enriched_at"] is not None, "must not be asked about again"
    assert row["game_changer"] is None
    assert row["reserved"] is None


@pytest.mark.anyio
async def test_a_field_scryfall_does_not_answer_keeps_its_stored_value(monkeypatch):
    """A double-faced card carries no top-level `oracle_text` — the text lives
    in `card_faces`. Filling holes must not punch new ones."""
    db = await get_db()
    card = await insert_card(db, "Valakut Awakening // Valakut Stoneforge")
    await db.execute(
        """UPDATE cards SET oracle_text = 'stored text', cmc = 3, mana_cost = '{2}{R}',
        legalities = '{"commander": "legal"}', keywords = '["Landfall"]' WHERE id = ?""",
        (card,),
    )
    await db.commit()
    sf = await _scryfall_id(db, card)

    _patch_scryfall(monkeypatch, {sf: {
        "id": sf,
        "game_changer": False,
        "reserved": False,
        "type_line": "Instant // Land",
        # No oracle_text, no cmc, no mana_cost, no legalities, no keywords.
    }})

    await backfill_scryfall_fields()

    row = await _row(db, card)
    assert row["oracle_text"] == "stored text"
    assert row["cmc"] == 3
    assert row["mana_cost"] == "{2}{R}"
    assert json.loads(row["legalities"]) == {"commander": "legal"}
    assert json.loads(row["keywords"]) == ["Landfall"]
    assert row["type_line"] == "Instant // Land"
    # Asked and answered, so the flags are a real "no" this time.
    assert row["game_changer"] == 0


@pytest.mark.anyio
async def test_scryfall_owns_keywords_and_overwrites_the_archidekt_reading(monkeypatch):
    """Archidekt's keyword list is its own reading of a card and disagrees with
    Scryfall's; Scryfall is the authority, including when it says "none"."""
    db = await get_db()
    card = await insert_card(db, "Big Score")
    await db.execute(
        "UPDATE cards SET keywords = '[\"Treasure\"]' WHERE id = ?", (card,)
    )
    await db.commit()
    sf = await _scryfall_id(db, card)
    _patch_scryfall(monkeypatch, {sf: {"id": sf, "keywords": []}})

    await backfill_scryfall_fields()

    assert json.loads((await _row(db, card))["keywords"]) == []


@pytest.mark.anyio
async def test_a_429_stops_the_run_and_keeps_what_it_already_wrote(monkeypatch):
    """Scryfall asks for 2 requests/second on /collection. If it pushes back,
    the run stops where it is — the stamps written so far mean the next run
    continues rather than starts over."""
    db = await get_db()
    monkeypatch.setattr(card_enrichment, "_CHUNK", 1)
    first = await insert_card(db, "Sol Ring")
    second = await insert_card(db, "Rhystic Study")
    first_sf = await _scryfall_id(db, first)

    calls = {"n": 0}

    async def fake(identifiers):
        calls["n"] += 1
        if calls["n"] > 1:
            raise httpx.HTTPStatusError(
                "429",
                request=httpx.Request("POST", "https://api.scryfall.com/cards/collection"),
                response=httpx.Response(429),
            )
        return [{"id": first_sf, "legalities": {"commander": "legal"}}], []

    from app.clients import scryfall as scryfall_module
    monkeypatch.setattr(scryfall_module.scryfall, "get_cards_collection", fake)

    result = await backfill_scryfall_fields()

    assert result["status"] == "rate_limited"
    assert result["enriched"] == 1
    assert (await _row(db, first))["scryfall_enriched_at"] is not None
    assert (await _row(db, second))["scryfall_enriched_at"] is None
    assert await pending_count() == 1


@pytest.mark.anyio
async def test_force_reasks_about_a_card_that_is_not_due(monkeypatch):
    """WotC edits the Game Changers list; `force` is how the whole collection
    is re-read instead of the tenth that happens to be due."""
    db = await get_db()
    card = await insert_card(db, "Farewell")
    sf = await _scryfall_id(db, card)

    _patch_scryfall(monkeypatch, {sf: {"id": sf, "game_changer": False}})
    await backfill_scryfall_fields()
    assert (await _row(db, card))["game_changer"] == 0

    _patch_scryfall(monkeypatch, {sf: {"id": sf, "game_changer": True}})
    assert (await backfill_scryfall_fields())["checked"] == 0  # not due
    result = await backfill_scryfall_fields(force=True)

    assert result["checked"] == 1 and result["game_changers"] == 1
    assert (await _row(db, card))["game_changer"] == 1


@pytest.mark.anyio
async def test_the_endpoints_report_and_trigger(client, monkeypatch):
    """`/enrichment` has to keep "no" and "never asked" apart — that is the
    whole reason it reports both a count of flags and a count of stamps."""
    db = await get_db()
    study = await insert_card(db, "Rhystic Study")
    await insert_card(db, "Cardmarket Import", set_code="")
    study_sf = await _scryfall_id(db, study)
    _patch_scryfall(monkeypatch, {study_sf: {
        "id": study_sf, "game_changer": True, "reserved": False,
        "legalities": {"commander": "legal"}, "cardmarket_id": 12345,
    }})

    async with client:
        before = (await client.get("/api/cards/enrichment")).json()
        run = (await client.post("/api/cards/backfill-scryfall")).json()
        after = (await client.get("/api/cards/enrichment")).json()

    assert before["total_cards"] == 2 and before["asked"] == 0
    assert before["pending"] == 2 and before["game_changers"] == 0
    assert run["status"] == "completed" and run["game_changers"] == 1
    # Both were asked; only the one Scryfall resolved carries flags.
    assert after["asked"] == 2 and after["pending"] == 0
    assert after["game_changers"] == 1 and after["with_legalities"] == 1
    assert after["refresh_after_days"] == card_enrichment.REFRESH_AFTER_DAYS


@pytest.mark.anyio
async def test_an_archidekt_sync_does_not_undo_the_enrichment(monkeypatch):
    """The regression this sprint exists for.

    `upsert_card` is the single write path and the nightly sync drives it with
    Archidekt payloads, which carry `legalities: "{}"`, no rank on a thin entry,
    and nothing at all about Game Changers or the Reserved List. Letting those
    through meant the enrichment survived until 03:00.
    """
    db = await get_db()
    card = await insert_card(db, "Rhystic Study", set_code="6ed")
    sf = await _scryfall_id(db, card)
    _patch_scryfall(monkeypatch, {sf: {
        "id": sf,
        "game_changer": True,
        "reserved": True,
        "legalities": {"commander": "legal"},
        "keywords": ["Ward"],
        "edhrec_rank": 44,
        "oracle_text": "Whenever an opponent casts a spell...",
        "cardmarket_id": 12345,
    }})
    await backfill_scryfall_fields()

    from app.services.sync_service import upsert_card

    await upsert_card(db, {
        "scryfall_id": sf,
        "name": "Rhystic Study",
        "type_line": "Enchantment",
        "legalities": "{}",       # what parse_archidekt_card sends
        "oracle_text": "",        # a thin entry with no oracleCard
        "keywords": [],           # over half of the entries look like this
        "edhrec_rank": None,
        # game_changer / reserved / cardmarket_id: absent from the payload
    })
    await db.commit()

    row = await _row(db, card)
    assert row["game_changer"] == 1
    assert row["reserved"] == 1
    assert json.loads(row["legalities"]) == {"commander": "legal"}
    assert row["edhrec_rank"] == 44
    assert row["oracle_text"].startswith("Whenever an opponent")
    assert json.loads(row["keywords"]) == ["Ward"]
    assert row["cardmarket_id"] == 12345
