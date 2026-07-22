"""Logging a played game from outside the web UI (HA service, voice, later the
game-logger form).

Deck resolution accepts a name because that is what a voice command or an
automation carries — "log a win with Atraxa" — while the UI always knows the id.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import aiosqlite

from ..models.schemas import DeckGameCreate

logger = logging.getLogger(__name__)

# Names offered back when a lookup fails, so the caller can see what exists.
MAX_CANDIDATES = 10


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


async def log_game(db: aiosqlite.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a payload, resolve its deck and insert the game.

    Raises :class:`DeckLookupError` for deck problems and
    :class:`pydantic.ValidationError` for bad field values.
    """
    fields = {k: v for k, v in payload.items() if k not in ("deck", "deck_id")}
    game = DeckGameCreate(**fields)
    deck_id, deck_name = await resolve_deck(db, payload.get("deck"), payload.get("deck_id"))

    played_at = game.played_at.strip() or date.today().isoformat()
    cursor = await db.execute(
        """INSERT INTO deck_games
        (deck_id, played_at, result, opponents, pod_size, on_play,
         mulligans, missed_land_drops, turns, what_worked, what_didnt, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (deck_id, played_at, game.result, game.opponents, game.pod_size,
         int(game.on_play), game.mulligans, game.missed_land_drops, game.turns,
         game.what_worked, game.what_didnt, game.notes),
    )
    await db.commit()

    logger.info("Logged %s for deck %s (%d)", game.result, deck_name, deck_id)
    return {
        "status": "logged",
        "game_id": cursor.lastrowid,
        "deck_id": deck_id,
        "deck_name": deck_name,
        "result": game.result,
        "played_at": played_at,
    }
