"""Wishlist API routes."""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class WishlistCardInfo(BaseModel):
    name: str = ""
    set_name: str = ""
    image_uri: str = ""
    scryfall_id: str = ""


class WishlistItemResponse(BaseModel):
    id: int = 0
    card_id: int = 0
    target_price_eur: float = 0.0
    notes: str = ""
    added_at: str = ""
    current_price: float | None = None
    is_deal: bool = False
    card: WishlistCardInfo = WishlistCardInfo()


class WishlistAdd(BaseModel):
    scryfall_id: str = ""
    card_name: str = ""
    target_price_eur: float = 0.0
    notes: str = ""


@router.get("/", response_model=list[WishlistItemResponse])
async def list_wishlist():
    db = await get_db()
    cursor = await db.execute(
        """SELECT w.id, w.card_id, w.target_price_eur, w.notes, w.added_at,
                  c.name, c.set_name, c.image_uri, c.scryfall_id
           FROM wishlist w
           LEFT JOIN cards c ON c.id = w.card_id
           WHERE w.removed_at IS NULL
           ORDER BY w.added_at DESC"""
    )
    rows = await cursor.fetchall()

    items = []
    for r in rows:
        card_name = r["name"] or ""
        # Try to find current price from cardmarket_price_history
        price_cursor = await db.execute(
            """SELECT ph.trend FROM cardmarket_products cp
            JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
            WHERE LOWER(cp.card_name) = LOWER(?)
            ORDER BY ph.date DESC LIMIT 1""",
            (card_name,),
        )
        price_row = await price_cursor.fetchone()
        current_price = price_row[0] if price_row else None
        is_deal = (
            current_price is not None
            and r["target_price_eur"] > 0
            and current_price <= r["target_price_eur"]
        )
        items.append(WishlistItemResponse(
            id=r["id"],
            card_id=r["card_id"] or 0,
            target_price_eur=r["target_price_eur"] or 0,
            notes=r["notes"] or "",
            added_at=r["added_at"] or "",
            current_price=current_price,
            is_deal=is_deal,
            card=WishlistCardInfo(
                name=card_name,
                set_name=r["set_name"] or "",
                image_uri=r["image_uri"] or "",
                scryfall_id=r["scryfall_id"] or "",
            ),
        ))
    return items


@router.post("/", response_model=WishlistItemResponse)
async def add_to_wishlist(item: WishlistAdd):
    db = await get_db()

    # Resolve to card_id
    card_id = None
    card_name = ""
    if item.scryfall_id:
        cursor = await db.execute(
            "SELECT id, name FROM cards WHERE scryfall_id = ?", (item.scryfall_id,)
        )
        row = await cursor.fetchone()
        if row:
            card_id = row["id"]
            card_name = row["name"]
    if not card_id and item.card_name:
        cursor = await db.execute(
            "SELECT id, name FROM cards WHERE LOWER(name) = LOWER(?)", (item.card_name.strip(),)
        )
        row = await cursor.fetchone()
        if row:
            card_id = row["id"]
            card_name = row["name"]

    if not card_id:
        raise HTTPException(status_code=404, detail="Card not found in database. Sync collection first.")

    try:
        cursor = await db.execute(
            "INSERT INTO wishlist (card_id, target_price_eur, notes) VALUES (?, ?, ?)",
            (card_id, item.target_price_eur, item.notes.strip()),
        )
        await db.commit()
        return WishlistItemResponse(
            id=cursor.lastrowid or 0,
            card_id=card_id,
            target_price_eur=item.target_price_eur,
            notes=item.notes.strip(),
            card=WishlistCardInfo(name=card_name),
        )
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="Card already on wishlist")
        raise


@router.delete("/{item_id}")
async def remove_from_wishlist(item_id: int):
    db = await get_db()
    cursor = await db.execute(
        "UPDATE wishlist SET removed_at = CURRENT_TIMESTAMP WHERE id = ? AND removed_at IS NULL",
        (item_id,),
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}
