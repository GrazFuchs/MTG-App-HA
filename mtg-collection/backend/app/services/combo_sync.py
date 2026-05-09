"""Combo sync service — fetch and cache Spellbook combos per deck."""
import asyncio
import json
import logging
from typing import Any

from ..database import get_db
from ..clients.spellbook import spellbook

logger = logging.getLogger(__name__)


def _extract_combo_fields(combo: dict[str, Any], is_partial: bool) -> dict[str, Any]:
    """Normalize a Spellbook combo response to our DB schema."""
    # Spellbook can use various field names depending on version
    combo_id = str(combo.get("id", combo.get("variant_id", "")))
    cards = combo.get("uses", combo.get("cards", []))
    # Cards can be list of dicts or list of strings
    if cards and isinstance(cards[0], dict):
        card_names = [c.get("card", {}).get("name", c.get("name", "")) for c in cards]
    else:
        card_names = [str(c) for c in cards]

    results = combo.get("produces", combo.get("results", combo.get("result", [])))
    if results and isinstance(results[0], dict):
        result_list = [r.get("feature", {}).get("name", r.get("name", str(r))) for r in results]
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

    missing_cards = []
    if is_partial:
        missing = combo.get("missingCards", combo.get("missing_cards", []))
        if missing and isinstance(missing[0], dict):
            missing_cards = [m.get("card", {}).get("name", m.get("name", "")) for m in missing]
        else:
            missing_cards = [str(m) for m in missing]

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

    Called automatically after sync_deck. Can also be triggered manually.
    Returns: count of combos found (full + partial).
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
    try:
        data = await spellbook.find_combos_in_decklist(card_names, commander_name)
    except Exception as e:
        logger.error("Spellbook API error for deck %d: %s", deck_id, e)
        return 0

    included = data.get("included", [])
    almost = data.get("almost_included", [])

    # 3. Delete existing combos for this deck
    await db.execute("DELETE FROM deck_combos WHERE deck_id = ?", (deck_id,))

    # 4. Insert new combos
    count = 0
    for combo in included:
        fields = _extract_combo_fields(combo, is_partial=False)
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

    for combo in almost:
        fields = _extract_combo_fields(combo, is_partial=True)
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

    await db.commit()
    logger.info("Synced %d combos for deck %d (%d full, %d partial)",
                count, deck_id, len(included), len(almost))
    return count
