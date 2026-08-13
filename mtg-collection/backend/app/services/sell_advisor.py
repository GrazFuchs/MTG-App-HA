"""Sell advisor: suggest cards to sell based on unused copies and price spikes."""
import logging
from typing import Any

from ..database import get_db

logger = logging.getLogger(__name__)


async def suggest_sells(
    target_amount_eur: float | None = 50.0, max_suggestions: int = 10
) -> list[dict[str, Any]]:
    """Score and rank cards to sell.

    Score = unused_copies * trend_price * (1 + spike_pct/100).
    Accumulates until target_amount_eur is reached; pass ``None`` to rank every
    candidate and offer all unused copies (used by the HA sell sensors).
    """
    db = await get_db()

    # One row per card. Price and product come from correlated subqueries
    # rather than joins: joining cardmarket_products multiplied every
    # collection row by the number of matching products, so `total_owned`
    # counted a 3-copy playset as 93 when the card had 31 Cardmarket products.
    cursor = await db.execute(
        """SELECT
            c.name as card_name,
            c.set_name,
            COALESCE(SUM(col.quantity + col.foil_quantity), 0) as total_owned,
            COALESCE(deck_use.in_decks, 0) as in_decks,
            (SELECT cp.cm_product_id FROM cardmarket_products cp
             WHERE cp.card_id = c.id LIMIT 1) as cm_product_id,
            (SELECT ph.trend FROM cardmarket_products cp
             JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
             WHERE cp.card_id = c.id
             ORDER BY ph.date DESC LIMIT 1) as trend,
            (SELECT ph.avg30 FROM cardmarket_products cp
             JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
             WHERE cp.card_id = c.id
             ORDER BY ph.date DESC LIMIT 1) as avg30
        FROM collection col
        JOIN cards c ON c.id = col.card_id
        LEFT JOIN (
            SELECT dc.card_id, SUM(dc.quantity) as in_decks
            FROM deck_cards dc GROUP BY dc.card_id
        ) deck_use ON deck_use.card_id = c.id
        GROUP BY c.id
        -- COALESCE spelled out: a bare `in_decks` in HAVING/ORDER BY binds to
        -- deck_use.in_decks (NULL for cards in no deck), not to the SELECT
        -- alias, which silently dropped every card that isn't in a deck.
        HAVING total_owned > COALESCE(deck_use.in_decks, 0) AND trend > 0
        ORDER BY (total_owned - COALESCE(deck_use.in_decks, 0)) * trend
                 * (1 + CASE WHEN avg30 > 0
                             THEN (trend - avg30) / avg30 ELSE 0 END) DESC"""
    )
    rows = await cursor.fetchall()

    suggestions = []
    accumulated = 0.0

    for row in rows:
        if len(suggestions) >= max_suggestions:
            break
        if target_amount_eur is not None and accumulated >= target_amount_eur:
            break

        unused = int(row["total_owned"]) - int(row["in_decks"])
        if unused <= 0:
            continue

        trend = float(row["trend"])
        avg30 = float(row["avg30"] or 0)
        spike_pct = (trend - avg30) / avg30 * 100 if avg30 > 0 else 0.0

        # Determine how many to sell (enough to reach target, but not more than unused)
        if target_amount_eur is None or trend <= 0:
            copies_to_sell = unused
        else:
            remaining = target_amount_eur - accumulated
            copies_to_sell = min(unused, max(1, int(remaining / trend) + 1))
        expected_total = round(copies_to_sell * trend, 2)

        # Build reason
        reasons = []
        if int(row["in_decks"]) == 0:
            reasons.append("nicht in Decks")
        else:
            reasons.append(f"nur {int(row['in_decks'])} in Decks benötigt")
        if spike_pct > 10:
            reasons.append(f"Preis-Spike +{spike_pct:.0f}%")

        suggestions.append({
            "card_name": row["card_name"],
            "set_name": row["set_name"],
            "copies_to_sell": copies_to_sell,
            "unused_copies": unused,
            "trend_price_eur": trend,
            "expected_total_eur": expected_total,
            "spike_pct": round(spike_pct, 1),
            "reason": ", ".join(reasons) if reasons else "Überschüssige Kopien",
        })
        accumulated += expected_total

    return suggestions
