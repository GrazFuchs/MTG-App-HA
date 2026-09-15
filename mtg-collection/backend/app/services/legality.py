"""Is this deck legal in its own format?

What a 60-card deck gets instead of a bracket and a power score. Those two say
what a Commander deck is *capable of*; this says whether the deck is a deck at
all — the right size, the right number of copies, no card the format has banned.
Facts rather than judgements, and the only one of the three that applies to every
format.

The data has been complete for months and nobody read it: **8022 of 8022 cards
carry Scryfall's `legalities` object**, refreshed weekly by `card_enrichment`,
and not one consumer looked at it. Same shape as `next_due_days` sitting unread
on the dog sensor for two weeks — a fact in the database is not monitoring.

Four rules, and each one has a trap in it:

**Size.** Counted over the main deck only, which is why `board` had to exist
first (Sprint 12). A Commander deck is exactly 100 *including* the commander; a
constructed deck is *at least* 60 with no upper bound, because playing 63 is
legal and only ever a choice.

**Copies.** Four of any card, one in singleton formats — except basic lands, and
except the cards that say otherwise in their own rules text. Deck 3 holds **20x
Rat Colony** in a singleton format and is entirely legal, because the card reads
"A deck can have any number of cards named Rat Colony". A check without that
exemption reports nineteen violations on a correct deck, and a checker that cries
wolf gets switched off rather than fixed. The exemption is read from the oracle
text, not from a list of names: a list is the part that goes stale.

**Legality.** Straight from Scryfall's key for this format. `restricted` is a
Vintage answer and means "legal, but only one copy" — it is folded into the copy
limit rather than reported as its own kind of wrong.

**Unknown is not legal.** A card whose `legalities` we never fetched, or whose
object has no key for this format, is counted separately and reported. It is
neither passed nor failed: the same rule the bracket uses for cards Spellbook
does not classify. An unknown counted as legal is how a checker quietly stops
checking.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..database import get_db
from . import formats
from .queries import BASIC_LAND_NAMES, token_exclusion_sql

logger = logging.getLogger(__name__)

#: Cards that lift their own copy limit say so in their rules text. Matching the
#: sentence rather than keeping a list of names means a new one works the day it
#: is printed — the same reason mass land denial is asked of Spellbook instead of
#: transcribed from a 2024 bundle.
_ANY_NUMBER = re.compile(
    r"a deck can have any number of cards named", re.IGNORECASE
)

#: Scryfall's answers. Anything else is treated as unknown rather than guessed at.
_LEGAL = "legal"
_RESTRICTED = "restricted"
_KNOWN_BAD = ("banned", "not_legal")

_BASICS_LOWER = {name.lower() for name in BASIC_LAND_NAMES}


def _exempt_from_copy_limit(name: str, oracle_text: str | None) -> bool:
    """Basic lands, and cards that grant themselves an exemption."""
    if (name or "").lower() in _BASICS_LOWER:
        return True
    # Snow-covered basics and any future basic land type: the type line would be
    # the cleaner test, but the name list already covers every printed one and a
    # card called "Wastes" is a basic land whatever its type line says here.
    return bool(_ANY_NUMBER.search(oracle_text or ""))


async def check_deck(deck_id: int) -> dict[str, Any]:
    """Check one deck against its format's rules. Never raises on data gaps."""
    db = await get_db()

    cursor = await db.execute("SELECT id, name, format FROM decks WHERE id = ?", (deck_id,))
    deck = await cursor.fetchone()
    if deck is None:
        return {"deck_id": deck_id, "error": "deck not found"}

    spec = formats.spec(deck["format"])
    rules = spec.rules

    # ⚠️ Tokens are not cards. Archidekt lets one sit in a decklist as a
    # reminder of what the deck makes, and the first run of this check reported
    # deck 7 as 104 cards in a 100-card format with three "cards" not legal in
    # Commander — all four of those were token rows.
    cursor = await db.execute(
        f"""SELECT c.name, c.oracle_text, c.legalities, c.type_line,
                  dc.quantity, dc.board, dc.is_commander
           FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = ? AND {token_exclusion_sql("c")}""",
        (deck_id,),
    )
    rows = await cursor.fetchall()

    violations: list[dict[str, Any]] = []
    unknown = 0
    main_count = side_count = maybe_count = 0
    #: Copies per card name, over main + sideboard. The maybeboard is not part
    #: of the deck, so a card sitting there does not count against the limit.
    copies: dict[str, int] = {}
    #: Names that lift their own copy limit (basics, "any number of").
    exempt: set[str] = set()
    #: Names the format restricts to a single copy (Vintage).
    restricted: set[str] = set()

    # ⚠️ A format with no sideboard has no sideboard *pile* either. Archidekt
    # offers the category regardless, and in Commander people use it as a
    # scratch list — deck 20 keeps three cards there, deck 21 one. Reporting
    # that as a rules violation is noise about a habit, so those cards are
    # treated exactly like a maybeboard: outside the deck, not counted, not
    # checked. Where the format *does* have a sideboard, the limit applies.
    side_is_part_of_deck = rules.side_max > 0

    for row in rows:
        board = row["board"] or "main"
        quantity = int(row["quantity"] or 0)
        if board == "main":
            main_count += quantity
        elif board == "side" and side_is_part_of_deck:
            side_count += quantity
        else:
            maybe_count += quantity
            continue

        name = row["name"] or ""
        copies[name] = copies.get(name, 0) + quantity
        if _exempt_from_copy_limit(name, row["oracle_text"]):
            exempt.add(name)

        # --- legality of the card itself ---------------------------------
        if not spec.legality_key:
            continue
        try:
            legalities = json.loads(row["legalities"] or "{}")
        except (TypeError, ValueError):
            legalities = {}
        status = legalities.get(spec.legality_key)
        if status is None:
            unknown += 1
        elif status in _KNOWN_BAD:
            violations.append({
                "kind": "legality",
                "card": name,
                "status": status,
                "board": board,
                "detail": f"{name} is {status.replace('_', ' ')} in {spec.name}",
            })
        elif status == _RESTRICTED:
            # Restricted is a Vintage answer meaning "legal, one copy". It is
            # not reported as its own kind of wrong — it tightens the copy
            # limit below, and only shows up if more than one is played.
            restricted.add(name)

    # --- size ------------------------------------------------------------
    if rules.main_min and main_count < rules.main_min:
        violations.append({
            "kind": "size",
            "detail": (
                f"{main_count} cards in the main deck, {spec.name} needs at "
                f"least {rules.main_min}"
            ),
            "have": main_count, "want": rules.main_min,
        })
    if rules.main_max and main_count > rules.main_max:
        violations.append({
            "kind": "size",
            "detail": (
                f"{main_count} cards in the main deck, {spec.name} allows at "
                f"most {rules.main_max}"
            ),
            "have": main_count, "want": rules.main_max,
        })
    if side_count > rules.side_max:
        violations.append({
            "kind": "sideboard",
            "detail": (
                f"{side_count} cards in the sideboard, {spec.name} allows "
                f"{rules.side_max}"
            ),
            "have": side_count, "want": rules.side_max,
        })

    # --- copies ----------------------------------------------------------
    # A restricted card is capped at one even where it is exempt by name,
    # because the format's restriction is the stricter of the two.
    for name, count in sorted(copies.items()):
        if name in restricted:
            allowed = 1
        elif name in exempt:
            continue
        else:
            allowed = rules.max_copies
        if count > allowed:
            violations.append({
                "kind": "copies",
                "card": name,
                "detail": (
                    f"{count}x {name}, {spec.name} allows {allowed}"
                    + (" (restricted)" if name in restricted else "")
                ),
                "have": count, "want": allowed,
            })

    checked = bool(rules.main_min or rules.main_max or spec.legality_key)
    return {
        "deck_id": deck_id,
        "deck_name": deck["name"],
        "format": spec.name,
        "legality_key": spec.legality_key,
        # False when the format is unknown to us: nothing was checked, so
        # "legal" would be a claim rather than a result.
        "checked": checked,
        "main_count": main_count,
        "side_count": side_count,
        "maybeboard_count": maybe_count,
        "rules": formats.rules_payload(deck["format"]),
        "violations": violations,
        #: Cards with no legality answer for this format. Neither passed nor
        #: failed — shown, so the gap is visible instead of implied.
        "unknown_legality": unknown,
        "legal": checked and not violations,
    }


async def check_and_store(deck_id: int) -> dict[str, Any]:
    """Check a deck and keep the result on the deck row."""
    result = await check_deck(deck_id)
    if "error" in result:
        return result
    db = await get_db()
    await db.execute(
        """UPDATE decks SET legality_json = ?, legality_checked_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (json.dumps(result), deck_id),
    )
    await db.commit()
    return result


async def check_all_decks() -> dict[str, Any]:
    """Re-check every deck. Local SQL, no network.

    Run after a sync (the lists changed) **and** after a Scryfall enrichment
    pass (the legalities changed). The second is the one that matters over time:
    rotation and bans do not touch a deck, they move underneath it, and the
    weekly refresh is the only way they arrive.
    """
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks ORDER BY id")
    deck_ids = [row["id"] for row in await cursor.fetchall()]

    results = []
    for deck_id in deck_ids:
        try:
            results.append(await check_and_store(deck_id))
        except Exception as exc:
            logger.warning("Legality check failed for deck %d: %s", deck_id, exc)
            results.append({"deck_id": deck_id, "error": str(exc)})

    illegal = [r for r in results if r.get("checked") and not r.get("legal")]
    logger.info(
        "Legality check: %d decks, %d checked, %d with violations",
        len(results), sum(1 for r in results if r.get("checked")), len(illegal),
    )
    return {
        "decks": len(results),
        "checked": sum(1 for r in results if r.get("checked")),
        "illegal": len(illegal),
        "results": results,
    }


async def annotate_combos(
    deck_format: str | None, combos: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Mark each partial combo with whether its missing cards are even legal.

    A combo one card short is an upgrade suggestion; a combo one *banned* card
    short is not, and until now nothing said so — Spellbook does not know what
    format the deck is. In Commander this almost never bites, which is why it
    went unnoticed: nearly everything is Commander-legal. In Standard most of
    the card pool is not.

    **Annotated rather than dropped.** "This combo needs a card your format has
    banned" is information; hiding the combo turns it into a question the reader
    has to answer again every time. Callers that want a clean upgrade list read
    `completable`.

    One place, because both the API and the MCP tool need it and two copies of
    "the same thing" is how they drift (0.45.0).
    """
    key = formats.legality_key(deck_format)
    if not key or not combos:
        for combo in combos:
            combo.setdefault("missing_not_legal", [])
            combo.setdefault("completable", True)
        return combos

    wanted = {
        name
        for combo in combos
        for name in (combo.get("missing_cards") or [])
        if name
    }
    if not wanted:
        for combo in combos:
            combo["missing_not_legal"] = []
            combo["completable"] = True
        return combos

    db = await get_db()
    placeholders = ",".join("?" * len(wanted))
    cursor = await db.execute(
        f"""SELECT name, legalities FROM cards
            WHERE name IN ({placeholders}) GROUP BY name""",
        list(wanted),
    )
    status_by_name: dict[str, str | None] = {}
    for row in await cursor.fetchall():
        try:
            status_by_name[row["name"]] = json.loads(row["legalities"] or "{}").get(key)
        except (TypeError, ValueError):
            status_by_name[row["name"]] = None

    for combo in combos:
        missing = combo.get("missing_cards") or []
        # A card we have never seen is unknown, not illegal — the same rule as
        # everywhere else here. Only a card we asked about and got a "no" for
        # counts against the combo.
        illegal = [
            name for name in missing
            if status_by_name.get(name) in _KNOWN_BAD
        ]
        combo["missing_not_legal"] = illegal
        # Completable when at least one missing card could actually be added.
        combo["completable"] = not missing or len(illegal) < len(missing)
    return combos


def stored(raw: str | None) -> dict[str, Any] | None:
    """Parse a stored check, tolerating a row that predates the column."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
