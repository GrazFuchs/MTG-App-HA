"""Logging a played game from outside the web UI (HA service, voice, later the
game-logger form).

Deck resolution accepts a name because that is what a voice command or an
automation carries — "log a win with Atraxa" — while the UI always knows the id.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

import aiosqlite

from ..models.schemas import DeckGameCreate

logger = logging.getLogger(__name__)

# Names offered back when a lookup fails, so the caller can see what exists.
MAX_CANDIDATES = 10

#: How long after the previous game a new one still belongs to the same match.
#:
#: ⚠️ **This is a judgement, not a rule.** Ninety minutes covers a best-of-three
#: with a break in it; two separate Bo1 games against the same person on the
#: same evening would be pulled together wrongly. That is the deliberate error:
#: a wrong grouping is corrected with one click, while an extra mandatory field
#: stops the game being logged at all. The whole point of Sprint 15 is that a
#: match costs **no** extra typing — three bookings in a row are a match.
#:
#: The fetchlog measurement is the reason it is built this way: 8 walks in 7
#: days through a one-tap NFC tag, against 1 training session and 0 meals
#: through a web form, over three months. What has a button gets used.
MATCH_WINDOW_MINUTES = 90


class DeckLookupError(Exception):
    """Deck could not be resolved to exactly one deck."""

    def __init__(self, message: str, candidates: list[str] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


async def resolve_deck(
    db: aiosqlite.Connection, deck: str | int | None = None, deck_id: int | None = None
) -> tuple[int, str]:
    """Resolve a deck id or name to ``(id, name)``.

    Names match case-insensitively: exact first, then unique substring.  An
    ambiguous name raises rather than guessing — logging a game against the
    wrong deck is worse than asking again.
    """
    if deck_id is None and isinstance(deck, int):
        deck_id = deck
    elif deck_id is None and isinstance(deck, str) and deck.strip().isdigit():
        deck_id = int(deck.strip())

    if deck_id is not None:
        cursor = await db.execute("SELECT id, name FROM decks WHERE id = ?", (deck_id,))
        row = await cursor.fetchone()
        if row is None:
            raise DeckLookupError(f"No deck with id {deck_id}")
        return row["id"], row["name"]

    name = (deck or "").strip() if isinstance(deck, str) else ""
    if not name:
        raise DeckLookupError("deck or deck_id is required")

    cursor = await db.execute(
        "SELECT id, name FROM decks WHERE LOWER(name) = LOWER(?) ORDER BY id", (name,)
    )
    rows = await cursor.fetchall()

    if not rows:
        cursor = await db.execute(
            "SELECT id, name FROM decks WHERE name LIKE ? ORDER BY LENGTH(name), id",
            (f"%{name}%",),
        )
        rows = await cursor.fetchall()

    if not rows:
        cursor = await db.execute(
            "SELECT name FROM decks ORDER BY name LIMIT ?", (MAX_CANDIDATES,)
        )
        known = [r["name"] for r in await cursor.fetchall()]
        raise DeckLookupError(f"No deck matching {name!r}", known)

    if len(rows) > 1:
        raise DeckLookupError(
            f"{name!r} matches {len(rows)} decks — be more specific",
            [r["name"] for r in rows[:MAX_CANDIDATES]],
        )

    return rows[0]["id"], rows[0]["name"]


def normalize_opponent(opponents: str | None) -> str:
    """The key two games are matched on. Empty means "do not group"."""
    return " ".join((opponents or "").split()).lower()


async def default_pod_size(db: aiosqlite.Connection, deck_id: int) -> int:
    """What this deck's format usually seats. Four is only right for Commander."""
    from . import formats

    cursor = await db.execute("SELECT format FROM decks WHERE id = ?", (deck_id,))
    row = await cursor.fetchone()
    return formats.spec(row["format"] if row else None).rules.default_pod_size


async def renumber_match(db: aiosqlite.Connection, match_id: str | None) -> None:
    """Number a match's games 1, 2, 3 ... in the order they were played.

    Called after anything that changes which games a match holds, so
    `game_in_match` is derived rather than remembered. A match left holding one
    game is dissolved back into a single game: "match" is a statement about a
    group, and a group of one is just a game.
    """
    if not match_id:
        return
    cursor = await db.execute(
        "SELECT id FROM deck_games WHERE match_id = ? ORDER BY played_at, id",
        (match_id,),
    )
    ids = [row["id"] for row in await cursor.fetchall()]
    if len(ids) < 2:
        for game_id in ids:
            await db.execute(
                "UPDATE deck_games SET match_id = NULL, game_in_match = NULL WHERE id = ?",
                (game_id,),
            )
        return
    for position, game_id in enumerate(ids, start=1):
        await db.execute(
            "UPDATE deck_games SET game_in_match = ? WHERE id = ?", (position, game_id)
        )


async def _match_for_new_game(
    db: aiosqlite.Connection, deck_id: int, opponents: str, played_at: str
) -> str | None:
    """Find or open the match this game belongs to. Returns its id, or None.

    The rule in one sentence: **a game booked within the window against the
    same opponent with the same deck continues that match.** No question, no
    field, no extra tap.

    Two things follow from that, and both are deliberate:

    **The second game creates the match and adopts the first.** A lone game
    stays NULL, because until there is a second one there is nothing to group.
    Deciding at the first game would mean deciding before anyone could know.

    **No opponent name, no grouping.** Guessing from the timestamp alone would
    merge two unrelated games played back to back, and a wrong merge is the one
    error that is not obvious afterwards.

    The window is measured against `created_at` (when it was booked), because
    `played_at` is a date with no time in it at all.
    """
    key = normalize_opponent(opponents)
    if not key:
        return None

    cursor = await db.execute(
        f"""SELECT id, match_id, opponents FROM deck_games
            WHERE deck_id = ? AND played_at = ?
              AND created_at >= datetime('now', '-{MATCH_WINDOW_MINUTES} minutes')
            ORDER BY created_at DESC, id DESC
            LIMIT 5""",
        (deck_id, played_at),
    )
    for row in await cursor.fetchall():
        if normalize_opponent(row["opponents"]) != key:
            continue
        if row["match_id"]:
            return row["match_id"]
        match_id = uuid.uuid4().hex[:16]
        await db.execute(
            "UPDATE deck_games SET match_id = ?, game_in_match = 1 WHERE id = ?",
            (match_id, row["id"]),
        )
        return match_id
    return None


async def insert_game(
    db: aiosqlite.Connection, deck_id: int, game: DeckGameCreate
) -> int:
    """Write one game. **The only INSERT into `deck_games` in the app.**

    Both callers used to write their own: the web form through the router, and
    Home Assistant through `log_game`. Two booking paths that drift apart is
    this codebase's most expensive recurring mistake -- 0.45.0 had two booking
    paths, the surplus had two readings, the bracket had three readers -- so
    the pod-size default and the match grouping live here, where neither caller
    can skip them. A test fails if a second INSERT appears anywhere else.
    """
    played_at = (game.played_at or "").strip() or date.today().isoformat()
    pod_size = game.pod_size
    if pod_size is None:
        pod_size = await default_pod_size(db, deck_id)

    if "match_id" in game.model_fields_set:
        # An explicit null means "start fresh" -- the way a wrong grouping is
        # undone. An explicit id joins that match.
        match_id = game.match_id
    else:
        match_id = await _match_for_new_game(db, deck_id, game.opponents, played_at)

    cursor = await db.execute(
        """INSERT INTO deck_games
        (deck_id, played_at, result, opponents, pod_size, on_play,
         mulligans, missed_land_drops, turns, what_worked, what_didnt, notes,
         match_id, sideboard_notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (deck_id, played_at, game.result, game.opponents, pod_size,
         int(game.on_play), game.mulligans, game.missed_land_drops, game.turns,
         game.what_worked, game.what_didnt, game.notes,
         match_id, game.sideboard_notes),
    )
    game_id = cursor.lastrowid
    # Numbered from the group, never counted up by hand: the number is a fact
    # about the match, and a match can be regrouped afterwards.
    await renumber_match(db, match_id)
    await db.commit()
    return game_id


async def match_summary(db: aiosqlite.Connection, match_id: str | None) -> str:
    """Wins-losses of a match as a string, or "" when the game stands alone.

    Computed, never stored: a saved match result could disagree with the games
    it came from, and then there would be two answers and no way to tell which
    one is real.
    """
    if not match_id:
        return ""
    cursor = await db.execute(
        "SELECT result FROM deck_games WHERE match_id = ?", (match_id,)
    )
    results = [row["result"] for row in await cursor.fetchall()]
    wins = sum(1 for r in results if r == "win")
    losses = sum(1 for r in results if r == "loss")
    return f"{wins}-{losses}"


async def log_game(db: aiosqlite.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a payload, resolve its deck and insert the game.

    Raises :class:`DeckLookupError` for deck problems and
    :class:`pydantic.ValidationError` for bad field values.
    """
    fields = {k: v for k, v in payload.items() if k not in ("deck", "deck_id")}
    game = DeckGameCreate(**fields)
    deck_id, deck_name = await resolve_deck(db, payload.get("deck"), payload.get("deck_id"))

    played_at = (game.played_at or "").strip() or date.today().isoformat()
    game_id = await insert_game(db, deck_id, game)

    cursor = await db.execute(
        "SELECT match_id, game_in_match, pod_size FROM deck_games WHERE id = ?",
        (game_id,),
    )
    row = await cursor.fetchone()

    logger.info("Logged %s for deck %s (%d)", game.result, deck_name, deck_id)
    return {
        "status": "logged",
        "game_id": game_id,
        "deck_id": deck_id,
        "deck_name": deck_name,
        "result": game.result,
        "played_at": played_at,
        "pod_size": row["pod_size"],
        # Reported back so the caller can *see* that the grouping took. The
        # mechanism is invisible otherwise, and an invisible rule is one nobody
        # trusts -- which is why the status sensor says "Match 1-1".
        "match_id": row["match_id"],
        "game_in_match": row["game_in_match"],
        "match_score": await match_summary(db, row["match_id"]),
    }
