"""A port of edhpowerlevel.com's power score, computed offline.

The algorithm is deterministic and needs five fields per card — USD price,
EDHREC rank, mana value, type line/layout and the Reserved List flag — all of
which this database holds after the Scryfall enrichment. What it produces is
**not** a bracket and must never be mixed with one: the bracket asks what a deck
is *capable of*, this asks what its cards are *worth and wanted*, scaled by how
cheaply the deck can deploy them. Combos, game changers and land denial go into
the bracket only, exactly as they do in the original.

Its author says the score is gameable — "you could fill a whole deck with only
tutors and expensive lands and it would have a high score and be completely
ineffective" — and recommends comparing the **Score** rather than the Power
Level between decks. Both are reported; the caveat belongs in the UI.

Faithfulness matters more than tidiness here, because the only way to check a
port is against the original. Five places look wrong and are deliberate:

1. `de()` weights the decile index but **not** the fraction inside it.
2. `Ce` is not clamped, so a very cheap deck scores above 1 and a very
   expensive one goes negative.
3. A modal double-faced card counts as a land and drops out of the average
   mana cost entirely.
4. Basic lands get a flat `2 x quantity` **after** the land factor, not before.
5. `commanderImpact` applies only when the card really is the commander.
"""
import json
import logging
import math
from typing import Any
from urllib.parse import quote

from ..database import get_db

logger = logging.getLogger(__name__)

#: Verbatim from the site's bundle. `popCurve[10]` is also the number the
#: EDHREC rank is subtracted from, so it is both a curve top and an inversion
#: base.
FACTORS: dict[str, Any] = {
    "land": 0.6,
    "reserved": 0.2,
    "favorPrice": 0.25,
    "powerCurve": [0, 250, 320, 350, 380, 420, 470, 560, 760, 890, 1000],
    "popCurve": [0, 8500, 13600, 17100, 19800, 21900, 23700, 25300, 26200, 26700, 27000],
    "priceCurve": [0, 0.5, 1.5, 3.5, 6, 10, 15, 25, 40, 65, 100],
    "cmcFloor": 1.75,
    "cmcCeiling": 6,
    "efficiencyLimits": [0.65, 1.1],
    #: Maps the 0-10 power level onto a 1-5 Commander bracket. Added 2026-08-29
    #: after diffing the port against the site's own shipped script — it was
    #: the one constant in its `factors` object the port did not have.
    #: The site uses it as `ceil(de(level, bracketCurve))` and then takes the
    #: larger of that and its rule-based answer.
    "bracketCurve": [0, 4.7, 6.7, 7.7, 9.25, 10],
}

#: ⚠️ `popCurve` was derived in September 2024, when 27,686 cards were Commander
#: legal, and has not been touched since. Raising only the last stop is **not**
#: an update: the other ten are decile boundaries of that same 2024
#: distribution, so moving the top alone produces a curve that is neither the
#: original nor a correct recalibration — and it silently shifts every deck's
#: popularity score. A real refresh means re-deriving all eleven stops from
#: today's rank distribution. Until someone does that, the 2024 curve stands,
#: because it is the only version a result can be checked against.
POP_CURVE_DERIVED = "2024-09"

BASIC_LANDS = frozenset({
    "Mountain", "Forest", "Island", "Swamp", "Plains", "Wastes",
    "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Island",
    "Snow-Covered Swamp", "Snow-Covered Plains", "Snow-Covered Wastes",
})

#: Cards whose stored price is multiplied before it meets the price curve.
PRICE_OVERRIDES: dict[str, float] = {
    "Sol Ring": 8.0,
    "Rest in Peace": 2.5,
    "Mystic Remora": 2.0,
    "The One Ring": 0.8,
    "Sylvan Library": 0.6,
    "Ragavan, Nimble Pilferer": 0.4,
}

#: The original calls this the "social taboo" correction: cards that are far
#: more resented than their price and popularity suggest.
IMPACT_OVERRIDES: dict[str, float] = {
    "Cataclysm": 1.7,
    "Jokulhaups": 1.7,
    "Boom // Bust": 1.7,
    "Armageddon": 1.4,
}

#: Applied only when the card is the deck's commander. Keyed by the name before
#: the first comma, which is the level of identification the source material
#: gives — "Korvold" rather than a full title that would have to be guessed at.
#: Among commanders that part is effectively unique, and the override cannot
#: fire on a card that is not in the command zone anyway.
COMMANDER_IMPACT_OVERRIDES: dict[str, float] = {
    "Sisay": 4.0,
    "Kinnan": 4.0,
    "Magda": 3.5,
    "Thrasios": 3.5,
    "Vivi Ornitier": 3.0,
    "Korvold": 3.0,
    "Chulane": 3.0,
    "Yuriko": 3.0,
    "Orvar": 3.0,
    "Winota": 3.0,
    "Urza": 3.0,
    "Shirei": 2.5,
    "Tergrid": 2.5,
    "Yedora": 2.0,
    "Kraum": 2.0,
    "Tymna the Weaver": 2.0,
    "Vial Smasher the Fierce": 2.0,
}

#: Free spells are counted at zero, and a handful of cards at what they
#: realistically cost rather than what is printed on them.
_FREE_SPELLS = (
    "Fierce Guardianship", "Deflecting Swat", "Deadly Rollick", "Flawless Maneuver",
    "Obscuring Haze", "Flare of Denial", "Flare of Fortitude", "Flare of Duplication",
    "Flare of Malice", "Flare of Cultivation", "Endurance", "Solitude", "Grief",
    "Subtlety", "Fury", "Force of Vigor", "Force of Negation", "Force of Despair",
    "Force of Virtue", "Force of Rage", "Force of Will", "Misdirection", "Submerge",
    "Snuff Out", "Daze", "Foil", "Gush",
)
CMC_OVERRIDES: dict[str, float] = {name: 0.0 for name in _FREE_SPELLS} | {
    "Shriekmaw": 2.0,
    "Blasphemous Act": 3.0,
    "Vandalblast": 3.0,
    "Treasure Cruise": 3.0,
    "Dig Through Time": 4.0,
    "Everflowing Chalice": 2.0,
    "The Great Henge": 5.0,
    "Cyclonic Rift": 5.0,
    "Temporal Trespass": 7.0,
    "Emrakul, the Promised End": 7.0,
}

#: The bundle also carries `producer` overrides that correct which colours a
#: land makes. They steer the mana-base display, never the score, so they are
#: not ported.

_TIPPING_POINT_SHARE = 0.65


def de(value: float, curve: list[float], weight: float = 1.0) -> float:
    """The site's interpolator: decile index times weight, plus a raw fraction.

    ⚠️ The fraction inside a decile is **not** multiplied by the weight — only
    the decile boundary is. At weight 1.25 the result is therefore not a clean
    1.25 x [0..10] but piecewise offset. Implementing this "properly" is the
    single most likely way to drift from the reference.
    """
    if value <= curve[0]:
        return 0.0
    if value > curve[-1]:
        return (len(curve) - 1) * weight
    for index in range(len(curve) - 1):
        if curve[index] <= value < curve[index + 1]:
            span = curve[index + 1] - curve[index]
            return index * weight + (value - curve[index]) / span
    return 0.0


def _price_usd(row: Any) -> float:
    """The card's USD price, lowest of the printing's non-foil and foil.

    ⚠️ Ours comes from Archidekt (its TCGplayer figure) for most cards, where
    the original reads Scryfall. They track each other but are not the same
    number, so a small divergence from the reference is expected here and is
    not a porting error.
    """
    candidates = []
    for key in ("price_usd", "price_usd_foil"):
        raw = (row[key] or "").strip()
        if raw:
            try:
                candidates.append(float(raw))
            except ValueError:
                continue
    return min(candidates) if candidates else 0.0


def _base_name(name: str) -> str:
    return (name or "").split(",")[0].strip()


def _card_impact(row: Any, quantity: int, is_commander: bool) -> dict[str, Any]:
    """Impact of one card entry, before the deck-level scaling."""
    name = row["name"] or ""

    price = _price_usd(row) * PRICE_OVERRIDES.get(name, 1.0)
    if row["reserved"] == 1:
        price *= FACTORS["reserved"]

    rank = row["edhrec_rank"]
    popularity = FACTORS["popCurve"][10] - rank if rank else 0

    price_rating = de(price, FACTORS["priceCurve"], 1 + FACTORS["favorPrice"])
    pop_rating = de(popularity, FACTORS["popCurve"], 1 + FACTORS["favorPrice"] * -1)
    impact = (price_rating + pop_rating) * quantity

    impact *= IMPACT_OVERRIDES.get(name, 1.0)
    if is_commander:
        impact *= COMMANDER_IMPACT_OVERRIDES.get(_base_name(name), 1.0)

    cmc = CMC_OVERRIDES.get(name, row["cmc"] or 0.0)

    head = (row["type_line"] or "").split(" // ")[0].split(" — ")[0]
    is_land = "Land" in head or (row["layout"] or "") == "modal_dfc"
    if is_land:
        impact *= FACTORS["land"]
        cmc = 0.0
    if name in BASIC_LANDS:
        # Flat floor, applied *after* the land factor rather than scaled by it.
        impact = 2.0 * quantity

    return {
        "name": name,
        "quantity": quantity,
        "impact": impact,
        "cmc": cmc,
        "is_land": is_land,
        "is_mdfc": (row["layout"] or "") == "modal_dfc",
    }


async def compute_power_level(deck_id: int) -> dict[str, Any]:
    """Score one deck and store the result with the numbers behind it."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.name, c.cmc, c.type_line, c.layout, c.edhrec_rank, c.reserved,
                  c.price_usd, c.price_usd_foil, dc.quantity, dc.is_commander
        FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ?""",
        (deck_id,),
    )
    rows = await cursor.fetchall()
    if not rows:
        return {"deck_id": deck_id, "score": None, "reason": "deck has no cards"}

    entries = [
        _card_impact(r, int(r["quantity"] or 1), bool(r["is_commander"])) for r in rows
    ]

    total_impact = sum(e["impact"] for e in entries)
    nonlands = [e for e in entries if not e["is_land"]]
    nonland_impact = sum(e["impact"] for e in nonlands)
    nonland_count = sum(e["quantity"] for e in nonlands)

    # An MDFC is out of the average entirely — it is neither a land's zero nor
    # its printed cost.
    costed = [e for e in entries if not e["is_mdfc"]]
    avg_cost = (
        sum(e["cmc"] * e["quantity"] for e in costed) / nonland_count
        if nonland_count else 0.0
    )

    # Tipping point: the mana value at which the cumulative non-land impact
    # first passes 65% — "how much mana you need to access the majority of the
    # power in your deck".
    impact_by_cmc: dict[float, float] = {}
    for entry in nonlands:
        impact_by_cmc[entry["cmc"]] = impact_by_cmc.get(entry["cmc"], 0.0) + entry["impact"]
    tipping_point = 0.0
    running = 0.0
    for cmc in sorted(impact_by_cmc):
        running += impact_by_cmc[cmc]
        if running > nonland_impact * _TIPPING_POINT_SHARE:
            tipping_point = cmc
            break

    midpoint = (avg_cost + tipping_point) / 2
    ceiling, floor = FACTORS["cmcCeiling"], FACTORS["cmcFloor"]
    efficiency = (ceiling - midpoint) / (ceiling - floor)  # deliberately unclamped
    low, high = FACTORS["efficiencyLimits"]
    scale = low + (high - low) * efficiency

    score = total_impact * scale
    level = de(score, FACTORS["powerCurve"])

    top = sorted(entries, key=lambda e: e["impact"], reverse=True)[:10]
    detail = {
        "score": round(score, 1),
        "power_level": round(level, 2),
        "efficiency": round(efficiency * 10, 2),  # the site shows Ce x 10
        "tipping_point": tipping_point,
        "avg_cost": round(avg_cost, 2),
        # What the reference site would call this deck's bracket, derived from
        # the power level alone. **Not** the same thing as `computed_bracket`
        # from services/bracket.py, which applies the WotC rules (game
        # changers, two-card combos, mass land denial, extra turns) and is the
        # authority. Kept because the disagreement is the interesting part: a
        # deck whose rules say 2 while its power curve says 4 is stronger than
        # its label, and nothing else in the app says so.
        "reference_bracket": max(1, min(5, math.ceil(de(level, FACTORS["bracketCurve"])))),
        "total_impact": round(total_impact, 1),
        "nonland_impact": round(nonland_impact, 1),
        "cards": len(rows),
        "lands": sum(1 for e in entries if e["is_land"]),
        "top_cards": [{"name": e["name"], "impact": round(e["impact"], 2)} for e in top],
        "impact_by_cmc": {str(k): round(v, 1) for k, v in sorted(impact_by_cmc.items())},
        "pop_curve_derived": POP_CURVE_DERIVED,
        "caveat": (
            "Demand (price and popularity) scaled by curve efficiency. It says "
            "nothing about synergy, combos or consistency, and its author "
            "recommends comparing the score rather than the level."
        ),
    }

    await db.execute(
        """UPDATE decks SET power_score = ?, power_level = ?, power_detail = ?,
        power_computed_at = CURRENT_TIMESTAMP WHERE id = ?""",
        (round(score, 2), round(level, 3), json.dumps(detail), deck_id),
    )
    await db.commit()
    logger.info(
        "Power deck %d: score %.1f, level %.2f (avg cost %.2f, tipping point %g, "
        "efficiency %.2f)",
        deck_id, score, level, avg_cost, tipping_point, efficiency * 10,
    )
    return {"deck_id": deck_id, "score": round(score, 2), "level": round(level, 3),
            "detail": detail}


async def compute_power_for_all_decks() -> dict[str, Any]:
    """Recompute every deck. Local arithmetic, no network."""
    db = await get_db()
    cursor = await db.execute("SELECT id, name FROM decks ORDER BY id")
    decks = await cursor.fetchall()

    results = []
    for row in decks:
        try:
            outcome = await compute_power_level(row["id"])
            results.append({
                "deck_id": row["id"], "name": row["name"],
                "score": outcome.get("score"), "level": outcome.get("level"),
            })
        except Exception as exc:
            logger.warning("Power computation failed for deck %d: %s", row["id"], exc)
            results.append({"deck_id": row["id"], "name": row["name"], "error": str(exc)})

    scored = [r for r in results if r.get("score") is not None]
    logger.info("Power recompute: %d of %d decks", len(scored), len(results))
    return {"decks": len(results), "computed": len(scored), "results": results}


async def reference_url(deck_id: int) -> str:
    """The edhpowerlevel.com link that scores this exact list, for comparison.

    The site takes a decklist in the query string: newlines become `~`, spaces
    become `+`, and `~Z~` terminates it — without that terminator its decoder
    refuses the URL as truncated. This is the only way to check the port
    against the original, since the original runs in a browser.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.name, dc.quantity, dc.is_commander
        FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ? ORDER BY dc.is_commander DESC, c.name""",
        (deck_id,),
    )
    lines = [
        f"{int(row['quantity'] or 1)} {row['name']}"
        + (" [Commander]" if row["is_commander"] else "")
        for row in await cursor.fetchall()
    ]
    encoded = quote("~".join(lines), safe="").replace("%20", "+")
    return f"https://edhpowerlevel.com?d={encoded}~Z~"
