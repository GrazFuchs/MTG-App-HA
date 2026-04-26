"""Wishlist API routes."""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class WishlistItem(BaseModel):
    id: int = 0
    card_name: str
    max_price_eur: float = 0.0
    notes: str = ""
    added_at: str = ""
    current_price: float | None = None
    is_deal: bool = False


class WishlistAdd(BaseModel):
    card_name: str
    max_price_eur: float = 0.0
    notes: str = ""


@router.get("/", response_model=list[WishlistItem])
async def list_wishlist():
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, card_name, max_price_eur, notes, added_at FROM wishlist ORDER BY added_at DESC"
    )
    rows = await cursor.fetchall()

    items = []
    for r in rows:
        # Try to find current price from cardmarket_price_history
        price_cursor = await db.execute(
            """SELECT ph.trend FROM cardmarket_products cp
            JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
            WHERE LOWER(cp.card_name) = LOWER(?)
            ORDER BY ph.date DESC LIMIT 1""",
            (r["card_name"],),
        )
        price_row = await price_cursor.fetchone()
        current_price = price_row[0] if price_row else None
        is_deal = (
            current_price is not None
            and r["max_price_eur"] > 0
            and current_price <= r["max_price_eur"]
        )
        items.append(WishlistItem(
            id=r["id"],
            card_name=r["card_name"],
            max_price_eur=r["max_price_eur"],
            notes=r["notes"],
            added_at=r["added_at"] or "",
            current_price=current_price,
            is_deal=is_deal,
        ))
    return items


@router.post("/", response_model=WishlistItem)
async def add_to_wishlist(item: WishlistAdd):
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO wishlist (card_name, max_price_eur, notes) VALUES (?, ?, ?)",
            (item.card_name.strip(), item.max_price_eur, item.notes.strip()),
        )
        await db.commit()
        return WishlistItem(
            id=cursor.lastrowid or 0,
            card_name=item.card_name.strip(),
            max_price_eur=item.max_price_eur,
            notes=item.notes.strip(),
        )
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="Card already on wishlist")
        raise


@router.delete("/{item_id}")
async def remove_from_wishlist(item_id: int):
    db = await get_db()
    cursor = await db.execute("DELETE FROM wishlist WHERE id = ?", (item_id,))
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}
