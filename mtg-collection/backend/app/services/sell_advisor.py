"""Sell advisor: suggest cards to sell based on unused copies and price spikes."""
import logging
from typing import Any

from ..database import get_db

logger = logging.getLogger(__name__)


async def suggest_sells(target_amount_eur: float = 50.0, max_suggestions: int = 10) -> list[dict[str, Any]]:
    """Score and rank cards to sell.

    Score = unused_copies * trend_price * (1 + spike_pct/100).
    Accumulates until target_amount_eur is reached.
    """
    db = await get_db()

    # Get all collection entries with price data and deck usage
    cursor = await db.execute(
        """SELECT
            c.name as card_name,
            c.set_name,
            COALESCE(SUM(col.quantity + col.foil_quantity), 0) as total_owned,
            COALESCE(deck_use.in_decks, 0) as in_decks,
            cp.cm_product_id,
            ph.trend,
            ph.avg30,
            CASE WHEN ph.avg30 > 0 THEN (ph.trend - ph.avg30) / ph.avg30 * 100 ELSE 0 END as spike_pct
        FROM collection col
        JOIN cards c ON c.id = col.card_id
        LEFT JOIN (
            SELECT dc.card_id, SUM(dc.quantity) as in_decks
            FROM deck_cards dc GROUP BY dc.card_id
        ) deck_use ON deck_use.card_id = c.id
        LEFT JOIN cardmarket_products cp ON cp.card_id = c.id
        LEFT JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
            AND ph.date = (SELECT MAX(date) FROM cardmarket_price_history)
        GROUP BY c.id
        HAVING total_owned > in_decks AND ph.trend > 0
        ORDER BY (total_owned - in_decks) * ph.trend * (1 + CASE WHEN ph.avg30 > 0 THEN (ph.trend - ph.avg30) / ph.avg30 ELSE 0 END) DESC"""
    )
    rows = await cursor.fetchall()

    suggestions = []
    accumulated = 0.0

    for row in rows:
        if len(suggestions) >= max_suggestions:
            break
        if accumulated >= target_amount_eur:
            break

        unused = int(row["total_owned"]) - int(row["in_decks"])
        if unused <= 0:
            continue

        trend = float(row["trend"])
        spike_pct = float(row["spike_pct"])

        # Determine how many to sell (enough to reach target, but not more than unused)
        remaining = target_amount_eur - accumulated
        copies_to_sell = min(unused, max(1, int(remaining / trend) + 1)) if trend > 0 else unused
        copies_to_sell = min(copies_to_sell, unused)
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
