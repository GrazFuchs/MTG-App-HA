"""Sprint 14: is the deck legal in its own format?

The data for this has been complete since Sprint 02 — 8022 of 8022 cards carry
Scryfall's `legalities` — and no consumer read it. What a 60-card deck gets
instead of a bracket and a power score: facts, not judgements.
"""
import json

import pytest
from _helpers import insert_card, insert_deck
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services import legality


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _legalities(**kwargs) -> str:
    """A Scryfall legalities object with everything not named as not_legal."""
    base = {k: "not_legal" for k in (
        "standard", "pioneer", "modern", "legacy", "vintage", "pauper",
        "premodern", "commander", "predh", "brawl",
    )}
    base.update(kwargs)
    return json.dumps(base)


async def _deck(name: str, deck_format: str, cards: list[dict]) -> int:
    """Build a deck. Each card: {name, quantity, board?, legal_in?, oracle?}."""
    db = await get_db()
    deck_id = await insert_deck(db, name, deck_format=deck_format)
    for spec in cards:
        card_id = await insert_card(
            db, spec["name"], oracle_text=spec.get("oracle", "")
        )
        await db.execute(
            "UPDATE cards SET legalities = ? WHERE id = ?",
            (spec.get("legalities", _legalities(**(spec.get("legal_in") or {}))), card_id),
        )
        await db.execute(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, board)
               VALUES (?,?,?,?)""",
            (deck_id, card_id, spec.get("quantity", 1), spec.get("board", "main")),
        )
    await db.commit()
    return deck_id


def _kinds(result) -> list[str]:
    return sorted(v["kind"] for v in result["violations"])


def _filler(count: int, legal_in: dict, *, board: str = "main", start: int = 0) -> list[dict]:
    """`count` distinct single copies, so the filler never trips the copy limit
    it is only there to pad around."""
    return [
        {"name": f"Filler {start + i}", "quantity": 1, "board": board,
         "legal_in": legal_in}
        for i in range(count)
    ]


@pytest.mark.anyio
async def test_a_legal_constructed_deck_passes():
    deck_id = await _deck("Sligh", "Premodern", [
        {"name": f"Burn {i}", "quantity": 4, "legal_in": {"premodern": "legal"}}
        for i in range(15)
    ] + [
        {"name": f"Side {i}", "quantity": 3, "board": "side",
         "legal_in": {"premodern": "legal"}} for i in range(5)
    ])
    result = await legality.check_deck(deck_id)
    assert result["main_count"] == 60
    assert result["side_count"] == 15
    assert result["violations"] == []
    assert result["legal"] is True
    assert result["unknown_legality"] == 0


@pytest.mark.anyio
async def test_a_short_deck_and_an_oversized_sideboard_are_named():
    deck_id = await _deck("Half a deck", "Standard", [
        {"name": f"Card {i}", "quantity": 4, "legal_in": {"standard": "legal"}}
        for i in range(10)
    ] + [
        {"name": f"Side {i}", "quantity": 4, "board": "side",
         "legal_in": {"standard": "legal"}} for i in range(5)
    ])
    result = await legality.check_deck(deck_id)
    assert _kinds(result) == ["side" + "board", "size"]
    sizes = {v["kind"]: v for v in result["violations"]}
    assert sizes["size"]["have"] == 40 and sizes["size"]["want"] == 60
    assert sizes["sideboard"]["have"] == 20 and sizes["sideboard"]["want"] == 15


@pytest.mark.anyio
async def test_no_upper_bound_on_a_constructed_main_deck():
    """63 cards is legal and only ever a choice — a checker that calls it a
    violation is wrong about the rules, not strict about them."""
    deck_id = await _deck("Sixty-three", "Modern", [
        {"name": f"Card {i}", "quantity": 3, "legal_in": {"modern": "legal"}}
        for i in range(21)
    ])
    result = await legality.check_deck(deck_id)
    assert result["main_count"] == 63
    assert result["violations"] == []


@pytest.mark.anyio
async def test_a_banned_card_is_named_with_its_status():
    deck_id = await _deck("With a banned card", "Modern",
        _filler(56, {"modern": "legal"}) + [
        {"name": "Mox Opal", "quantity": 4, "legal_in": {"modern": "banned"}},
    ])
    result = await legality.check_deck(deck_id)
    banned = [v for v in result["violations"] if v["kind"] == "legality"]
    assert len(banned) == 1
    assert banned[0]["card"] == "Mox Opal"
    assert banned[0]["status"] == "banned"
    assert "banned in Modern" in banned[0]["detail"]


@pytest.mark.anyio
async def test_a_card_not_in_the_format_is_a_violation_too():
    deck_id = await _deck("Off-format", "Standard",
        _filler(56, {"standard": "legal"}) + [
        {"name": "Old Card", "quantity": 4, "legal_in": {"standard": "not_legal"}},
    ])
    result = await legality.check_deck(deck_id)
    assert [v["card"] for v in result["violations"] if v["kind"] == "legality"] == ["Old Card"]


@pytest.mark.anyio
async def test_too_many_copies():
    deck_id = await _deck("Five of", "Modern", [
        {"name": "Greedy", "quantity": 5, "legal_in": {"modern": "legal"}},
    ] + _filler(55, {"modern": "legal"}))
    result = await legality.check_deck(deck_id)
    copies = [v for v in result["violations"] if v["kind"] == "copies"]
    assert len(copies) == 1
    assert copies[0]["card"] == "Greedy" and copies[0]["have"] == 5


@pytest.mark.anyio
async def test_basic_lands_are_exempt_from_the_copy_limit():
    deck_id = await _deck("Mountains", "Modern", [
        {"name": "Mountain", "quantity": 24, "legal_in": {"modern": "legal"}},
    ] + _filler(36, {"modern": "legal"}))
    result = await legality.check_deck(deck_id)
    assert result["violations"] == []


@pytest.mark.anyio
async def test_a_card_that_lifts_its_own_limit_is_exempt():
    """Deck 3 holds 20x Rat Colony in a singleton format and is legal, because
    the card says so in its own rules text. A check without this reports
    nineteen violations on a correct deck — and a checker that cries wolf gets
    switched off rather than fixed."""
    deck_id = await _deck("Rats", "Commander", [
        {"name": "Rat Colony", "quantity": 20,
         "oracle": "Rat Colony gets +1/+0 for each other Rat you control.\n"
                   "A deck can have any number of cards named Rat Colony.",
         "legal_in": {"commander": "legal"}},
        {"name": "Swamp", "quantity": 40, "legal_in": {"commander": "legal"}},
    ] + _filler(40, {"commander": "legal"}))
    result = await legality.check_deck(deck_id)
    assert [v for v in result["violations"] if v["kind"] == "copies"] == []


@pytest.mark.anyio
async def test_singleton_is_enforced_for_commander():
    deck_id = await _deck("Two of", "Commander", [
        {"name": "Duplicate", "quantity": 2, "legal_in": {"commander": "legal"}},
        {"name": "Swamp", "quantity": 98, "legal_in": {"commander": "legal"}},
    ])  # Swamp is a basic land, so 98 of it is legal
    result = await legality.check_deck(deck_id)
    copies = [v for v in result["violations"] if v["kind"] == "copies"]
    assert [v["card"] for v in copies] == ["Duplicate"]
    assert copies[0]["want"] == 1


@pytest.mark.anyio
async def test_restricted_means_one_copy_not_a_violation_of_its_own():
    """Vintage restricts rather than bans. One copy is fine and must not be
    reported; two is a copy violation, not a legality violation."""
    one = await _deck("One Lotus", "Vintage", [
        {"name": "Black Lotus", "quantity": 1, "legal_in": {"vintage": "restricted"}},
    ] + _filler(59, {"vintage": "legal"}))
    assert (await legality.check_deck(one))["violations"] == []

    two = await _deck("Two Lotuses", "Vintage", [
        {"name": "Black Lotus", "quantity": 2, "legal_in": {"vintage": "restricted"}},
    ] + _filler(58, {"vintage": "legal"}))
    result = await legality.check_deck(two)
    assert _kinds(result) == ["copies"]
    assert "restricted" in result["violations"][0]["detail"]


@pytest.mark.anyio
async def test_the_maybeboard_is_not_part_of_the_deck():
    """A card parked in the maybeboard counts neither towards the size nor
    against the copy limit — it is not in the deck."""
    deck_id = await _deck("With a maybeboard", "Modern",
        _filler(60, {"modern": "legal"}) + [
        {"name": "Banned Idea", "quantity": 12, "board": "maybe",
         "legal_in": {"modern": "banned"}},
    ])
    result = await legality.check_deck(deck_id)
    assert result["main_count"] == 60
    assert result["maybeboard_count"] == 12
    assert result["violations"] == []


@pytest.mark.anyio
async def test_an_unknown_legality_is_counted_not_assumed():
    """A card we never asked Scryfall about is neither legal nor illegal. Same
    rule the bracket uses for cards Spellbook does not classify: unclassified,
    not clean."""
    deck_id = await _deck("Half unknown", "Modern",
        _filler(40, {"modern": "legal"}) + [
        {"name": "Never asked", "quantity": 4, "legalities": "{}"},
    ] + _filler(16, {"modern": "legal"}, start=100))
    result = await legality.check_deck(deck_id)
    assert result["unknown_legality"] == 1
    assert [v for v in result["violations"] if v["kind"] == "legality"] == []


@pytest.mark.anyio
async def test_an_unknown_format_is_not_checked_and_does_not_claim_legal():
    deck_id = await _deck("Mystery", "Nonsense", [
        {"name": "Whatever", "quantity": 3},
    ])
    result = await legality.check_deck(deck_id)
    assert result["checked"] is False
    assert result["legal"] is False, "not checked must not read as legal"
    assert result["violations"] == []


@pytest.mark.anyio
async def test_commander_deck_of_exactly_100_passes():
    deck_id = await _deck("Proper Commander", "Commander", [
        {"name": f"Card {i}", "quantity": 1, "legal_in": {"commander": "legal"}}
        for i in range(100)
    ])
    result = await legality.check_deck(deck_id)
    assert result["main_count"] == 100
    assert result["violations"] == []


@pytest.mark.anyio
async def test_the_api_serves_and_stores_the_check(client):
    deck_id = await _deck("Stored", "Premodern", [
        {"name": f"Card {i}", "quantity": 4, "legal_in": {"premodern": "legal"}}
        for i in range(15)
    ])
    async with client as ac:
        first = (await ac.get(f"/api/decks/{deck_id}/legality")).json()
        again = (await ac.get(f"/api/decks/{deck_id}/legality")).json()
    assert first["legal"] and again["legal"]

    db = await get_db()
    cursor = await db.execute(
        "SELECT legality_json, legality_checked_at FROM decks WHERE id = ?", (deck_id,)
    )
    row = await cursor.fetchone()
    assert row["legality_checked_at"] is not None
    assert json.loads(row["legality_json"])["main_count"] == 60


@pytest.mark.anyio
async def test_recheck_all_reports_a_summary(client):
    await _deck("Fine", "Premodern", [
        {"name": f"Card {i}", "quantity": 4, "legal_in": {"premodern": "legal"}}
        for i in range(15)
    ])
    await _deck("Too small", "Premodern", [
        {"name": "Lonely", "quantity": 1, "legal_in": {"premodern": "legal"}},
    ])
    async with client as ac:
        summary = (await ac.post("/api/decks/legality/recheck-all")).json()
    assert summary["decks"] == 2
    assert summary["checked"] == 2
    assert summary["illegal"] == 1
    assert "results" not in summary, "the sweep returns a summary, not every deck"


# ---------------------------------------------------------------------------
# What reaches Home Assistant
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ha_sensor_tells_unchecked_from_illegal():
    """`legal` is null when nothing was checked and false when it was. A
    template must be able to tell those apart: "we did not look" and "we looked
    and it is wrong" call for different reactions."""
    from app.services.ha_metrics import deck_stats

    db = await get_db()
    ok = await _deck("Fine", "Premodern",
                     _filler(60, {"premodern": "legal"}))
    bad = await _deck("Short", "Premodern",
                      _filler(10, {"premodern": "legal"}, start=200))
    unknown_format = await _deck("Mystery", "Nonsense", [{"name": "Whatever"}])

    await legality.check_all_decks()
    by_id = {d["deck_id"]: d for d in await deck_stats(db)}

    assert by_id[ok]["legal"] is True
    assert by_id[ok]["violations"] == 0
    assert by_id[bad]["legal"] is False
    assert by_id[bad]["violations"] == 1
    assert "at least 60" in by_id[bad]["violation_detail"]
    assert by_id[unknown_format]["legal"] is None, "unchecked must not read as legal or illegal"


@pytest.mark.anyio
async def test_a_newly_illegal_deck_is_announced_once(monkeypatch):
    """The nightly check must announce the transition, not the state. Without
    the dedup stamp it pushes the same banned card every night, which is the
    fastest way to teach someone to ignore the notification."""
    from app.services import notifications

    posted: list[dict] = []

    async def fake_notify(**kwargs):
        posted.append(kwargs)
        return True

    monkeypatch.setattr(notifications, "send_persistent_notification", fake_notify)

    deck_id = await _deck("Rotated out", "Standard",
                          _filler(56, {"standard": "legal"}) + [
                              {"name": "Banned Thing", "quantity": 4,
                               "legal_in": {"standard": "banned"}}])
    await legality.check_all_decks()

    assert await notifications.notify_newly_illegal_decks() == 1
    assert len(posted) == 1
    assert "Banned Thing" in posted[0]["message"]
    assert posted[0]["notification_id"] == f"stoerung_mtg_deck_illegal_{deck_id}"

    # Same state, second run: silent.
    assert await notifications.notify_newly_illegal_decks() == 0
    assert len(posted) == 1

    # Checked again, same problem: still silent. This is the case the first
    # attempt got wrong — it compared timestamps, and since the check runs every
    # night, "checked after we announced" was true every night.
    await legality.check_all_decks()
    assert await notifications.notify_newly_illegal_decks() == 0
    assert len(posted) == 1

    # A *different* problem gets through. Here: the deck also became too small.
    db = await get_db()
    await db.execute(
        "DELETE FROM deck_cards WHERE deck_id = ? AND card_id IN "
        "(SELECT card_id FROM deck_cards WHERE deck_id = ? LIMIT 20)",
        (deck_id, deck_id),
    )
    await db.commit()
    await legality.check_all_decks()
    assert await notifications.notify_newly_illegal_decks() == 1
    assert len(posted) == 2
    assert "main deck" in posted[1]["message"]


@pytest.mark.anyio
async def test_a_legal_or_unchecked_deck_is_never_announced(monkeypatch):
    from app.services import notifications

    posted: list[dict] = []

    async def fake_notify(**kwargs):
        posted.append(kwargs)
        return True

    monkeypatch.setattr(notifications, "send_persistent_notification", fake_notify)

    await _deck("Fine", "Premodern", _filler(60, {"premodern": "legal"}))
    await _deck("Mystery", "Nonsense", [{"name": "Whatever", "quantity": 3}])
    await legality.check_all_decks()

    assert await notifications.notify_newly_illegal_decks() == 0
    assert posted == []


@pytest.mark.anyio
async def test_a_partial_combo_needing_a_banned_card_is_marked_not_completable():
    """Spellbook does not know the deck's format, so a combo one banned card
    short looks exactly like a real upgrade. In Commander that almost never
    bites; in Standard most of the card pool is not legal."""
    db = await get_db()
    deck_id = await _deck("Standard deck", "Standard",
                          _filler(60, {"standard": "legal"}))
    banned_id = await insert_card(db, "Forbidden Piece")
    await db.execute("UPDATE cards SET legalities = ? WHERE id = ?",
                     (_legalities(standard="banned"), banned_id))
    legal_id = await insert_card(db, "Available Piece")
    await db.execute("UPDATE cards SET legalities = ? WHERE id = ?",
                     (_legalities(standard="legal"), legal_id))
    await db.commit()

    combos = await legality.annotate_combos("Standard", [
        {"name": "Impossible", "missing_cards": ["Forbidden Piece"]},
        {"name": "Buyable", "missing_cards": ["Available Piece"]},
        {"name": "Half", "missing_cards": ["Forbidden Piece", "Available Piece"]},
        {"name": "Complete", "missing_cards": []},
        {"name": "Never seen", "missing_cards": ["Some Card We Lack"]},
    ])
    by_name = {c["name"]: c for c in combos}
    assert by_name["Impossible"]["completable"] is False
    assert by_name["Impossible"]["missing_not_legal"] == ["Forbidden Piece"]
    assert by_name["Buyable"]["completable"] is True
    # One of two is legal, so it can still be finished.
    assert by_name["Half"]["completable"] is True
    assert by_name["Complete"]["completable"] is True
    # A card we have never seen is unknown, not illegal.
    assert by_name["Never seen"]["missing_not_legal"] == []
    assert by_name["Never seen"]["completable"] is True
    assert deck_id  # keeps the fixture honest


@pytest.mark.anyio
async def test_combos_are_not_annotated_for_a_format_without_a_legality_key():
    combos = await legality.annotate_combos("Unknown", [
        {"name": "Whatever", "missing_cards": ["Anything"]},
    ])
    assert combos[0]["completable"] is True
    assert combos[0]["missing_not_legal"] == []


# ---------------------------------------------------------------------------
# What the first run against the real database found
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tokens_are_not_cards():
    """Archidekt lets a token sit in a decklist as a reminder of what the deck
    makes. The first run of this check against the live data reported deck 7 as
    104 cards in a 100-card format with three "cards" not legal in Commander —
    all four were token rows."""
    db = await get_db()
    deck_id = await insert_deck(db, "With tokens", deck_format="Commander")
    for i in range(100):
        card_id = await insert_card(db, f"Real {i}")
        await db.execute("UPDATE cards SET legalities = ? WHERE id = ?",
                         (_legalities(commander="legal"), card_id))
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'main')",
            (deck_id, card_id))
    for name, layout, type_line in (
        ("Frog Lizard", "token", "Token Creature — Frog Lizard"),
        ("Copy", "token", "Token"),
        ("Some Emblem", "emblem", "Emblem"),
    ):
        card_id = await insert_card(db, name, type_line=type_line, layout=layout)
        # Tokens have no format legality at all, which is exactly why they
        # looked like violations.
        await db.execute("UPDATE cards SET legalities = ? WHERE id = ?",
                         (_legalities(commander="not_legal"), card_id))
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'main')",
            (deck_id, card_id))
    await db.commit()

    result = await legality.check_deck(deck_id)
    assert result["main_count"] == 100, "tokens must not count towards deck size"
    assert result["violations"] == []


@pytest.mark.anyio
async def test_a_sideboard_in_a_format_without_one_is_not_a_violation():
    """Commander has no sideboard, and Archidekt offers the category anyway —
    deck 20 keeps three cards there as a scratch list. Calling that a rules
    violation is noise about a habit, so those cards are treated like a
    maybeboard: outside the deck, not counted, not checked."""
    deck_id = await _deck("Commander with notes", "Commander",
        _filler(100, {"commander": "legal"}) + [
        {"name": "Scratch Note", "quantity": 3, "board": "side",
         "legal_in": {"commander": "not_legal"}},
    ])
    result = await legality.check_deck(deck_id)
    assert result["main_count"] == 100
    assert result["side_count"] == 0, "no sideboard in this format means no sideboard pile"
    assert result["maybeboard_count"] == 3
    assert result["violations"] == []


@pytest.mark.anyio
async def test_a_sideboard_in_a_format_with_one_is_still_checked():
    """The counterpart: where the format has a sideboard, the limit applies."""
    deck_id = await _deck("Too big a sideboard", "Modern",
        _filler(60, {"modern": "legal"}) + [
        {"name": f"Side {i}", "quantity": 4, "board": "side",
         "legal_in": {"modern": "legal"}} for i in range(5)
    ])
    result = await legality.check_deck(deck_id)
    assert result["side_count"] == 20
    assert _kinds(result) == ["sideboard"]
