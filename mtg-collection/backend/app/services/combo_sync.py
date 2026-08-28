"""Combo sync service — fetch and cache Spellbook combos per deck.

Two things about the Spellbook answer shape decide how this file is written,
both checked against the live API on 2026-08-28 rather than assumed:

* `/find-my-combos/` buckets its answer as `results.included` (every card
  present) and `results.almostIncluded` (one card short), plus three buckets
  that would require changing the deck's colours or commander. Only the first
  two are stored; a combo that needs a different colour identity is not a
  suggestion, it is a different deck.
* **There is no `missingCards` field.** A combo carries `uses`, the cards it
  needs, and that is all — which is why every one of the cached partial combos
  had an empty missing-card list. What is missing has to be derived here: the
  cards a combo uses, minus the cards the deck holds.
"""
import asyncio
import json
import logging
from typing import Any, Iterable

from ..database import get_db
from ..clients.spellbook import spellbook

logger = logging.getLogger(__name__)

#: How long a deck's combo answer is treated as current. A deck that changed is
#: re-asked by the sync anyway; this is the interval for the ones that did not,
#: because Spellbook keeps adding variants to an unchanged decklist.
COMBO_REFRESH_AFTER_DAYS = 14

#: Pause between decks in a bulk run. Spellbook publishes no rate limit; this is
#: the same courtesy interval the per-deck sync already used.
BULK_PACING_SECONDS = 1.0


def _card_keys(name: str) -> set[str]:
    """Every spelling a card name might be matched under.

    A double-faced card is "Valakut Awakening // Valakut Stoneforge" in one
    source and "Valakut Awakening" in the other, so both halves count as the
    same card for the purpose of "is it in the deck".
    """
    name = (name or "").strip().lower()
    if not name:
        return set()
    keys = {name}
    if "//" in name:
        keys.update(part.strip() for part in name.split("//") if part.strip())
    return keys


def _deck_card_keys(names: Iterable[str]) -> set[str]:
    keys: set[str] = set()
    for name in names:
        keys |= _card_keys(name)
    return keys


def _missing_from(card_names: list[str], deck_keys: set[str]) -> list[str]:
    """The combo's cards the deck does not hold."""
    return [n for n in card_names if n and not (_card_keys(n) & deck_keys)]


def _extract_combo_fields(
    combo: dict[str, Any], is_partial: bool, deck_keys: set[str]
) -> dict[str, Any]:
    """Normalize a Spellbook combo response to our DB schema."""
    # Spellbook can use various field names depending on version
    combo_id = str(combo.get("id", combo.get("variant_id", "")))
    cards = combo.get("uses", combo.get("cards", []))
    # Cards can be list of dicts (nested card.name) or list of strings
    if cards and isinstance(cards[0], dict):
        card_names = [
            c.get("card", {}).get("name", "") if isinstance(c.get("card"), dict)
            else c.get("card", c.get("name", ""))
            for c in cards
        ]
    else:
        card_names = [str(c) for c in cards]

    results = combo.get("produces", combo.get("results", combo.get("result", [])))
    if results and isinstance(results[0], dict):
        result_list = [
            r.get("feature", {}).get("name", "") if isinstance(r.get("feature"), dict)
            else r.get("name", str(r))
            for r in results
        ]
    elif isinstance(results, str):
        result_list = [results]
    else:
        result_list = [str(r) for r in results]

    name = " + ".join(card_names[:3])
    if len(card_names) > 3:
        name += f" +{len(card_names) - 3}"

    color_identity = combo.get("identity", combo.get("color_identity", ""))
    if isinstance(color_identity, list):
        color_identity = "".join(color_identity)

    prerequisites = combo.get("otherPrerequisites", combo.get("prerequisites", ""))
    steps = combo.get("description", combo.get("steps", ""))

    missing_cards: list[str] = []
    if is_partial:
        missing_cards = _missing_from(card_names, deck_keys)
        if not missing_cards:
            # Nothing named is missing, so what the deck lacks is one of the
            # combo's templates ("any creature with flying"). Naming the
            # template is less useful than naming a card, but it is true, and
            # an empty list would claim the combo is complete.
            missing_cards = [
                t.get("template", {}).get("name", "")
                for t in combo.get("requires", [])
                if isinstance(t, dict) and isinstance(t.get("template"), dict)
            ]
            missing_cards = [m for m in missing_cards if m]

    return {
        "combo_id": combo_id,
        "name": name,
        "color_identity": color_identity,
        "cards_json": json.dumps(card_names),
        "result_json": json.dumps(result_list),
        "prerequisites": prerequisites if isinstance(prerequisites, str) else json.dumps(prerequisites),
        "steps": steps if isinstance(steps, str) else json.dumps(steps),
        "is_partial": 1 if is_partial else 0,
        "missing_cards_json": json.dumps(missing_cards),
    }


async def sync_combos_for_deck(deck_id: int) -> int:
    """Detect and store combos for a single deck.

    Returns the count of combos found (full + partial) and stamps the deck as
    asked — including when the answer is zero, which is a result and not a
    failure. A Spellbook error is **raised**, not turned into a 0: the two used
    to be indistinguishable, and a deck with no combos looked exactly like a
    deck the sync had never reached.
    """
    db = await get_db()

    # 1. Load deck card names
    cursor = await db.execute(
        """SELECT c.name FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ?""",
        (deck_id,),
    )
    rows = await cursor.fetchall()
    card_names = [r[0] for r in rows]

    if not card_names:
        logger.warning("Deck %d has no cards, skipping combo sync", deck_id)
        return 0

    # Get commander name
    cursor = await db.execute(
        "SELECT commander_name FROM decks WHERE id = ?", (deck_id,)
    )
    deck_row = await cursor.fetchone()
    commander_name = deck_row["commander_name"] if deck_row else None

    # 2. Call Spellbook API
    data = await spellbook.find_combos_in_decklist(card_names, commander_name)

    included = data.get("included", [])
    almost = data.get("almost_included", [])

    # The commander counts as being in the deck for "is this card missing",
    # even though it travels in its own field rather than the main list.
    deck_keys = _deck_card_keys([*card_names, commander_name or ""])

    # 3. Replace this deck's cached combos
    await db.execute("DELETE FROM deck_combos WHERE deck_id = ?", (deck_id,))

    # 4. Insert new combos
    count = 0
    for combo, is_partial in [(c, False) for c in included] + [(c, True) for c in almost]:
        fields = _extract_combo_fields(combo, is_partial, deck_keys)
        await db.execute(
            """INSERT OR IGNORE INTO deck_combos
            (deck_id, combo_id, name, color_identity, cards_json, result_json,
             prerequisites, steps, is_partial, missing_cards_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (deck_id, fields["combo_id"], fields["name"], fields["color_identity"],
             fields["cards_json"], fields["result_json"], fields["prerequisites"],
             fields["steps"], fields["is_partial"], fields["missing_cards_json"]),
        )
        count += 1

    await db.execute(
        "UPDATE decks SET combos_synced_at = CURRENT_TIMESTAMP WHERE id = ?", (deck_id,)
    )
    await db.commit()
    logger.info(
        "Combo sync deck %d: %d combos (%d complete, %d one card short)",
        deck_id, count, len(included), len(almost),
    )
    return count


async def sync_combos_for_stale_decks(
    max_decks: int | None = None, force: bool = False
) -> dict[str, Any]:
    """Ask Spellbook about every deck that is due, one deck at a time.

    "Due" means never asked, or asked longer than `COMBO_REFRESH_AFTER_DAYS`
    ago. A deck the running sync has just handled is fresh by that measure and
    is skipped here, so this costs nothing when there is nothing to do.
    """
    db = await get_db()
    where = "1=1" if force else (
        "combos_synced_at IS NULL"
        f" OR combos_synced_at < datetime('now', '-{COMBO_REFRESH_AFTER_DAYS} days')"
    )
    cursor = await db.execute(
        f"""SELECT id, name FROM decks
        WHERE {where}
        ORDER BY COALESCE(combos_synced_at, ''), id"""
        + (" LIMIT ?" if max_decks else ""),
        (max_decks,) if max_decks else (),
    )
    due = await cursor.fetchall()
    if not due:
        return {"status": "completed", "decks": 0, "combos": 0, "failed": 0, "results": []}

    results: list[dict[str, Any]] = []
    combos = 0
    failed = 0
    for index, row in enumerate(due):
        if index:
            await asyncio.sleep(BULK_PACING_SECONDS)
        try:
            count = await sync_combos_for_deck(row["id"])
            combos += count
            results.append({"deck_id": row["id"], "name": row["name"], "combos": count})
        except Exception as exc:
            # Named, with the deck it belongs to. The old best-effort wrapper
            # turned this into a 0, which the caller could not tell apart from
            # "asked, none found".
            failed += 1
            logger.warning(
                "Combo sync failed for deck %d (%s): %s", row["id"], row["name"], exc
            )
            results.append({"deck_id": row["id"], "name": row["name"], "error": str(exc)})

    logger.info(
        "Combo top-up: %d decks asked, %d combos cached, %d failed",
        len(due), combos, failed,
    )
    return {
        "status": "completed",
        "decks": len(due),
        "combos": combos,
        "failed": failed,
        "results": results,
    }
