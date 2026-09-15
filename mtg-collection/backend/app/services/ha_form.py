"""The HA game-logger form: input entities the add-on owns.

Instead of asking the user to build the form from HA helpers, the add-on
publishes `select`/`number`/`switch`/`text`/`button` entities itself.  The deck
list therefore stays in sync with the database on its own, and the dashboard
card needs no templating: pressing the button makes the add-on read the values
it is already holding and write the game.

Field values are persisted (`ha_form_state`), so a half-filled form survives an
add-on restart.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import aiosqlite

from ..models.schemas import DeckGameCreate
from .ha_entities import Entity

logger = logging.getLogger(__name__)

FORM_DEVICE_INFO: dict[str, Any] = {
    "identifiers": ["mtg_game_logger"],
    "name": "MTG Game Logger",
    "manufacturer": "mtg-collection-ha",
    "model": "Game Logger",
}

# HA caps a `text` entity — and any entity state — at 255 characters, which is
# below what the DeckGame model allows for opponents (300) and notes (1000).
# Longer texts stay a web-UI affair.
TEXT_MAX = 255

# A dropdown beyond this is unusable; decks are sorted by name and cut off.
MAX_DECK_OPTIONS = 200

# Marks "no deck chosen yet" in a select, which cannot hold an empty option.
NO_DECK = "—"


@dataclass(frozen=True)
class FormField:
    """One input in the form."""

    key: str
    name: str
    component: str
    default: str
    icon: str = ""
    options: list[str] = field(default_factory=list)
    min: int = 0
    max: int = 0
    step: int = 1

    @property
    def entity_key(self) -> str:
        return f"log_{self.key}"


FIELDS: list[FormField] = [
    FormField("deck", "Deck", "select", NO_DECK, icon="mdi:cards-playing-outline"),
    FormField(
        "result", "Result", "select", "win", icon="mdi:flag-checkered",
        options=["win", "loss", "draw"],
    ),
    FormField("pod_size", "Pod Size", "number", "4", icon="mdi:account-group", min=1, max=8),
    FormField("on_play", "On the Play", "switch", "OFF", icon="mdi:play-circle-outline"),
    FormField("mulligans", "Mulligans", "number", "0", icon="mdi:reload", min=0, max=10),
    FormField(
        "missed_land_drops", "Missed Land Drops", "number", "0",
        icon="mdi:image-broken-variant", min=0, max=50,
    ),
    FormField("turns", "Turns", "number", "0", icon="mdi:timer-outline", min=0, max=100),
    FormField("opponents", "Opponents", "text", "", icon="mdi:account-multiple"),
    # The only field Sprint 15 adds. The match itself arrives through the time
    # window and costs no input at all -- a second field ("is this game two?")
    # would be exactly the extra step that makes a logging path go unused.
    # Stays empty for Commander, where there is nothing to sideboard.
    FormField("sideboard", "Sideboard", "text", "", icon="mdi:swap-horizontal"),
    FormField("notes", "Notes", "text", "", icon="mdi:note-text-outline"),
]

FIELDS_BY_KEY = {f.key: f for f in FIELDS}

SUBMIT_KEY = "submit"
STATUS_KEY = "status"


def state_topic(prefix: str, key: str) -> str:
    return f"{prefix}/form/{key}"


def command_topic(prefix: str, key: str) -> str:
    return f"{state_topic(prefix, key)}/set"


def command_topic_filter(prefix: str) -> str:
    return f"{prefix}/form/+/set"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def _field_entity(spec: FormField, prefix: str, deck_options: list[str]) -> Entity:
    extra: dict[str, Any] = {"command_topic": command_topic(prefix, spec.key)}

    if spec.component == "select":
        extra["options"] = deck_options if spec.key == "deck" else spec.options
    elif spec.component == "number":
        extra.update({"min": spec.min, "max": spec.max, "step": spec.step, "mode": "box"})
    elif spec.component == "switch":
        extra.update({"payload_on": "ON", "payload_off": "OFF"})
    elif spec.component == "text":
        extra.update({"max": TEXT_MAX, "mode": "text"})

    return Entity(
        key=spec.entity_key,
        name=f"Log {spec.name}",
        component=spec.component,
        state_topic=state_topic(prefix, spec.key),
        icon=spec.icon,
        device=FORM_DEVICE_INFO,
        extra=extra,
    )


def form_entities(prefix: str, deck_options: list[str]) -> list[Entity]:
    """Every entity of the game-logger device."""
    entities = [_field_entity(spec, prefix, deck_options) for spec in FIELDS]

    entities.append(Entity(
        key=f"log_{SUBMIT_KEY}",
        name="Log Game",
        component="button",
        has_state=False,
        icon="mdi:content-save-check",
        device=FORM_DEVICE_INFO,
        extra={
            "command_topic": command_topic(prefix, SUBMIT_KEY),
            "payload_press": "PRESS",
        },
    ))
    entities.append(Entity(
        key=f"log_{STATUS_KEY}",
        name="Log Status",
        state_topic=state_topic(prefix, STATUS_KEY),
        icon="mdi:information-outline",
        device=FORM_DEVICE_INFO,
    ))
    return entities


# ---------------------------------------------------------------------------
# Deck options
# ---------------------------------------------------------------------------


async def deck_options(db: aiosqlite.Connection) -> tuple[list[str], dict[str, int]]:
    """Dropdown labels and their label → deck id mapping.

    Decks sharing a name get their id appended, so every label resolves to
    exactly one deck.
    """
    cursor = await db.execute(
        "SELECT id, name FROM decks ORDER BY LOWER(name), id LIMIT ?", (MAX_DECK_OPTIONS,)
    )
    rows = await cursor.fetchall()

    counts: dict[str, int] = {}
    for r in rows:
        name = (r["name"] or "").strip() or f"Deck {r['id']}"
        counts[name] = counts.get(name, 0) + 1

    labels = [NO_DECK]
    mapping: dict[str, int] = {}
    for r in rows:
        name = (r["name"] or "").strip() or f"Deck {r['id']}"
        label = f"{name} (#{r['id']})" if counts[name] > 1 else name
        labels.append(label)
        mapping[label] = r["id"]

    cursor = await db.execute("SELECT COUNT(*) FROM decks")
    total = (await cursor.fetchone())[0]
    if total > MAX_DECK_OPTIONS:
        logger.warning(
            "%d decks exceed the %d option limit of the deck selector", total, MAX_DECK_OPTIONS
        )

    return labels, mapping


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def defaults() -> dict[str, str]:
    return {spec.key: spec.default for spec in FIELDS}


async def load_state(db: aiosqlite.Connection) -> dict[str, str]:
    """Stored field values, filled up with defaults."""
    values = defaults()
    cursor = await db.execute("SELECT field, value FROM ha_form_state")
    for row in await cursor.fetchall():
        if row["field"] in values:
            values[row["field"]] = row["value"]
    return values


async def _store(db: aiosqlite.Connection, values: dict[str, str]) -> None:
    for key, value in values.items():
        await db.execute(
            """INSERT INTO ha_form_state (field, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(field) DO UPDATE
               SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
            (key, value),
        )
    await db.commit()


def coerce(spec: FormField, raw: str, valid_options: list[str] | None = None) -> str:
    """Normalise an incoming command payload to the value we store.

    Raises ValueError when the payload cannot be used at all — HA is then left
    showing the old value rather than a bogus one.
    """
    raw = (raw or "").strip()

    if spec.component == "select":
        options = valid_options if valid_options is not None else spec.options
        if raw not in options:
            raise ValueError(f"{raw!r} is not one of {options}")
        return raw

    if spec.component == "number":
        try:
            number = int(float(raw))
        except ValueError as exc:
            raise ValueError(f"{raw!r} is not a number") from exc
        return str(max(spec.min, min(spec.max, number)))

    if spec.component == "switch":
        return "ON" if raw.upper() in ("ON", "TRUE", "1") else "OFF"

    return raw[:TEXT_MAX]


async def set_field(db: aiosqlite.Connection, key: str, raw: str) -> str:
    """Apply one incoming command and return the stored value."""
    spec = FIELDS_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Unknown form field {key!r}")

    options = None
    if spec.key == "deck":
        options, _ = await deck_options(db)

    value = coerce(spec, raw, options)
    await _store(db, {key: value})

    if spec.key == "deck":
        await _follow_deck(db, value)
    return value


async def apply_command(db: aiosqlite.Connection, key: str, raw: str) -> dict[str, str]:
    """Apply one command and return **every** field value that changed.

    ⚠️ Not just the one that was commanded. Picking a deck also moves the pod
    size, and a value the add-on changes but never publishes is a value Home
    Assistant does not have: the database would say 2 while the dashboard kept
    showing 4, and the next submit would quietly take the number nobody could
    see. Found by clicking the real dropdown against the real add-on -- the
    unit tests were all green, because they read the database.

    Same class as the `json_attributes` trap in the HA packages: the state
    changed, nothing announced it, and everything looked fine.
    """
    before = await load_state(db)
    await set_field(db, key, raw)
    after = await load_state(db)
    return {k: v for k, v in after.items() if before.get(k) != v}


async def _follow_deck(db: aiosqlite.Connection, label: str) -> None:
    """Move the pod size to what the chosen deck's format usually seats.

    Four players is right for Commander and wrong for everything played 1v1,
    and a form that starts wrong every time is a form whose value gets
    corrected by hand until one day it does not -- and then the log holds a
    four-player Standard game.

    Only on the deck change: a value set by hand afterwards stands until the
    next deck is picked. Overwriting it on every publish would make the field
    unusable, which is the mirror image of the same mistake.
    """
    from . import formats
    from .game_log import default_pod_size

    if not label or label == NO_DECK:
        return
    _labels, mapping = await deck_options(db)
    deck_id = mapping.get(label)
    if deck_id is None:
        return
    await _store(db, {"pod_size": str(await default_pod_size(db, deck_id))})

    # A format with no sideboard has nothing to write there, and a leftover
    # note from the last Standard match must not ride along into a Commander
    # game.
    cursor = await db.execute("SELECT format FROM decks WHERE id = ?", (deck_id,))
    row = await cursor.fetchone()
    if row is not None and not formats.spec(row["format"]).rules.matches:
        await _store(db, {"sideboard": ""})


async def reset(db: aiosqlite.Connection) -> dict[str, str]:
    """Clear the form back to its defaults (after a successful submit)."""
    values = defaults()
    await _store(db, values)
    return values


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


async def submit(db: aiosqlite.Connection) -> dict[str, Any]:
    """Write the currently held form values as a game.

    Returns the :func:`services.game_log.log_game` result on success, or
    ``{"error": …}`` — the caller surfaces both through the status sensor.
    """
    from .game_log import DeckLookupError, log_game

    values = await load_state(db)
    label = values.get("deck", NO_DECK)
    if not label or label == NO_DECK:
        return {"error": "No deck selected"}

    _labels, mapping = await deck_options(db)
    deck_id = mapping.get(label)
    if deck_id is None:
        # The deck was renamed or deleted while it sat selected in the form.
        return {"error": f"Deck {label!r} no longer exists — pick it again"}

    payload = {
        "deck_id": deck_id,
        "result": values["result"],
        "pod_size": int(values["pod_size"]),
        "on_play": values["on_play"] == "ON",
        "mulligans": int(values["mulligans"]),
        "missed_land_drops": int(values["missed_land_drops"]),
        "turns": int(values["turns"]),
        "opponents": values["opponents"],
        "notes": values["notes"],
        "sideboard_notes": values.get("sideboard", ""),
    }

    try:
        result = await log_game(db, payload)
    except DeckLookupError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("Game logger submit failed")
        return {"error": f"{type(exc).__name__}: {exc}"}

    await reset(db)
    return result


def status_text(result: dict[str, Any]) -> str:
    """One-line outcome for the status sensor (HA states cap at 255 chars)."""
    if "error" in result:
        return f"Error: {result['error']}"[:255]
    line = (
        f"Logged {result['result']} with {result['deck_name']} on {result['played_at']}"
    )
    # The grouping happens silently, by a clock nobody sees. Saying "Match 1-1"
    # here is how you find out it took -- and, more importantly, how you find
    # out it took when it should not have, while you can still undo it.
    if result.get("match_id"):
        line += (
            f" - game {result.get('game_in_match')} of the match,"
            f" now {result.get('match_score')}"
        )
    return line[:255]


def validate_bounds() -> None:
    """Assert the form bounds match the model the games are validated against.

    Called by the tests: a form that lets you pick a value the API rejects
    would fail only on submit, which is the worst place to find out.
    """
    model_fields = DeckGameCreate.model_fields
    for spec in FIELDS:
        if spec.component != "number":
            continue
        if spec.key not in model_fields:
            continue
        meta = model_fields[spec.key].metadata
        limits = {type(m).__name__: m for m in meta}
        ge = getattr(limits.get("Ge"), "ge", None)
        le = getattr(limits.get("Le"), "le", None)
        assert ge is None or spec.min >= ge, f"{spec.key}: min {spec.min} < model {ge}"
        assert le is None or spec.max <= le, f"{spec.key}: max {spec.max} > model {le}"
