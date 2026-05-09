"""Listing health analysis: compare Cardmarket listings vs current trend price."""
import logging
from ..database import get_db

logger = logging.getLogger(__name__)


async def analyze_listings(threshold_pct: float = 15.0) -> dict:
    """Compare each cardmarket_listing against the latest trend price.

    Returns a dict with four buckets:
    - underpriced: my_price < trend * (1 - threshold_pct/100)
    - overpriced:  my_price > trend * (1 + threshold_pct/100)
    - fair:        within the threshold band
    - no_match:    listings without a matching cardmarket_product / trend price
    """
    db = await get_db()

    cursor = await db.execute(
        """
        SELECT
            cl.id AS listing_id,
            cl.card_name,
            cl.price AS my_price,
            ph.trend AS trend_price
        FROM cardmarket_listings cl
        LEFT JOIN cardmarket_products cp
            ON LOWER(cp.card_name) = LOWER(cl.card_name)
        LEFT JOIN cardmarket_price_history ph
            ON ph.cm_product_id = cp.cm_product_id
           AND ph.date = (
               SELECT MAX(ph2.date)
               FROM cardmarket_price_history ph2
               WHERE ph2.cm_product_id = cp.cm_product_id
           )
        ORDER BY cl.card_name
        """
    )
    rows = await cursor.fetchall()

    underpriced: list[dict] = []
    overpriced: list[dict] = []
    fair: list[dict] = []
    no_match: list[dict] = []

    factor = threshold_pct / 100.0

    for row in rows:
        listing_id = row["listing_id"]
        card_name = row["card_name"]
        my_price = float(row["my_price"] or 0)
        trend = row["trend_price"]

        if my_price <= 0:
            # Zero-price listings: skip comparison, put in no_match
            no_match.append({"listing_id": listing_id, "card_name": card_name, "my_price": my_price})
            continue

        if trend is None or trend <= 0:
            no_match.append({"listing_id": listing_id, "card_name": card_name, "my_price": my_price})
            continue

        trend = float(trend)
        delta_pct = round((my_price - trend) / trend * 100, 1) if trend > 0 else 0.0
        suggested_price = round(trend, 2)
        entry = {
            "listing_id": listing_id,
            "card_name": card_name,
            "my_price": my_price,
            "trend_price": trend,
            "suggested_price": suggested_price,
            "delta_pct": delta_pct,
        }

        if my_price < trend * (1 - factor):
            underpriced.append(entry)
        elif my_price > trend * (1 + factor):
            overpriced.append(entry)
        else:
            fair.append(entry)

    return {
        "underpriced": underpriced,
        "overpriced": overpriced,
        "fair": fair,
        "no_match": no_match,
    }
