"""Voice intent endpoints for HA Assist integration."""
import logging

from fastapi import APIRouter, Query

from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/card-count")
async def voice_card_count(name: str = Query(..., description="Card name to look up")):
    """Return how many copies of a card the user owns (across all printings).

    Used by HA Assist via REST sensor to answer queries like
    "How many Sol Ring do I have?".

    Returns:
        card_name: normalized name from the database
        quantity:  total physical copies (sum of quantity + foil_quantity)
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.name, COALESCE(SUM(col.quantity + col.foil_quantity), 0) AS qty
           FROM cards c
           LEFT JOIN collection col ON col.card_id = c.id
           WHERE LOWER(c.name) = LOWER(?)
           GROUP BY c.id
           ORDER BY qty DESC
           LIMIT 1""",
        (name.strip(),),
    )
    row = await cursor.fetchone()
    if not row or row["qty"] == 0:
        # Try a LIKE match as fallback
        cursor = await db.execute(
            """SELECT c.name, COALESCE(SUM(col.quantity + col.foil_quantity), 0) AS qty
               FROM cards c
               LEFT JOIN collection col ON col.card_id = c.id
               WHERE LOWER(c.name) LIKE LOWER(?)
               GROUP BY c.id
               ORDER BY qty DESC
               LIMIT 1""",
            (f"%{name.strip()}%",),
        )
        row = await cursor.fetchone()

    if not row:
        return {"card_name": name, "quantity": 0, "found": False}

    return {"card_name": row["name"], "quantity": int(row["qty"]), "found": True}


@router.get("/active-deals")
async def voice_active_deals():
    """Return wishlist items where the current price is at or below the target.

    Used by HA Assist to answer "Are there any active deals on my wishlist?".

    Returns:
        deals_count: number of items currently at or below target price
        items:       list of deal items with card name, prices, and delta
    """
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT
            w.id,
            c.name AS card_name,
            w.target_price_eur,
            w.set_code,
            w.is_foil,
            w.priority,
            COALESCE(
                (SELECT ph.trend FROM cardmarket_products cp
                 JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                 WHERE LOWER(cp.card_name) = LOWER(c.name)
                 ORDER BY ph.date DESC LIMIT 1),
                CAST(NULLIF(
                    CASE WHEN w.is_foil THEN c.price_eur_foil ELSE c.price_eur END,
                    ''
                ) AS REAL)
            ) AS current_price_eur
        FROM wishlist w
        LEFT JOIN cards c ON c.id = w.card_id
        WHERE w.removed_at IS NULL AND w.status = 'wanted'
          AND w.target_price_eur > 0
        ORDER BY w.priority DESC, c.name
        """
    )
    rows = await cursor.fetchall()

    deals = []
    for row in rows:
        target = float(row["target_price_eur"] or 0)
        current = row["current_price_eur"]
        if current is None:
            continue
        current = float(current)
        if current > target:
            continue
        delta_pct = round((current - target) / target * 100, 1) if target > 0 else 0.0
        deals.append({
            "id": row["id"],
            "card_name": row["card_name"] or "",
            "set_code": row["set_code"] or "",
            "is_foil": bool(row["is_foil"]),
            "target_price_eur": target,
            "current_price_eur": round(current, 2),
            "delta_pct": delta_pct,
            "priority": row["priority"] or 3,
        })

    return {"deals_count": len(deals), "items": deals}
