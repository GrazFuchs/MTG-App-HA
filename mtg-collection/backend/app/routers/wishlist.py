"""Wishlist API routes — extended with set/foil/priority/status/deck/tags/acquisition."""
import json
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..database import get_db
from ..models.schemas import (
    AcquisitionStats,
    MonthBucket,
    SourceBucket,
    WishlistAcquireRequest,
    WishlistItemCreate,
    WishlistItemResponse,
    WishlistItemUpdate,
    WishlistOrderRequest,
    WishlistSummary,
)
from ..services.card_resolver import resolve_card

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_tags(tags_csv: str) -> list[str]:
    """Parse comma-separated tags string into a list, filtering empties."""
    if not tags_csv:
        return []
    return [t.strip() for t in tags_csv.split(",") if t.strip()]


def _safe_float(value) -> float | None:
    """Safely convert a price string/value to float or None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _build_item_response(row, current_price: float | None) -> WishlistItemResponse:
    """Build a WishlistItemResponse from a DB row + computed price."""
    target = row["target_price_eur"] or 0
    is_deal = current_price is not None and target > 0 and current_price <= target
    # Compute price delta for acquired items
    paid = _safe_float(row["paid_price_eur"]) if "paid_price_eur" in row.keys() else None
    price_delta_eur: float | None = None
    price_delta_pct: float | None = None
    if paid is not None and current_price is not None and current_price > 0:
        price_delta_eur = round(paid - current_price, 2)
        price_delta_pct = round((paid - current_price) / current_price * 100, 1)
    return WishlistItemResponse(
        id=row["id"],
        card_id=row["card_id"] or 0,
        card_name=row["card_name"] or "",
        scryfall_id=row["scryfall_id"] or "",
        set_code=row["set_code"],
        set_name=row["set_name"],
        is_foil=bool(row["is_foil"]),
        quantity=row["quantity"] or 1,
        target_price_eur=target,
        priority=row["priority"] or 3,
        status=row["status"] or "wanted",
        deck_id=row["deck_id"],
        deck_name=row["deck_name"],
        tags=_parse_tags(row["tags"] or ""),
        notes=row["notes"] or "",
        added_at=row["added_at"] or "",
        acquired_at=row["acquired_at"],
        current_price_eur=current_price,
        is_deal=is_deal,
        image_uri=row["image_uri"],
        color_identity=json.loads(row["color_identity"] or "[]") if "color_identity" in row.keys() else [],
        is_ordered=bool(row["is_ordered"]) if "is_ordered" in row.keys() else False,
        ordered_at=row["ordered_at"] if "ordered_at" in row.keys() else None,
        expected_price_eur=_safe_float(row["expected_price_eur"]) if "expected_price_eur" in row.keys() else None,
        paid_price_eur=paid,
        source=row["source"] if "source" in row.keys() else None,
        not_received_at=row["not_received_at"] if "not_received_at" in row.keys() else None,
        price_delta_eur=price_delta_eur,
        price_delta_pct=price_delta_pct,
    )


def _get_current_price(row) -> float | None:
    """Extract current price from joined row (prefers cardmarket trend, falls back to scryfall)."""
    cm_price = _safe_float(row["cm_trend"]) if "cm_trend" in row.keys() else None
    if cm_price is not None:
        return cm_price
    if row["is_foil"]:
        return _safe_float(row["price_eur_foil"])
    return _safe_float(row["price_eur"])


_BASE_SELECT = """
    SELECT w.id, w.card_id, w.target_price_eur, w.notes, w.added_at,
           w.set_code, w.is_foil, w.quantity, w.priority, w.status,
           w.deck_id, w.tags, w.acquired_at,
           w.is_ordered, w.ordered_at, w.expected_price_eur,
           w.paid_price_eur, w.source, w.not_received_at,
           c.name AS card_name, c.scryfall_id, c.image_uri,
           c.set_name, c.price_eur, c.price_eur_foil,
           c.color_identity,
           d.name AS deck_name,
           (SELECT ph.trend FROM cardmarket_products cp
            JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
            WHERE LOWER(cp.card_name) = LOWER(c.name)
            ORDER BY ph.date DESC LIMIT 1) AS cm_trend
    FROM wishlist w
    LEFT JOIN cards c ON c.id = w.card_id
    LEFT JOIN decks d ON d.id = w.deck_id
"""


@router.get("/summary", response_model=WishlistSummary)
async def get_wishlist_summary():
    """Aggregate stats for the wishlist (only 'wanted' items)."""
    db = await get_db()
    cursor = await db.execute(f"""
        {_BASE_SELECT}
        WHERE w.removed_at IS NULL AND w.status = 'wanted'
    """)
    rows = await cursor.fetchall()

    total_items = 0
    total_quantity = 0
    total_target_eur = 0.0
    total_current_eur = 0.0
    items_below = 0
    items_above = 0
    items_unknown = 0
    by_priority: dict[int, int] = {}
    deck_counts: dict[int, dict] = {}

    for row in rows:
        total_items += 1
        qty = row["quantity"] or 1
        total_quantity += qty
        target = row["target_price_eur"] or 0
        total_target_eur += target * qty

        price = _get_current_price(row)
        if price is not None:
            total_current_eur += price * qty
            if target > 0 and price <= target:
                items_below += 1
            elif target > 0:
                items_above += 1
        else:
            items_unknown += 1

        prio = row["priority"] or 3
        by_priority[prio] = by_priority.get(prio, 0) + 1

        deck_id = row["deck_id"]
        if deck_id is not None:
            if deck_id not in deck_counts:
                deck_counts[deck_id] = {"deck_id": deck_id, "deck_name": row["deck_name"] or "", "count": 0}
            deck_counts[deck_id]["count"] += 1

    return WishlistSummary(
        total_items=total_items,
        total_quantity=total_quantity,
        total_target_eur=round(total_target_eur, 2),
        total_current_eur=round(total_current_eur, 2),
        items_below_target=items_below,
        items_above_target=items_above,
        items_unknown_price=items_unknown,
        by_priority=by_priority,
        by_deck=list(deck_counts.values()),
    )


@router.get("/export/cardmarket", response_class=PlainTextResponse)
async def export_cardmarket():
    """Plain-text decklist format for Cardmarket Wantlist import."""
    db = await get_db()
    cursor = await db.execute("""
        SELECT w.quantity, c.name
        FROM wishlist w
        LEFT JOIN cards c ON c.id = w.card_id
        WHERE w.removed_at IS NULL AND w.status = 'wanted'
        ORDER BY w.priority DESC, c.name ASC
    """)
    rows = await cursor.fetchall()
    lines = [f"{row['quantity'] or 1} {row['name']}" for row in rows if row["name"]]
    content = "\n".join(lines) + "\n" if lines else ""
    today = date.today().isoformat()
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename=wantlist_{today}.txt"},
    )


@router.get("/export/json")
async def export_json():
    """Full JSON export of the wishlist for backup."""
    db = await get_db()
    cursor = await db.execute(f"""
        {_BASE_SELECT}
        WHERE w.removed_at IS NULL
        ORDER BY w.added_at DESC
    """)
    rows = await cursor.fetchall()
    items = []
    for row in rows:
        price = _get_current_price(row)
        items.append(_build_item_response(row, price).model_dump())
    return {"items": items, "exported_at": date.today().isoformat()}


@router.get("/", response_model=list[WishlistItemResponse])
async def list_wishlist(
    status: str = Query("wanted", description="Filter by status. Use '*' for all, 'ordered' for is_ordered=1."),
    priority: int | None = Query(None, ge=1, le=5, description="Filter by priority"),
    deck_id: int | None = Query(None, description="Filter by deck"),
    tag: str | None = Query(None, description="Filter by tag"),
    color: str = Query("", description="Filter by color: W,U,B,R,G,M,C (CSV)"),
    is_deal_only: bool = Query(False, description="Only items where current <= target"),
    is_ordered: Optional[bool] = Query(None, description="Filter by ordered flag"),
    sort: str = Query("priority", description="Sort field: priority|added_at|target_price|current_price|delta_eur"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Paginated wishlist with filters."""
    db = await get_db()

    conditions = ["w.removed_at IS NULL"]
    params: list = []

    if status == "ordered":
        # Convenience alias: ordered = wanted + is_ordered=1
        conditions.append("w.status = 'wanted'")
        conditions.append("w.is_ordered = 1")
    elif status != "*":
        conditions.append("w.status = ?")
        params.append(status)
        if is_ordered is not None:
            conditions.append("w.is_ordered = ?")
            params.append(1 if is_ordered else 0)
    elif is_ordered is not None:
        conditions.append("w.is_ordered = ?")
        params.append(1 if is_ordered else 0)

    if priority is not None:
        conditions.append("w.priority = ?")
        params.append(priority)

    if deck_id is not None:
        conditions.append("w.deck_id = ?")
        params.append(deck_id)

    if tag:
        conditions.append("(',' || w.tags || ',') LIKE ?")
        params.append(f"%,{tag.strip()},%")

    if color:
        for clr in color.split(","):
            clr = clr.strip().upper()
            if clr in ("W", "U", "B", "R", "G"):
                conditions.append(
                    "(c.color_identity LIKE ? AND c.color_identity NOT LIKE '%,%')"
                )
                params.append(f'%"{clr}"%')
            elif clr == "M":
                conditions.append("c.color_identity LIKE '%,%'")
            elif clr == "C":
                conditions.append("(c.color_identity = '[]' OR c.color_identity IS NULL)")

    where_clause = " AND ".join(conditions)

    # Determine sort
    sort_map = {
        "priority": "w.priority DESC, w.added_at DESC",
        "added_at": "w.added_at DESC",
        "target_price": "w.target_price_eur DESC",
        "current_price": "cm_trend DESC",
        "delta_eur": "(COALESCE(cm_trend, 0) - w.target_price_eur) ASC",
    }
    order_by = sort_map.get(sort, sort_map["priority"])

    offset = (page - 1) * page_size
    query = f"""
        {_BASE_SELECT}
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    items = []
    for row in rows:
        price = _get_current_price(row)
        if is_deal_only:
            target = row["target_price_eur"] or 0
            if price is None or target <= 0 or price > target:
                continue
        items.append(_build_item_response(row, price))

    return items


@router.get("/{item_id}", response_model=WishlistItemResponse)
async def get_wishlist_item(item_id: int):
    """Get a single wishlist item by ID."""
    db = await get_db()
    cursor = await db.execute(f"""
        {_BASE_SELECT}
        WHERE w.id = ? AND w.removed_at IS NULL
    """, (item_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    price = _get_current_price(row)
    return _build_item_response(row, price)


@router.post("/")
async def add_to_wishlist(item: WishlistItemCreate):
    """Add a card to the wishlist. Returns owned-check warning if applicable."""
    db = await get_db()

    if not item.card_name and not item.scryfall_id:
        raise HTTPException(status_code=422, detail="Either card_name or scryfall_id is required")

    # Resolve card
    card = await resolve_card(
        db,
        card_name=item.card_name,
        scryfall_id=item.scryfall_id,
        set_code=item.set_code,
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found in database or Scryfall")

    card_id = card["id"]

    # Owned-check: count across all printings of same card name
    cursor = await db.execute(
        """SELECT COALESCE(SUM(col.quantity + col.foil_quantity), 0) as owned
           FROM collection col
           JOIN cards c2 ON c2.id = col.card_id
           WHERE LOWER(c2.name) = LOWER((SELECT name FROM cards WHERE id = ?))""",
        (card_id,),
    )
    owned_row = await cursor.fetchone()
    owned = owned_row["owned"] if owned_row else 0

    warning = None
    if owned >= item.quantity:
        warning = f"You already own {owned} copies in your collection"

    # Validate deck_id if provided
    if item.deck_id is not None:
        cursor = await db.execute("SELECT id FROM decks WHERE id = ?", (item.deck_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=422, detail=f"Deck with id {item.deck_id} does not exist")

    # Insert
    try:
        cursor = await db.execute(
            """INSERT INTO wishlist
               (card_id, set_code, is_foil, quantity, target_price_eur, priority, status, deck_id, tags, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card_id,
                item.set_code,
                int(item.is_foil),
                item.quantity,
                item.target_price_eur,
                item.priority,
                item.status,
                item.deck_id,
                item.tags.strip(),
                item.notes.strip(),
            ),
        )
        await db.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(
                status_code=409,
                detail="Card already on wishlist with this set/foil combination",
            )
        raise

    # Fetch the created item for response
    cursor = await db.execute(f"""
        {_BASE_SELECT}
        WHERE w.id = ?
    """, (new_id,))
    row = await cursor.fetchone()
    price = _get_current_price(row) if row else None
    resp = _build_item_response(row, price) if row else None

    # Publish MQTT sensor for the new wishlist item (fire-and-forget)
    import asyncio
    from ..services.ha_publisher import publish_wishlist_sensor_by_id
    asyncio.create_task(publish_wishlist_sensor_by_id(new_id))

    return {"item": resp, "warning": warning}


@router.patch("/{item_id}", response_model=WishlistItemResponse)
async def update_wishlist_item(item_id: int, updates: WishlistItemUpdate):
    """Partial update of a wishlist item."""
    db = await get_db()

    # Check exists
    cursor = await db.execute(
        "SELECT id FROM wishlist WHERE id = ? AND removed_at IS NULL", (item_id,)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Item not found")

    # Build dynamic SET clause
    fields = []
    params: list = []
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    field_map = {
        "target_price_eur": "target_price_eur",
        "priority": "priority",
        "status": "status",
        "deck_id": "deck_id",
        "tags": "tags",
        "notes": "notes",
        "quantity": "quantity",
    }
    for key, col in field_map.items():
        if key in update_data:
            val = update_data[key]
            if key == "tags" and val is not None:
                val = val.strip()
            if key == "notes" and val is not None:
                val = val.strip()
            fields.append(f"{col} = ?")
            params.append(val)

    # Validate deck_id if being updated
    if "deck_id" in update_data and update_data["deck_id"] is not None:
        cursor = await db.execute("SELECT id FROM decks WHERE id = ?", (update_data["deck_id"],))
        if not await cursor.fetchone():
            raise HTTPException(status_code=422, detail=f"Deck with id {update_data['deck_id']} does not exist")

    # If status changed to 'acquired', set acquired_at
    if update_data.get("status") == "acquired":
        fields.append("acquired_at = CURRENT_TIMESTAMP")

    params.append(item_id)
    await db.execute(
        f"UPDATE wishlist SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    await db.commit()

    # Return updated item
    cursor = await db.execute(f"""
        {_BASE_SELECT}
        WHERE w.id = ?
    """, (item_id,))
    row = await cursor.fetchone()
    price = _get_current_price(row)
    result = _build_item_response(row, price)

    # Update MQTT sensor: remove for terminal statuses, re-publish otherwise
    import asyncio
    from ..services.ha_publisher import publish_wishlist_sensor_by_id, delete_wishlist_sensor
    new_status = update_data.get("status", row["status"] if row else None)
    if new_status in ("acquired", "dropped"):
        asyncio.create_task(delete_wishlist_sensor(item_id))
    else:
        asyncio.create_task(publish_wishlist_sensor_by_id(item_id))

    return result


@router.delete("/{item_id}")
async def remove_from_wishlist(item_id: int):
    """Soft-delete: set removed_at timestamp."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE wishlist SET removed_at = CURRENT_TIMESTAMP WHERE id = ? AND removed_at IS NULL",
        (item_id,),
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    import asyncio
    from ..services.ha_publisher import delete_wishlist_sensor
    asyncio.create_task(delete_wishlist_sensor(item_id))

    return {"ok": True}


@router.post("/{item_id}/order")
async def order_wishlist_item(item_id: int, body: WishlistOrderRequest | None = None):
    """Mark a wishlist item as ordered (bought but not yet received)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, status FROM wishlist WHERE id = ? AND removed_at IS NULL",
        (item_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    if row["status"] == "acquired":
        raise HTTPException(status_code=400, detail="Cannot order an already acquired item")
    if row["status"] == "not_received":
        raise HTTPException(status_code=400, detail="Cannot order an item marked as not received")

    expected = body.expected_price_eur if body else None
    set_code = body.set_code if body else None
    is_foil = body.is_foil if body else None
    await db.execute(
        """UPDATE wishlist SET is_ordered = 1, ordered_at = CURRENT_TIMESTAMP,
           expected_price_eur = COALESCE(?, expected_price_eur),
           set_code = COALESCE(?, set_code),
           is_foil = COALESCE(?, is_foil)
           WHERE id = ?""",
        (expected, set_code, is_foil, item_id),
    )
    await db.commit()
    return {"ok": True, "is_ordered": True}


@router.post("/{item_id}/unorder")
async def unorder_wishlist_item(item_id: int):
    """Undo the ordered flag (e.g. cancelled order)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, is_ordered FROM wishlist WHERE id = ? AND removed_at IS NULL",
        (item_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    if not row["is_ordered"]:
        raise HTTPException(status_code=400, detail="Item is not ordered")

    await db.execute(
        "UPDATE wishlist SET is_ordered = 0, ordered_at = NULL WHERE id = ?",
        (item_id,),
    )
    await db.commit()
    return {"ok": True, "is_ordered": False}


@router.post("/{item_id}/acquire")
async def acquire_wishlist_item(item_id: int, body: WishlistAcquireRequest | None = None):
    """Mark item as acquired with optional paid_price_eur and source."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, status, is_ordered, expected_price_eur FROM wishlist WHERE id = ? AND removed_at IS NULL",
        (item_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    if row["status"] == "acquired":
        raise HTTPException(status_code=400, detail="Already acquired")

    paid_price = None
    source = None
    set_code = None
    is_foil = None
    if body:
        paid_price = body.paid_price_eur
        source = body.source
        set_code = body.set_code
        is_foil = body.is_foil
    # If was ordered and no paid_price given, use expected_price as paid_price
    if paid_price is None and row["is_ordered"] and row["expected_price_eur"] is not None:
        paid_price = row["expected_price_eur"]

    await db.execute(
        """UPDATE wishlist
           SET status = 'acquired', acquired_at = CURRENT_TIMESTAMP,
               is_ordered = 0, paid_price_eur = COALESCE(?, paid_price_eur),
               source = COALESCE(?, source),
               set_code = COALESCE(?, set_code),
               is_foil = COALESCE(?, is_foil)
           WHERE id = ?""",
        (paid_price, source, set_code, is_foil, item_id),
    )
    await db.commit()

    import asyncio
    from ..services.ha_publisher import delete_wishlist_sensor
    asyncio.create_task(delete_wishlist_sensor(item_id))

    return {"ok": True, "status": "acquired"}


@router.post("/{item_id}/mark-not-received")
async def mark_not_received(item_id: int):
    """Mark an ordered item as not received (lost package, refund, etc.)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, status FROM wishlist WHERE id = ? AND removed_at IS NULL",
        (item_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.execute(
        """UPDATE wishlist
           SET status = 'not_received', not_received_at = CURRENT_TIMESTAMP, is_ordered = 0
           WHERE id = ?""",
        (item_id,),
    )
    await db.commit()

    import asyncio
    from ..services.ha_publisher import delete_wishlist_sensor
    asyncio.create_task(delete_wishlist_sensor(item_id))

    return {"ok": True, "status": "not_received"}


@router.get("/acquisitions/stats", response_model=AcquisitionStats)
async def acquisition_stats(days: int = Query(365, ge=1, le=3650)):
    """Aggregate acquired items over a time window."""
    db = await get_db()

    # Total aggregates
    cursor = await db.execute(
        """
        SELECT
            COUNT(*) AS total_acquired,
            COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS total_spent,
            COALESCE(SUM(
                COALESCE(
                    (SELECT ph.trend FROM cardmarket_products cp
                     JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                     WHERE LOWER(cp.card_name) = LOWER(c.name)
                     ORDER BY ph.date DESC LIMIT 1),
                    CAST(NULLIF(c.price_eur, '') AS REAL),
                    0
                ) * w.quantity
            ), 0) AS total_current_value
        FROM wishlist w
        LEFT JOIN cards c ON c.id = w.card_id
        WHERE w.removed_at IS NULL
          AND w.status = 'acquired'
          AND w.acquired_at >= datetime('now', ? || ' days')
        """,
        (f"-{days}",),
    )
    totals = await cursor.fetchone()

    # By source
    cursor = await db.execute(
        """
        SELECT
            COALESCE(w.source, 'unknown') AS source,
            COUNT(*) AS count,
            COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS total_spent,
            COALESCE(SUM(
                COALESCE(
                    (SELECT ph.trend FROM cardmarket_products cp
                     JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                     WHERE LOWER(cp.card_name) = LOWER(c.name)
                     ORDER BY ph.date DESC LIMIT 1),
                    CAST(NULLIF(c.price_eur, '') AS REAL),
                    0
                ) * w.quantity
            ), 0) AS total_value
        FROM wishlist w
        LEFT JOIN cards c ON c.id = w.card_id
        WHERE w.removed_at IS NULL
          AND w.status = 'acquired'
          AND w.acquired_at >= datetime('now', ? || ' days')
        GROUP BY COALESCE(w.source, 'unknown')
        ORDER BY total_spent DESC
        """,
        (f"-{days}",),
    )
    source_rows = await cursor.fetchall()
    by_source = [
        SourceBucket(
            source=r["source"],
            count=r["count"],
            total_spent_eur=round(r["total_spent"], 2),
            total_current_value_eur=round(r["total_value"], 2),
        )
        for r in source_rows
    ]

    # By month (last 12 months in window)
    cursor = await db.execute(
        """
        SELECT
            strftime('%Y-%m', w.acquired_at) AS month,
            COUNT(*) AS count,
            COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS spent
        FROM wishlist w
        WHERE w.removed_at IS NULL
          AND w.status = 'acquired'
          AND w.acquired_at >= datetime('now', ? || ' days')
          AND w.acquired_at IS NOT NULL
        GROUP BY strftime('%Y-%m', w.acquired_at)
        ORDER BY month DESC
        LIMIT 12
        """,
        (f"-{days}",),
    )
    month_rows = await cursor.fetchall()
    by_month = [
        MonthBucket(
            month=r["month"],
            count=r["count"],
            spent=round(r["spent"], 2),
        )
        for r in month_rows
    ]

    return AcquisitionStats(
        total_acquired=totals["total_acquired"],
        total_spent_eur=round(totals["total_spent"], 2),
        total_current_value_eur=round(totals["total_current_value"], 2),
        by_source=by_source,
        by_month=by_month,
    )


@router.post("/{item_id}/restore")
async def restore_wishlist_item(item_id: int):
    """Restore a soft-deleted item (set removed_at = NULL)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, removed_at FROM wishlist WHERE id = ?",
        (item_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    if row["removed_at"] is None:
        raise HTTPException(status_code=400, detail="Item is not deleted")

    await db.execute(
        "UPDATE wishlist SET removed_at = NULL WHERE id = ?",
        (item_id,),
    )
    await db.commit()
    return {"ok": True, "status": "restored"}
