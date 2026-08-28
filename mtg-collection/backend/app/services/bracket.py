"""Compute a deck's WotC bracket from local data, with the evidence for it.

The bracket system Wizards published for Commander sorts a deck by what it is
*capable* of, not by how it feels: game changers, two-card infinite combos, mass
land denial and chained extra turns. All four are now answerable from this
database — game changers from Scryfall (`cards.game_changer`), the combos from
the Spellbook cache (`deck_combos`), and mass land denial and extra turns from
Spellbook's card classification (`cards.mass_land_denial`, `cards.extra_turn`).

Three decisions shape what comes out, and each of them is a limit worth knowing:

**The result is a lower bound, and it only ever spans 2 to 4.** Bracket 1
(Exhibition) and bracket 5 (cEDH) are *declarations*, not measurements: an
Exhibition deck is one built around a bit, and a cEDH deck is one brought to a
tournament. Nothing in a decklist distinguishes either from its neighbour, so
the computation never claims them. That is what `user_bracket` is for.

**The evidence is the feature, not the number.** Every rule that raises the
floor records which cards or combos raised it, so the answer can be argued with.

**Under-detection is possible and is reported.** Spellbook classifies only the
cards in its own combo database — 49 of 88 on a real deck — so a card it does
not know is unclassified rather than clean. A small oracle-text fallback
catches the plainest wordings, and the detail carries the number of cards
nobody classified so the gap is visible instead of implied.
"""
import json
import logging
import re
from typing import Any

from ..database import get_db

logger = logging.getLogger(__name__)

#: The lowest bracket the rules can establish. A deck with none of the four
#: criteria is a bracket 1 or 2 deck and the difference is a matter of intent.
BASE_BRACKET = 2

#: A two-card combo counts as *early* — and so as bracket 4 — when the whole
#: thing can plausibly be assembled and fired by about turn seven, which is the
#: line the bracket guidance draws for brackets 1 to 3. Measured as the mana
#: still owed plus the mana value of the pieces.
#:
#: ⚠️ **This number is a model of "by turn seven", not a quoted rule.** Wizards
#: describes the restriction in words and leaves the reading to the table. Two
#: reference points fix it where it is: Kiki-Jiki (5) + Deceiver Exarch (3) is
#: eight and is treated as an early combo everywhere, while Mikaeus (6) +
#: Triskelion (6) is twelve and is not. Eight mana is roughly seven lands plus
#: a rock. A group that reads it differently changes this one constant.
EARLY_COMBO_MANA_CEILING = 8.0

#: More than this many distinct extra-turn cards reads as a plan rather than a
#: single trick, which the bracket 3 guidance treats as an upgrade.
EXTRA_TURN_CARDS_FOR_B3 = 2

#: Bracket 3 tolerates up to three game changers; a fourth is bracket 4.
GAME_CHANGERS_ALLOWED_AT_B3 = 3

#: An infinite combo that needs more pieces than this is not treated as a
#: bracket-3 signal. The bracket rules name *two-card* combos; this is the
#: allowance for the ones just beyond that line.
#:
#: ⚠️ Calibrated against two real decks, and it is a judgement, not a rule.
#: "Surf n Turf" holds two complete three-card infinites and reads as an
#: upgraded deck — Commander Spellbook independently calls it Ruthless.
#: "Squirreled Away" holds one four-piece engine that makes infinite Food
#: tokens, which wins nothing on its own — and Spellbook calls that deck
#: Exhibition. Three is the line those two put it on.
GENERIC_INFINITE_MAX_CARDS = 3

#: Plain oracle wordings for the two classifications Spellbook may not know.
#: Deliberately narrow: a false positive moves a deck up a bracket, which is
#: worse than missing an exotic card that the classification would have caught.
_MASS_LAND_DENIAL_PATTERNS = re.compile(
    r"destroy all lands"
    r"|destroy all nonbasic lands"
    r"|each player sacrifices (a|an|two|three|\d+|all|X) land"
    r"|return all lands .* to (their|its) owners' hands",
    re.IGNORECASE,
)
_EXTRA_TURN_PATTERN = re.compile(r"takes? an extra turn after this one", re.IGNORECASE)

#: Results that mean the extra turns are being chained rather than taken once.
_INFINITE_TURN_HINTS = ("infinite turn", "infinite extra turn", "extra turns")


def effective_bracket(
    user_bracket: int | None, computed_bracket: int | None, archidekt_bracket: int | None
) -> int | None:
    """The bracket to show, in order of how much it is worth trusting.

    A hand-set value wins because somebody decided it; the computation is a
    reviewed suggestion; the Archidekt import is a mirror of a field that is
    empty on every deck we have ever synced.
    """
    if user_bracket:
        return user_bracket
    if computed_bracket:
        return computed_bracket
    return archidekt_bracket or None


def _combo_cards(cards_json: str | None) -> list[str]:
    try:
        cards = json.loads(cards_json or "[]")
    except (TypeError, ValueError):
        return []
    return [c for c in cards if isinstance(c, str) and c]


#: The card facts the rules read. Shared so a hypothetical card is loaded with
#: exactly the same columns as a real one.
_CARD_COLUMNS = """c.name, c.game_changer, c.mass_land_denial, c.extra_turn,
                   c.oracle_text, c.cmc, c.scryfall_enriched_at"""


async def compute_bracket(
    deck_id: int, extra_card_ids: list[int] | None = None, persist: bool = True
) -> dict[str, Any]:
    """Work out the deck's bracket floor and write it, with the evidence.

    `extra_card_ids` answers "what would this deck be if I added that card"
    without touching the deck — it runs the very same rules over the very same
    columns, which is the only way the answer means anything. Such a run never
    persists.
    """
    db = await get_db()

    cursor = await db.execute(
        f"""SELECT {_CARD_COLUMNS}
        FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ?""",
        (deck_id,),
    )
    cards = list(await cursor.fetchall())
    if extra_card_ids:
        persist = False
        placeholders = ",".join("?" * len(extra_card_ids))
        cursor = await db.execute(
            f"SELECT {_CARD_COLUMNS} FROM cards c WHERE c.id IN ({placeholders})",
            extra_card_ids,
        )
        cards += list(await cursor.fetchall())
    if not cards:
        return {"deck_id": deck_id, "bracket": None, "reason": "deck has no cards"}

    cmc_by_name = {(r["name"] or "").lower(): (r["cmc"] or 0) for r in cards}

    game_changers = sorted({r["name"] for r in cards if r["game_changer"] == 1})

    # Classified by Spellbook, or matched by the narrow oracle fallback.
    mass_land_denial = sorted({
        r["name"] for r in cards
        if r["mass_land_denial"] == 1
        or (r["mass_land_denial"] is None
            and _MASS_LAND_DENIAL_PATTERNS.search(r["oracle_text"] or ""))
    })
    extra_turn_cards = sorted({
        r["name"] for r in cards
        if r["extra_turn"] == 1
        or (r["extra_turn"] is None and _EXTRA_TURN_PATTERN.search(r["oracle_text"] or ""))
    })

    unclassified = sum(1 for r in cards if r["mass_land_denial"] is None)
    unenriched = sum(1 for r in cards if r["scryfall_enriched_at"] is None)

    cursor = await db.execute(
        """SELECT name, cards_json, result_json, mana_value_needed
        FROM deck_combos WHERE deck_id = ? AND is_partial = 0""",
        (deck_id,),
    )
    complete_combos = await cursor.fetchall()

    early_combos: list[str] = []
    late_combos: list[str] = []
    chained_turn_combos: list[str] = []
    for combo in complete_combos:
        names = _combo_cards(combo["cards_json"])
        results = " ".join(_combo_cards(combo["result_json"])).lower()
        if any(hint in results for hint in _INFINITE_TURN_HINTS):
            chained_turn_combos.append(combo["name"] or " + ".join(names))
        if len(names) > 2:
            continue
        owed = combo["mana_value_needed"]
        pieces = sum(cmc_by_name.get(n.lower(), 0) for n in names)
        # A combo whose cost Spellbook did not state is judged on its pieces
        # alone rather than pushed into the higher bracket on a guess.
        total = (owed or 0) + pieces
        label = combo["name"] or " + ".join(names)
        (early_combos if total <= EARLY_COMBO_MANA_CEILING else late_combos).append(label)

    reasons: list[dict[str, Any]] = []

    def raise_floor(rule: str, minimum: int, evidence: list[str], note: str) -> None:
        reasons.append({
            "rule": rule, "minimum": minimum, "evidence": evidence, "note": note,
        })

    if len(game_changers) > GAME_CHANGERS_ALLOWED_AT_B3:
        raise_floor(
            "game_changers_over_limit", 4, game_changers,
            f"{len(game_changers)} game changers; bracket 3 allows at most "
            f"{GAME_CHANGERS_ALLOWED_AT_B3}",
        )
    elif game_changers:
        raise_floor(
            "game_changers", 3, game_changers,
            f"{len(game_changers)} game changer(s); bracket 2 allows none",
        )

    if early_combos:
        raise_floor(
            "two_card_combo_early", 4, early_combos,
            "two-card infinite that can come down early "
            f"(mana owed plus pieces at most {EARLY_COMBO_MANA_CEILING:g})",
        )
    if late_combos:
        raise_floor(
            "two_card_combo_late", 3, late_combos,
            "two-card infinite, but an expensive one",
        )
    compact_infinites = [
        (c["name"] or "").strip() for c in complete_combos
        if 0 < len(_combo_cards(c["cards_json"])) <= GENERIC_INFINITE_MAX_CARDS
    ]
    if compact_infinites and not (early_combos or late_combos):
        # A deck that wins on the spot is not a Core deck, even when the loop
        # takes three cards. The *two-card* distinction is what separates
        # bracket 3 from bracket 4; having an infinite at all is what separates
        # 3 from 2.
        #
        # ⚠️ This is the one rule the sources behind this sprint did not spell
        # out, and it was added because the live run found it missing: "Surf n
        # Turf" holds two complete three-card infinites and came out as Core,
        # while Commander Spellbook independently called the same deck
        # Ruthless. The piece limit above is what keeps it from also catching a
        # four-card engine that makes infinite Food and wins nothing.
        raise_floor(
            "infinite_combo", 3, compact_infinites,
            "a complete infinite combo, though it needs more than two cards",
        )
    if mass_land_denial:
        raise_floor("mass_land_denial", 4, mass_land_denial, "mass land denial")
    if chained_turn_combos:
        raise_floor(
            "extra_turns_chained", 4, chained_turn_combos,
            "a combo in this deck takes the extra turns in a loop",
        )
    elif len(extra_turn_cards) > EXTRA_TURN_CARDS_FOR_B3:
        raise_floor(
            "extra_turn_cards", 3, extra_turn_cards,
            f"{len(extra_turn_cards)} extra-turn cards reads as a plan, not a trick",
        )

    bracket = max([BASE_BRACKET, *(r["minimum"] for r in reasons)])

    detail = {
        "bracket": bracket,
        "reasons": reasons,
        "counts": {
            "cards": len(cards),
            "game_changers": len(game_changers),
            "two_card_combos_early": len(early_combos),
            "two_card_combos_late": len(late_combos),
            "complete_combos": len(complete_combos),
            "mass_land_denial": len(mass_land_denial),
            "extra_turn_cards": len(extra_turn_cards),
        },
        "coverage": {
            "cards_not_classified_by_spellbook": unclassified,
            "cards_never_enriched_from_scryfall": unenriched,
        },
        "scale": (
            "Computed brackets run from 2 to 4. Bracket 1 (Exhibition) and "
            "bracket 5 (cEDH) describe intent rather than contents and are set "
            "by hand."
        ),
    }

    if not persist:
        return {"deck_id": deck_id, "bracket": bracket, "detail": detail}

    await db.execute(
        """UPDATE decks SET computed_bracket = ?, computed_bracket_detail = ?,
        computed_bracket_at = CURRENT_TIMESTAMP WHERE id = ?""",
        (bracket, json.dumps(detail), deck_id),
    )
    await db.commit()
    logger.info(
        "Bracket deck %d: %d (%d game changers, %d early / %d late two-card combos, "
        "%d MLD, %d extra-turn cards)",
        deck_id, bracket, len(game_changers), len(early_combos), len(late_combos),
        len(mass_land_denial), len(extra_turn_cards),
    )
    return {"deck_id": deck_id, "bracket": bracket, "detail": detail}


async def compute_brackets_for_all_decks() -> dict[str, Any]:
    """Recompute every deck. Cheap — it is all local SQL, no network."""
    db = await get_db()
    cursor = await db.execute("SELECT id, name FROM decks ORDER BY id")
    decks = await cursor.fetchall()

    results = []
    for row in decks:
        try:
            outcome = await compute_bracket(row["id"])
            results.append({
                "deck_id": row["id"], "name": row["name"],
                "bracket": outcome.get("bracket"),
            })
        except Exception as exc:
            logger.warning("Bracket computation failed for deck %d: %s", row["id"], exc)
            results.append({"deck_id": row["id"], "name": row["name"], "error": str(exc)})

    computed = [r for r in results if r.get("bracket")]
    logger.info("Bracket recompute: %d of %d decks", len(computed), len(results))
    return {"decks": len(results), "computed": len(computed), "results": results}


async def bracket_impact_of_card(deck_id: int, card_id: int) -> dict[str, Any] | None:
    """What adding one card would do to a deck's bracket.

    Returns None when it changes nothing, so a caller can show a badge only
    where there is something to say. The comparison runs the deck through the
    rules twice rather than reasoning about the card in isolation — a fourth
    game changer matters only because three were already there.
    """
    before = await compute_bracket(deck_id, persist=False)
    after = await compute_bracket(deck_id, extra_card_ids=[card_id], persist=False)
    if before.get("bracket") is None or after.get("bracket") is None:
        return None
    if after["bracket"] <= before["bracket"]:
        return None

    was = {r["rule"] for r in before["detail"]["reasons"]}
    new_reasons = [r for r in after["detail"]["reasons"] if r["rule"] not in was]
    return {
        "from": before["bracket"],
        "to": after["bracket"],
        "reasons": new_reasons,
    }
