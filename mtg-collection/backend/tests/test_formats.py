"""Sprint 12: which analysis applies to which format, and which pile a card is in.

Before 0.47.0 the answer to the first question was "all of them, always".
A Standard deck synced from Archidekt came out with a WotC bracket of 2, an
edhpowerlevel score and a Spellbook label — three statements about a system it
is not part of, none of which declined to answer.
"""
import json

import pytest
from _helpers import insert_card, insert_deck
from httpx import ASGITransport, AsyncClient

from app.clients.archidekt import board_of, deck_boards, parse_archidekt_card
from app.database import get_db
from app.main import app
from app.services import formats


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# The table itself
# ---------------------------------------------------------------------------

def test_every_archidekt_number_resolves_to_a_known_format():
    """A number in the lookup must have a spec, or the gates read as 'unknown'.

    The failure this guards is quiet: a name with no spec answers False to
    every gate, so the deck simply shows nothing and nobody can tell that from
    "this format has no bracket".
    """
    missing = [
        (number, name)
        for number, name in formats.ARCHIDEKT_FORMATS.items()
        if name not in formats.FORMATS
    ]
    assert missing == []


def test_measured_numbers_are_the_measured_ones():
    """The five numbers that were wrong before 0.47.0, as measured 2026-09-15.

    Kept as a test rather than only as a comment because the old table was also
    written down confidently. If Archidekt ever renumbers, this fails and the
    remeasurement is a known task instead of a mystery.
    """
    assert formats.format_name(1) == "Standard"
    assert formats.format_name(3) == "Commander"
    assert formats.format_name(13) == "Brawl"        # was "Oathbreaker"
    assert formats.format_name(14) == "Oathbreaker"  # was "Pioneer"
    assert formats.format_name(15) == "Pioneer"      # was "Historic"
    assert formats.format_name(22) == "Premodern"    # was "Predh"
    assert formats.format_name(23) == "Predh"        # was "Timeless"


def test_an_unverified_number_is_not_guessed():
    """Everything above 6 shifted by one, so the pattern would predict names for
    7, 9, 10, ... — and they are deliberately not filled in. A plausible wrong
    name is worse than a gap, because nothing looks at it again."""
    for number in formats.UNVERIFIED_FORMAT_IDS:
        assert formats.format_name(number) == "Unknown", number
    assert formats.format_name(None) == "Unknown"
    assert formats.format_name(9999) == "Unknown"


def test_unknown_format_switches_everything_off():
    spec = formats.spec("Nonsense Format")
    assert spec.family == "unknown"
    assert not spec.commander and not spec.bracket and not spec.power
    assert spec.legality_key is None


def test_bracket_is_commander_only():
    """The WotC bracket describes casual multiplayer Commander. Duel Commander
    has its own banlist, Brawl is a different game, and neither is what
    brackets 1-3 are written about."""
    assert formats.bracket_applies("Commander")
    for other in ("Duel Commander", "Brawl", "Standard", "Pauper", "Premodern"):
        assert not formats.bracket_applies(other), other


def test_power_is_commander_only():
    assert formats.power_applies("Commander")
    for other in ("Standard", "Modern", "Legacy", "Premodern", "Brawl"):
        assert not formats.power_applies(other), other


def test_constructed_formats_share_one_shape_and_differ_only_in_legality():
    keys = set()
    for name in ("Standard", "Pioneer", "Modern", "Legacy", "Pauper", "Premodern"):
        rules = formats.deck_rules(name)
        assert (rules.main_min, rules.side_max, rules.max_copies) == (60, 15, 4), name
        assert not rules.singleton, name
        assert rules.default_pod_size == 2, name
        keys.add(formats.legality_key(name))
    assert len(keys) == 6, "each format must check its own legality key"


def test_commander_rules():
    rules = formats.deck_rules("Commander")
    assert (rules.main_min, rules.main_max) == (100, 100)
    assert rules.singleton and rules.max_copies == 1
    assert rules.side_max == 0
    assert rules.default_pod_size == 4


# ---------------------------------------------------------------------------
# The cross-check: does the deck look like its format claims?
# ---------------------------------------------------------------------------

def test_shape_check_passes_for_a_normal_deck():
    assert formats.check_shape(
        "Commander", total_cards=100, distinct_cards=100, has_commander_card=True
    ) is None
    assert formats.check_shape(
        "Standard", total_cards=60, distinct_cards=22, has_commander_card=False
    ) is None


def test_shape_check_catches_a_commander_in_a_constructed_format():
    reason = formats.check_shape(
        "Standard", total_cards=60, distinct_cards=22, has_commander_card=True
    )
    assert reason and "commander" in reason.lower()


def test_shape_check_catches_playsets_in_a_singleton_format():
    reason = formats.check_shape(
        "Commander", total_cards=100, distinct_cards=40, has_commander_card=True
    )
    assert reason and "singleton" in reason.lower()


def test_shape_check_stays_quiet_on_a_fragment():
    """Deck 14 holds 8 cards. That is a draft, not a claim about its format —
    and a checker that shouts about every unfinished deck gets ignored."""
    assert formats.check_shape(
        "Commander", total_cards=8, distinct_cards=8, has_commander_card=False
    ) is None


def test_shape_check_stays_quiet_for_an_unknown_format():
    assert formats.check_shape(
        "Unknown", total_cards=250, distinct_cards=3, has_commander_card=True
    ) is None


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------

#: A deck payload shaped like Archidekt's, with the flags measured on deck
#: 26328851 on 2026-09-15 — note `Sideboard` carries includedInDeck **true**.
_PAYLOAD = {
    "categories": [
        {"name": "Maybeboard", "includedInDeck": False},
        {"name": "Sideboard", "includedInDeck": True},
        {"name": "Land", "includedInDeck": True},
        {"name": "Slot In", "includedInDeck": False},
    ]
}


def test_deck_boards_reads_archidekts_own_flags():
    boards = deck_boards(_PAYLOAD)
    assert boards == {
        "Maybeboard": "maybe",
        "Sideboard": "side",
        "Land": "main",
        "Slot In": "maybe",
    }


def test_sideboard_needs_the_name_rule_because_the_flag_says_it_is_in_the_deck():
    """The measurement that decided this: Archidekt counts the sideboard
    towards the deck, so `includedInDeck` cannot separate main from side."""
    assert _PAYLOAD["categories"][1] == {"name": "Sideboard", "includedInDeck": True}
    assert deck_boards(_PAYLOAD)["Sideboard"] == "side"


def test_an_undeclared_category_counts_as_main():
    assert board_of(["Ramp"], deck_boards(_PAYLOAD)) == "main"


def test_the_strictest_category_wins():
    boards = deck_boards(_PAYLOAD)
    assert board_of(["Land", "Slot In"], boards) == "maybe"
    assert board_of(["Land", "Sideboard"], boards) == "side"
    assert board_of(["Sideboard", "Slot In"], boards) == "maybe"


def test_parse_card_carries_the_board():
    entry = {
        "card": {"uid": "abc", "oracleCard": {"name": "Ravenous Baloth"}},
        "categories": ["Sideboard"],
        "quantity": 1,
    }
    assert parse_archidekt_card(entry, deck_boards(_PAYLOAD))["board"] == "side"
    # No map at all (the collection sync) -> main, and nothing reads it.
    assert parse_archidekt_card(entry)["board"] == "main"


@pytest.mark.anyio
async def test_the_same_card_in_two_piles_stays_two_rows():
    """The bug this fixes, measured on deck 61 before 0.47.0: Archidekt had
    3x Ravenous Baloth under Lifegain and 1x in the sideboard, the database had
    4x Sideboard, and the deck read as 57 main cards instead of 60."""
    db = await get_db()
    deck_id = await insert_deck(db, "Boards")
    card_id = await insert_card(db, "Ravenous Baloth")

    for quantity, category, board in ((3, "Lifegain", "main"), (1, "Sideboard", "side")):
        await db.execute(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, category, board)
               VALUES (?,?,?,?,?)
               ON CONFLICT(deck_id, card_id, modifier, board) DO UPDATE SET
                   quantity = deck_cards.quantity + excluded.quantity""",
            (deck_id, card_id, quantity, category, board),
        )
    await db.commit()

    cursor = await db.execute(
        "SELECT board, quantity FROM deck_cards WHERE deck_id=? ORDER BY board", (deck_id,)
    )
    rows = [(r["board"], r["quantity"]) for r in await cursor.fetchall()]
    assert rows == [("main", 3), ("side", 1)]


# ---------------------------------------------------------------------------
# The gates, end to end
# ---------------------------------------------------------------------------

async def _deck_with_cards(name: str, deck_format: str, count: int = 60) -> int:
    db = await get_db()
    deck_id = await insert_deck(db, name, deck_format=deck_format)
    for index in range(count):
        card_id = await insert_card(db, f"{name} Card {index}")
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'main')",
            (deck_id, card_id),
        )
    await db.commit()
    return deck_id


@pytest.mark.anyio
async def test_a_constructed_deck_gets_no_bracket_and_no_power():
    from app.services.bracket import compute_bracket
    from app.services.power_level import compute_power_level

    deck_id = await _deck_with_cards("Standard Test", "Standard")

    bracket = await compute_bracket(deck_id)
    assert bracket["bracket"] is None
    assert bracket["reason"] == "not_applicable"

    power = await compute_power_level(deck_id)
    assert power["score"] is None
    assert power["reason"] == "not_applicable"


@pytest.mark.anyio
async def test_a_commander_deck_still_gets_both():
    from app.services.bracket import compute_bracket
    from app.services.power_level import compute_power_level

    deck_id = await _deck_with_cards("Commander Test", "Commander", count=40)

    assert (await compute_bracket(deck_id))["bracket"] == 2
    assert (await compute_power_level(deck_id))["score"] is not None


@pytest.mark.anyio
async def test_changing_the_format_clears_a_stored_bracket_and_score():
    """A deck re-pointed at another format on Archidekt must not keep the
    numbers it earned as a Commander deck. Without this the label survives its
    own justification — which is exactly what happened to the two Premodern
    decks, carrying a bracket of 2 from a table that read their format wrong.
    """
    from app.services.bracket import compute_bracket
    from app.services.power_level import compute_power_level

    db = await get_db()
    deck_id = await _deck_with_cards("Was Commander", "Commander", count=40)
    await compute_bracket(deck_id)
    await compute_power_level(deck_id)
    await db.execute(
        "UPDATE decks SET spellbook_bracket_tag = 'E' WHERE id = ?", (deck_id,)
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT computed_bracket, power_score FROM decks WHERE id = ?", (deck_id,)
    )
    before = await cursor.fetchone()
    assert before["computed_bracket"] is not None
    assert before["power_score"] is not None

    await db.execute("UPDATE decks SET format = 'Modern' WHERE id = ?", (deck_id,))
    await db.commit()
    await compute_bracket(deck_id)
    await compute_power_level(deck_id)

    cursor = await db.execute(
        """SELECT computed_bracket, computed_bracket_detail, power_score,
                  power_level, spellbook_bracket_tag
           FROM decks WHERE id = ?""",
        (deck_id,),
    )
    after = await cursor.fetchone()
    assert after["computed_bracket"] is None
    assert after["computed_bracket_detail"] is None
    assert after["power_score"] is None
    assert after["power_level"] is None
    assert after["spellbook_bracket_tag"] == ""


@pytest.mark.anyio
async def test_deck_api_reports_rules_counts_and_no_bracket(client):
    db = await get_db()
    deck_id = await insert_deck(db, "Sligh", deck_format="Premodern")
    for index in range(3):
        card_id = await insert_card(db, f"Sligh Card {index}")
        board = "side" if index == 2 else "main"
        await db.execute(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, category, board)
               VALUES (?,?,?,?,?)""",
            (deck_id, card_id, 4, "Burn", board),
        )
    await db.commit()

    async with client as ac:
        detail = (await ac.get(f"/api/decks/{deck_id}")).json()
        listing = (await ac.get("/api/decks/")).json()

    assert detail["format"] == "Premodern"
    assert detail["effective_bracket"] is None
    assert detail["power_score"] is None
    rules = detail["format_rules"]
    assert rules["family"] == "constructed"
    assert rules["legality_key"] == "premodern"
    assert (rules["main_min"], rules["side_max"], rules["max_copies"]) == (60, 15, 4)
    assert not rules["bracket_applies"] and not rules["power_applies"]

    entry = next(d for d in listing if d["id"] == deck_id)
    assert entry["card_count"] == 8          # main only
    assert entry["sideboard_count"] == 4
    assert entry["maybeboard_count"] == 0
    assert entry["format_rules"]["format"] == "Premodern"


@pytest.mark.anyio
async def test_list_detail_and_ha_agree_about_a_stale_bracket(client):
    """The three readers must not disagree — and they did, for one deploy.

    A stored bracket and score survive a format change until the next
    recompute. 0.47.0 gated the deck *page* on the format but not the deck
    *list* or the HA sensor, and the live system showed the two Premodern decks
    at bracket 2 in the list and at nothing on their own page, within minutes of
    the deploy. The gate now lives inside `effective_bracket`, and this test is
    what keeps the three in step.

    Same shape as the duplicated booking path in 0.45.0: two call sites doing
    "the same thing", neither wrong on its own, drifting quietly.
    """
    from app.services.ha_metrics import deck_stats

    db = await get_db()
    deck_id = await insert_deck(db, "Stale numbers", deck_format="Premodern")
    await db.execute(
        """UPDATE decks SET computed_bracket = 2, power_score = 365.1,
           power_level = 3.5, spellbook_bracket_tag = 'E' WHERE id = ?""",
        (deck_id,),
    )
    await db.commit()

    async with client as ac:
        detail = (await ac.get(f"/api/decks/{deck_id}")).json()
        listing = (await ac.get("/api/decks/")).json()
    row = next(d for d in listing if d["id"] == deck_id)
    sensor = next(d for d in await deck_stats(db) if d["deck_id"] == deck_id)

    for label, bracket, score in (
        ("deck page", detail["effective_bracket"], detail["power_score"]),
        ("deck list", row["effective_bracket"], row["power_score"]),
        ("HA sensor", sensor["bracket"], sensor["power_score"]),
    ):
        assert bracket is None, f"{label} still reports a bracket"
        assert score is None, f"{label} still reports a power score"

    assert detail["spellbook_bracket_tag"] == ""
    assert detail["computed_bracket_detail"] is None
    assert sensor["bracket_source"] == "not_applicable"
    # The stored values are untouched, so they return if the deck does.
    cursor = await db.execute(
        "SELECT computed_bracket, power_score FROM decks WHERE id = ?", (deck_id,)
    )
    stored = await cursor.fetchone()
    assert stored["computed_bracket"] == 2
    assert stored["power_score"] == 365.1


@pytest.mark.anyio
async def test_a_hand_set_bracket_does_not_leak_into_a_constructed_deck(client):
    """`user_bracket` normally wins over everything. It must not win here: a 3
    left on a deck whose format was read wrong is a leftover, not an opinion."""
    db = await get_db()
    deck_id = await insert_deck(db, "Was mislabelled", deck_format="Modern")
    await db.execute("UPDATE decks SET user_bracket = 3 WHERE id = ?", (deck_id,))
    await db.commit()

    async with client as ac:
        detail = (await ac.get(f"/api/decks/{deck_id}")).json()
    assert detail["user_bracket"] == 3
    assert detail["effective_bracket"] is None


@pytest.mark.anyio
async def test_deck_detail_reports_a_shape_mismatch(client):
    """100 singleton cards with a commander is a Commander deck whatever the
    format number says. Reported, not corrected — the table has been wrong
    before, and so can a deck."""
    db = await get_db()
    deck_id = await insert_deck(db, "Mislabelled", deck_format="Standard")
    for index in range(30):
        card_id = await insert_card(db, f"Mislabelled Card {index}")
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board, is_commander) "
            "VALUES (?,?,1,'main',?)",
            (deck_id, card_id, 1 if index == 0 else 0),
        )
    await db.commit()

    async with client as ac:
        detail = (await ac.get(f"/api/decks/{deck_id}")).json()
    assert detail["format_mismatch"]
    assert "commander" in detail["format_mismatch"].lower()


@pytest.mark.anyio
async def test_migration_26_maps_the_old_format_names():
    """The correction table is applied to names, because the number was never
    stored before. Every old name must map to something the new table knows."""
    from app.database import _FORMAT_NAME_CORRECTIONS

    for old, new in _FORMAT_NAME_CORRECTIONS.items():
        assert new == "Unknown" or new in formats.FORMATS, (old, new)
    # The one that bit us: two live decks carried "Predh" for Premodern.
    assert _FORMAT_NAME_CORRECTIONS["Predh"] == "Premodern"
    # And the six that were right are left alone.
    for untouched in ("Standard", "Modern", "Commander", "Legacy", "Vintage", "Pauper"):
        assert untouched not in _FORMAT_NAME_CORRECTIONS
