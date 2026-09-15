"""Sprint 13: what a deck actually demands.

"How many copies do my decks need" was asked in seven places, each with its own
SQL, and every one counted every row in `deck_cards` — the maybeboard, the
tokens, and the four decks in "Disassembled" and "Older Versions". With
Commander that overstates demand by a card here and there. With playsets it
overstates by four at a time, and the surplus, the sell advisor and the shopping
list are all built on it.
"""
import re
from pathlib import Path

import pytest
from _helpers import insert_card, insert_deck

from app.database import DEFAULT_NON_BINDING_FOLDERS, get_db

APP = Path(__file__).resolve().parents[1] / "app"


def test_no_demand_query_reads_deck_cards_directly():
    """The guard that keeps the seven in step.

    A `deck_usage` CTE or an `in_decks` column reading `deck_cards` raw is a
    query that counts the maybeboard and the disassembled decks. The view exists
    so a caller has to *name* it rather than remember a rule — this test is what
    catches the one who copies an old query instead.
    """
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"(deck_usage AS|as in_decks|AS in_decks|as total_in_decks)", text
        ):
            # Look at the SQL around the match: which table does it read?
            window = text[match.start(): match.start() + 320]
            if "deck_cards" in window and "deck_demand" not in window:
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(APP)}:{line}")
    assert offenders == [], (
        "these count deck demand from deck_cards instead of the deck_demand "
        f"view: {offenders}"
    )


async def _card_in_decks(name: str, specs: list[tuple[str, int, str, str]]) -> int:
    """specs: (deck name, quantity, board, folder). Returns the card id."""
    db = await get_db()
    card_id = await insert_card(db, name)
    for deck_name, quantity, board, folder in specs:
        deck_id = await insert_deck(db, deck_name)
        await db.execute(
            "UPDATE decks SET folder_name = ?, binds_copies = ? WHERE id = ?",
            (folder, 0 if folder in DEFAULT_NON_BINDING_FOLDERS else 1, deck_id),
        )
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,?,?)",
            (deck_id, card_id, quantity, board),
        )
    await db.commit()
    return card_id


async def _demand(card_id: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM deck_demand WHERE card_id = ?",
        (card_id,),
    )
    return (await cursor.fetchone())[0]


@pytest.mark.anyio
async def test_the_main_deck_and_the_sideboard_count():
    card_id = await _card_in_decks("Wanted", [
        ("Active", 4, "main", "Maxi"),
        ("Active", 2, "side", "Maxi"),
    ])
    assert await _demand(card_id) == 6


@pytest.mark.anyio
async def test_the_maybeboard_does_not_count():
    card_id = await _card_in_decks("Maybe", [
        ("Active", 4, "main", "Maxi"),
        ("Thinking", 4, "maybe", "Maxi"),
    ])
    assert await _demand(card_id) == 4


@pytest.mark.anyio
async def test_a_disassembled_deck_does_not_tie_up_its_cards():
    """Deck 10 is the previous version of deck 1 — the same cards, counted
    twice. Four such decks hold 432 cards between them."""
    card_id = await _card_in_decks("Shared", [
        ("Current", 4, "main", "Maxi"),
        ("Older Sharknado", 4, "main", "Older Versions"),
        ("Taken apart", 4, "main", "Disassembled"),
    ])
    assert await _demand(card_id) == 4


@pytest.mark.anyio
async def test_work_in_progress_still_binds():
    """A deck being built holds its cards — they are in the deck box."""
    card_id = await _card_in_decks("In progress", [
        ("Building", 3, "main", "Work in Progress"),
    ])
    assert await _demand(card_id) == 3


@pytest.mark.anyio
async def test_tokens_never_count_as_demand():
    db = await get_db()
    card_id = await insert_card(db, "Treasure", type_line="Token Artifact", layout="token")
    deck_id = await insert_deck(db, "With a token")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,9,'main')",
        (deck_id, card_id),
    )
    await db.commit()
    assert await _demand(card_id) == 0


@pytest.mark.anyio
async def test_a_hand_set_override_beats_the_folder():
    """The folder sets the starting value; a deck can be told otherwise —
    the same arrangement `user_bracket` has over the computed one."""
    db = await get_db()
    card_id = await insert_card(db, "Overridden")
    deck_id = await insert_deck(db, "Special case")
    await db.execute(
        "UPDATE decks SET folder_name = 'Disassembled', binds_copies = 1 WHERE id = ?",
        (deck_id,),
    )
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,4,'main')",
        (deck_id, card_id),
    )
    await db.commit()
    assert await _demand(card_id) == 4


# ---------------------------------------------------------------------------
# What the numbers look like from outside
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_completeness_separates_missing_from_bound_elsewhere():
    """The number this endpoint was missing.

    Owning four copies means nothing if all four are in another deck — and with
    playsets that is the normal case, not an edge one. "Buy one" and "take it
    out of the other deck" are different decisions, so they are reported
    separately rather than folded into one count.
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    db = await get_db()
    target = await insert_deck(db, "The one being built")
    other = await insert_deck(db, "Already assembled")

    # Owned 4, all four in the other deck, this deck wants 4.
    shared = await insert_card(db, "Contested Card", price_eur="3.00")
    await db.execute(
        "INSERT INTO collection (card_id, quantity, foil_quantity) VALUES (?,4,0)",
        (shared,))
    for deck_id in (target, other):
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,4,'main')",
            (deck_id, shared))

    # Owned none, nobody else has it: a genuine purchase.
    absent = await insert_card(db, "Never Owned", price_eur="10.00")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'main')",
        (target, absent))
    await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        result = (await ac.get(f"/api/decks/{target}/completeness")).json()

    # Owned four, all four in the other deck: not a purchase, a card to move.
    assert result["blocked_by_other_decks"] == 1
    # The genuine gap is still a purchase, and it is the only one.
    by_name = {m["name"]: m for m in result["missing_cards"]}
    assert list(by_name) == ["Never Owned"]
    assert by_name["Never Owned"]["bound_elsewhere"] == 0
    assert by_name["Never Owned"]["owned"] == 0


@pytest.mark.anyio
async def test_a_maybeboard_card_is_not_deck_demand_in_completeness():
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    db = await get_db()
    target = await insert_deck(db, "Wants it")
    parked = await insert_deck(db, "Just thinking about it")
    card = await insert_card(db, "Parked Card", price_eur="1.00")
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'main')",
        (target, card))
    await db.execute(
        "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,4,'maybe')",
        (parked, card))
    await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        result = (await ac.get(f"/api/decks/{target}/completeness")).json()
    # Four copies parked in someone's maybeboard block nothing.
    assert result["blocked_by_other_decks"] == 0
    assert result["missing_cards"][0]["bound_elsewhere"] == 0


@pytest.mark.anyio
async def test_the_power_score_counts_the_main_deck_only():
    """Deck 10 scored 824.7 with 32 Backlog cards that are not in the deck. The
    filter was held back in 0.47.0 so the format gate could be measured on its
    own; this is where it lands."""
    from app.services.power_level import compute_power_level

    db = await get_db()
    deck_id = await insert_deck(db, "With a backlog")
    for i in range(40):
        card_id = await insert_card(db, f"Played {i}", price_usd="1.00", edhrec_rank=500)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'main')",
            (deck_id, card_id))
    await db.commit()
    main_only = (await compute_power_level(deck_id))["score"]

    for i in range(20):
        card_id = await insert_card(db, f"Backlog {i}", price_usd="90.00", edhrec_rank=10)
        await db.execute(
            "INSERT INTO deck_cards (deck_id, card_id, quantity, board) VALUES (?,?,1,'maybe')",
            (deck_id, card_id))
    await db.commit()

    assert (await compute_power_level(deck_id))["score"] == main_only, (
        "twenty expensive maybeboard cards must not move the score"
    )


@pytest.mark.anyio
async def test_the_override_survives_a_sync_and_the_folder_does_not():
    """Two columns, and only one of them a sync is allowed to touch.

    `binds_copies` is re-derived from the Archidekt folder on every sync;
    `binds_copies_override` is a decision someone made by hand. Writing both
    from the same place is how a hand-set answer quietly disappears overnight —
    the bracket has the same pair for the same reason.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.services.sync_service import apply_binding_from_folder

    folder = DEFAULT_NON_BINDING_FOLDERS[0]
    db = await get_db()
    deck_id = await insert_deck(db, "Back in the box", folder=folder)
    # The folder is just a string on the row until a sync reads it — the
    # derivation is an action, not a column default.
    await apply_binding_from_folder(db, deck_id, folder)
    await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        # The folder decided: not binding, and nobody set it by hand.
        deck = (await ac.get(f"/api/decks/{deck_id}")).json()
        assert deck["binds_copies"] is False
        assert deck["binds_copies_override"] is None

        # Someone says "no, this one still holds its cards".
        deck = (await ac.put(f"/api/decks/{deck_id}/user-fields",
                             json={"binds_copies_override": True})).json()
        assert deck["binds_copies"] is True
        assert deck["binds_copies_override"] is True

        # A sync re-derives the folder value. The override must win anyway.
        await apply_binding_from_folder(db, deck_id, folder)
        await db.commit()
        deck = (await ac.get(f"/api/decks/{deck_id}")).json()
        assert deck["binds_copies"] is True, "the sync overwrote a hand-set decision"

        # Clearing hands the deck back to its folder rather than freezing the
        # current value — those are different statements about who decides.
        deck = (await ac.put(f"/api/decks/{deck_id}/user-fields",
                             json={"binds_copies_override": None})).json()
        assert deck["binds_copies_override"] is None
        assert deck["binds_copies"] is False


@pytest.mark.anyio
async def test_the_deck_list_and_the_deck_page_agree_about_binding():
    """The bracket disagreed between these two readers for a whole deploy
    (0.47.0 -> 0.47.1). One helper, asked twice."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.services.sync_service import apply_binding_from_folder

    folder = DEFAULT_NON_BINDING_FOLDERS[1]
    db = await get_db()
    deck_id = await insert_deck(db, "Shelved", folder=folder)
    await apply_binding_from_folder(db, deck_id, folder)
    await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        page = (await ac.get(f"/api/decks/{deck_id}")).json()
        listed = next(d for d in (await ac.get("/api/decks/")).json() if d["id"] == deck_id)

    assert page["binds_copies"] == listed["binds_copies"] is False
