"""What a deck format allows — the one table everything else asks.

Until 0.47.0 every deck in this database was Commander, and four analyses said
so without ever checking: the WotC bracket, the edhpowerlevel score, Spellbook's
per-card classification and the EDHREC commander lookup. None of them is defined
for a 60-card deck, and none of them declined to answer.

So this module owns two questions, and nothing else may answer them privately:

* **Which analysis applies to this deck?** `bracket_applies` / `power_applies` /
  `has_commander`. A format that is not in the table answers *no* to all of
  them — a guess here is how a Standard deck ends up labelled "bracket 2".
* **What shape is this deck supposed to have?** `deck_rules` — main size,
  sideboard size, copy limit, singleton, default pod size. Sprint 14 checks a
  deck against these; Sprint 15 takes the pod size from them.

Three decisions shape the table, and each is a limit worth knowing:

**The Archidekt format numbers are measured, not transcribed.** The old table
in `clients/archidekt.py` was written from memory when only Commander mattered,
and it was wrong from number 7 onward — every entry shifted by one. Measured
live on 2026-09-15 against Archidekt's own `/formats/<slug>` pages: 22 is
*Premodern*, not *Predh*; 15 is *Pioneer*, not *Historic*. It never showed
because Commander is 3 in both readings and all 22 decks were Commander — the
same accident that let the colour bug survive, where White/Black/Red happened
to contain exactly one colour letter.

**An unmeasured number gets no name.** `UNVERIFIED_FORMAT_IDS` below lists the
numbers nobody has confirmed; they resolve to `Unknown` rather than to the name
that would follow from the "everything shifts by one" pattern. The pattern is
almost certainly right, and that is exactly why it must not be written down as
fact: a plausible wrong name is worse than a visible gap, because nothing ever
looks at it again.

**The table is not trusted alone.** `check_shape` compares what the table
claims against what the deck actually looks like — 100 singleton cards with a
commander is not a Standard deck, whatever the number says. A contradiction is
reported, not resolved, and the gates fall back to "nothing applies". That is
the same rule the bracket uses for cards Spellbook does not know: unclassified,
not clean.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Family = Literal["commander", "constructed", "unknown"]


@dataclass(frozen=True)
class DeckRules:
    """The shape a legal deck of this format has."""

    #: Smallest legal main deck. `None` = the format has no rule we enforce.
    main_min: int | None = None
    #: Largest legal main deck. `None` = no upper bound (constructed formats).
    main_max: int | None = None
    #: Largest legal sideboard. 0 = the format has no sideboard.
    side_max: int = 0
    #: Copies of one card allowed across main + sideboard.
    max_copies: int = 4
    #: Singleton: exactly one of everything but basic lands.
    singleton: bool = False
    #: How many players a game of this format usually has. Sprint 15 uses it as
    #: the default for a logged game, because "4" is wrong for every 1v1 format
    #: and correcting it by hand every time is how a log stops being kept.
    default_pod_size: int = 2
    #: Is a *match* the unit here — best-of-three with sideboarding between
    #: games? True for constructed, false for the Commander family: a
    #: Commander pod plays one game and goes home, and there is no sideboard
    #: to change anything with. It decides whether the match statistics are
    #: shown at all, because "1 match, 100 %" under a single Commander game is
    #: a number pretending to be an insight.
    matches: bool = False


@dataclass(frozen=True)
class FormatSpec:
    """Everything the app needs to know about one format."""

    name: str
    family: Family
    #: Does a deck of this format have a commander?
    commander: bool
    #: Does the WotC 1-5 bracket apply? Commander only — see `bracket.py`. The
    #: system was written for casual multiplayer Commander; Duel Commander has
    #: its own banlist and its own culture, and cEDH-adjacent formats are not
    #: what brackets 1-3 describe. Applying it there would produce a number
    #: that looks official and means nothing.
    bracket: bool
    #: Does the edhpowerlevel port apply? Commander only, and for the same
    #: reason the port is faithful rather than tidy: its `popCurve` was derived
    #: from Commander-legal cards, its land factor assumes 99+1, and
    #: `commanderImpact` assumes there is a commander. A "Standard variant"
    #: would be invented, not ported.
    power: bool
    #: Key inside Scryfall's `legalities` object, or None when we do not check.
    legality_key: str | None
    rules: DeckRules


#: Standard constructed shape: 60+ main, 15 sideboard, 4 copies, 1v1, best of
#: three. The sideboard and the match are the same fact seen twice: a format
#: with 15 cards to swap in is a format where game two is a different game.
_CONSTRUCTED = DeckRules(
    main_min=60, main_max=None, side_max=15, max_copies=4, matches=True,
)

#: Commander shape: exactly 100 including the commander, singleton, 4 players.
_COMMANDER = DeckRules(
    main_min=100, main_max=100, side_max=0, max_copies=1,
    singleton=True, default_pod_size=4,
)

#: Commander-shaped but played 1v1, so the pod size differs.
_COMMANDER_1V1 = DeckRules(
    main_min=100, main_max=100, side_max=0, max_copies=1,
    singleton=True, default_pod_size=2,
)

#: Brawl and its relatives: 60 singleton around a commander.
_BRAWL = DeckRules(
    main_min=60, main_max=60, side_max=0, max_copies=1,
    singleton=True, default_pod_size=2,
)


FORMATS: dict[str, FormatSpec] = {
    # --- Commander family -------------------------------------------------
    "Commander": FormatSpec(
        "Commander", "commander", commander=True, bracket=True, power=True,
        legality_key="commander", rules=_COMMANDER,
    ),
    "Duel Commander": FormatSpec(
        "Duel Commander", "commander", commander=True, bracket=False, power=False,
        legality_key="duel", rules=_COMMANDER_1V1,
    ),
    "1v1 Commander": FormatSpec(
        "1v1 Commander", "commander", commander=True, bracket=False, power=False,
        legality_key=None, rules=_COMMANDER_1V1,
    ),
    "Pauper Commander": FormatSpec(
        "Pauper Commander", "commander", commander=True, bracket=False, power=False,
        legality_key="paupercommander", rules=_COMMANDER,
    ),
    "Predh": FormatSpec(
        "Predh", "commander", commander=True, bracket=False, power=False,
        legality_key="predh", rules=_COMMANDER,
    ),
    "Oathbreaker": FormatSpec(
        "Oathbreaker", "commander", commander=True, bracket=False, power=False,
        legality_key="oathbreaker", rules=DeckRules(
            main_min=60, main_max=60, side_max=0, max_copies=1,
            singleton=True, default_pod_size=4,
        ),
    ),
    "Brawl": FormatSpec(
        "Brawl", "commander", commander=True, bracket=False, power=False,
        legality_key="brawl", rules=_BRAWL,
    ),
    "Standard Brawl": FormatSpec(
        "Standard Brawl", "commander", commander=True, bracket=False, power=False,
        legality_key="standardbrawl", rules=_BRAWL,
    ),
    "Historic Brawl": FormatSpec(
        "Historic Brawl", "commander", commander=True, bracket=False, power=False,
        legality_key="brawl", rules=_BRAWL,
    ),

    # --- Constructed family ----------------------------------------------
    # All of these share 60/15/4 and differ only in which Scryfall key says
    # whether a card may be in them. That is the whole point of keeping the
    # legality key in the table instead of writing a rule per format.
    "Standard": FormatSpec(
        "Standard", "constructed", commander=False, bracket=False, power=False,
        legality_key="standard", rules=_CONSTRUCTED,
    ),
    "Pioneer": FormatSpec(
        "Pioneer", "constructed", commander=False, bracket=False, power=False,
        legality_key="pioneer", rules=_CONSTRUCTED,
    ),
    "Modern": FormatSpec(
        "Modern", "constructed", commander=False, bracket=False, power=False,
        legality_key="modern", rules=_CONSTRUCTED,
    ),
    "Legacy": FormatSpec(
        "Legacy", "constructed", commander=False, bracket=False, power=False,
        legality_key="legacy", rules=_CONSTRUCTED,
    ),
    "Vintage": FormatSpec(
        "Vintage", "constructed", commander=False, bracket=False, power=False,
        # Vintage restricts a list of cards to one copy. Scryfall reports that
        # as `restricted` in the same field, so `legality.py` reads it without
        # needing a second source — see the note there.
        legality_key="vintage", rules=_CONSTRUCTED,
    ),
    "Pauper": FormatSpec(
        "Pauper", "constructed", commander=False, bracket=False, power=False,
        # Commons only. Not a rule of ours: Scryfall's `pauper` key already
        # accounts for rarity, so a rare in a Pauper deck reads as `not_legal`
        # and needs no rarity check beside it.
        legality_key="pauper", rules=_CONSTRUCTED,
    ),
    "Premodern": FormatSpec(
        "Premodern", "constructed", commander=False, bracket=False, power=False,
        legality_key="premodern", rules=_CONSTRUCTED,
    ),
    "Explorer": FormatSpec(
        "Explorer", "constructed", commander=False, bracket=False, power=False,
        legality_key="explorer", rules=_CONSTRUCTED,
    ),
    "Historic": FormatSpec(
        "Historic", "constructed", commander=False, bracket=False, power=False,
        legality_key="historic", rules=_CONSTRUCTED,
    ),
    "Alchemy": FormatSpec(
        "Alchemy", "constructed", commander=False, bracket=False, power=False,
        legality_key="alchemy", rules=_CONSTRUCTED,
    ),
    "Timeless": FormatSpec(
        "Timeless", "constructed", commander=False, bracket=False, power=False,
        legality_key="timeless", rules=_CONSTRUCTED,
    ),
    "Penny Dreadful": FormatSpec(
        "Penny Dreadful", "constructed", commander=False, bracket=False, power=False,
        legality_key="penny", rules=_CONSTRUCTED,
    ),
    "Gladiator": FormatSpec(
        "Gladiator", "constructed", commander=False, bracket=False, power=False,
        # 100 singleton cards, no commander — the one format that is neither
        # shape. It is constructed because nothing here has a commander to
        # score or to look up on EDHREC.
        legality_key="gladiator", rules=DeckRules(
            main_min=100, main_max=100, side_max=0, max_copies=1, singleton=True,
        ),
    ),
    "Frontier": FormatSpec(
        "Frontier", "constructed", commander=False, bracket=False, power=False,
        # Scryfall dropped the `frontier` key when the format died.
        legality_key=None, rules=_CONSTRUCTED,
    ),
    "Future Standard": FormatSpec(
        "Future Standard", "constructed", commander=False, bracket=False, power=False,
        legality_key="future", rules=_CONSTRUCTED,
    ),
}


#: The empty spec every unknown format resolves to: nothing applies, nothing is
#: checked, nothing is claimed. Deliberately *not* a Commander default — a
#: default that happens to be right for today's database is how the whole
#: problem started.
UNKNOWN = FormatSpec(
    "Unknown", "unknown", commander=False, bracket=False, power=False,
    legality_key=None, rules=DeckRules(),
)


# ---------------------------------------------------------------------------
# Archidekt's `deckFormat` numbers
#
# ⚠️ MEASURED, NOT TRANSCRIBED. Each number below was confirmed on 2026-09-15
# by opening Archidekt's own `/formats/<slug>` page, taking the first deck it
# lists, and reading `deckFormat` from `GET /api/decks/<id>/small/`.
#
# The table this replaces (in `clients/archidekt.py`) was off by one from 7
# upward: it called 22 "Predh" when Archidekt means Premodern, and 15
# "Historic" when Archidekt means Pioneer. Two Premodern decks had been sitting
# in the database since 2026-09-12 labelled "Predh" because of it.
#
# The unmeasured numbers are NOT filled in from the pattern. See the module
# docstring: a plausible wrong name is worse than a visible gap.
# ---------------------------------------------------------------------------
ARCHIDEKT_FORMATS: dict[int, str] = {
    1: "Standard",
    2: "Modern",
    3: "Commander",
    4: "Legacy",
    5: "Vintage",
    6: "Pauper",
    8: "Frontier",
    13: "Brawl",
    14: "Oathbreaker",
    15: "Pioneer",
    16: "Historic",
    18: "Alchemy",
    21: "Gladiator",
    22: "Premodern",
    23: "Predh",
    24: "Timeless",
}

#: Numbers Archidekt uses that nobody has confirmed a name for. Listed so the
#: gap is visible and so a future measurement has somewhere to land. A deck
#: carrying one of these resolves to `Unknown` and gets no analysis at all,
#: which is loud enough to notice and safe enough to ship.
UNVERIFIED_FORMAT_IDS: tuple[int, ...] = (7, 9, 10, 11, 12, 17, 19, 20, 25)


def format_name(format_id: int | None) -> str:
    """Archidekt's `deckFormat` number → our format name.

    An unknown or unverified number yields `"Unknown"`. The number itself is
    kept on the deck row (`decks.archidekt_format_id`) so the gap can be closed
    later without a re-sync.
    """
    if format_id is None:
        return "Unknown"
    return ARCHIDEKT_FORMATS.get(int(format_id), "Unknown")


def spec(format_name_or_none: str | None) -> FormatSpec:
    """The spec for a stored `decks.format` value. Never raises."""
    if not format_name_or_none:
        return UNKNOWN
    return FORMATS.get(format_name_or_none.strip(), UNKNOWN)


def has_commander(fmt: str | None) -> bool:
    return spec(fmt).commander


def bracket_applies(fmt: str | None) -> bool:
    return spec(fmt).bracket


def power_applies(fmt: str | None) -> bool:
    return spec(fmt).power


def legality_key(fmt: str | None) -> str | None:
    return spec(fmt).legality_key


def deck_rules(fmt: str | None) -> DeckRules:
    return spec(fmt).rules


def default_pod_size(fmt: str | None) -> int:
    return spec(fmt).rules.default_pod_size


def family(fmt: str | None) -> Family:
    return spec(fmt).family


# ---------------------------------------------------------------------------
# The cross-check
# ---------------------------------------------------------------------------

#: A deck this small is a draft, not a statement about its format. Deck 14
#: ("Entchantment DECK") holds 8 cards and would otherwise be reported as
#: contradicting every format it could carry.
_TOO_SMALL_TO_JUDGE = 20


def check_shape(
    fmt: str | None, *, total_cards: int, distinct_cards: int, has_commander_card: bool
) -> str | None:
    """Does the deck look like the format claims? Returns a reason, or None.

    This exists because the format number comes from a table that was wrong for
    two years without anyone noticing. The deck itself is the second opinion:
    a commander plus ~100 singleton cards is a Commander deck whatever the
    number says, and 60 cards with playsets is not.

    Deliberately narrow. It reports only contradictions that cannot be a matter
    of taste — a missing commander where the format requires one, playsets in a
    singleton format, a card count off by more than a third. An incomplete deck
    is not a contradiction; that is what Sprint 14's deck check is for.
    """
    if total_cards < _TOO_SMALL_TO_JUDGE:
        return None

    s = spec(fmt)
    if s.family == "unknown":
        return None

    if s.commander and not has_commander_card:
        return (
            f"{s.name} decks have a commander, this one has none "
            f"({total_cards} cards)"
        )
    if not s.commander and has_commander_card:
        return f"{s.name} has no commander, but a card here is marked as one"

    # Playsets in a singleton format. Compared on distinct vs total rather than
    # per card, because basic lands legitimately repeat in every singleton deck
    # and a per-card test would need to know which those are.
    if s.rules.singleton and distinct_cards and total_cards > distinct_cards * 1.4:
        return (
            f"{s.name} is singleton, but {total_cards} cards share only "
            f"{distinct_cards} names"
        )

    if s.rules.main_max and total_cards > s.rules.main_max * 1.35:
        return (
            f"{s.name} allows at most {s.rules.main_max} cards, this deck has "
            f"{total_cards}"
        )
    if s.rules.main_min and total_cards < s.rules.main_min * 0.66:
        return (
            f"{s.name} needs at least {s.rules.main_min} cards, this deck has "
            f"{total_cards}"
        )
    return None


def rules_payload(fmt: str | None) -> dict:
    """The format's rules as the frontend and MCP see them.

    Handed out with the deck so neither has to keep its own copy of the table —
    the same reason the `ziele` map lives in one place in the HA packages, and
    the same reason the drying card reads its numbers off the button instead of
    holding them.
    """
    s = spec(fmt)
    r = s.rules
    return {
        "format": s.name,
        "family": s.family,
        "commander": s.commander,
        "bracket_applies": s.bracket,
        "power_applies": s.power,
        "legality_key": s.legality_key,
        "main_min": r.main_min,
        "main_max": r.main_max,
        "side_max": r.side_max,
        "max_copies": r.max_copies,
        "singleton": r.singleton,
        "default_pod_size": r.default_pod_size,
        "matches": r.matches,
    }
