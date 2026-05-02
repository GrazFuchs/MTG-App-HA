"""Cardmarket routes (CSV import/export, API sync, listing)."""
import csv
import io
from datetime import date

from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import get_db
from ..models.schemas import CardmarketListing, CardmarketImportResult
from ..services.cardmarket_import import import_cardmarket_csv
from ..services.cardmarket_prices import get_price_history, get_price_alerts, sync_cardmarket_prices

router = APIRouter()


class AddListingRequest(BaseModel):
    card_name: str
    set_name: str = ""
    set_code: str = ""
    quantity: int = 1
    price: float = 0
    condition: str = "NM"
    language: str = "English"
    is_foil: bool = False
    rarity: str = ""
    comments: str = ""


@router.get("/listings", response_model=list[CardmarketListing])
async def list_cardmarket_listings(
    search: str = Query("", description="Filter by card name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    db = await get_db()
    offset = (page - 1) * page_size

    if search:
        cursor = await db.execute(
            """SELECT * FROM cardmarket_listings
            WHERE card_name LIKE ? ORDER BY card_name LIMIT ? OFFSET ?""",
            (f"%{search}%", page_size, offset),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM cardmarket_listings ORDER BY card_name LIMIT ? OFFSET ?",
            (page_size, offset),
        )

    rows = await cursor.fetchall()
    return [
        CardmarketListing(
            id=r["id"], card_name=r["card_name"], set_name=r["set_name"],
            set_code=r["set_code"], quantity=r["quantity"], price=r["price"],
            condition=r["condition"], language=r["language"],
            is_foil=bool(r["is_foil"]), card_id=r["card_id"],
            imported_at=r["imported_at"],
            article_id=r["article_id"] or "",
            expansion_code=r["expansion_code"] or "",
            rarity=r["rarity"] or "",
            condition_full=r["condition_full"] or "",
            reverse_holo=bool(r["reverse_holo"]),
            comments=r["comments"] or "",
            product_url=r["product_url"] or "",
            source=r["source"] if "source" in r.keys() else "import",
        )
        for r in rows
    ]


@router.get("/stats")
async def cardmarket_stats():
    db = await get_db()
    cursor = await db.execute(
        """SELECT COUNT(*) as count, COALESCE(SUM(quantity), 0) as total_qty,
        COALESCE(SUM(price * quantity), 0) as total_value
        FROM cardmarket_listings"""
    )
    row = await cursor.fetchone()
    return {
        "unique_listings": row[0],
        "total_quantity": row[1],
        "total_value": round(row[2], 2),
    }


@router.post("/import", response_model=CardmarketImportResult)
async def upload_cardmarket_csv(file: UploadFile = File(...)):
    content = await file.read()
    result = await import_cardmarket_csv(content)
    return CardmarketImportResult(**result)


@router.get("/export")
async def export_cardmarket_csv():
    """Export Cardmarket listings as CSV in the official Cardmarket stock export format."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM cardmarket_listings ORDER BY card_name"
    )
    rows = await cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # Header row matching Cardmarket stock export format
    writer.writerow([
        "ArticleID", "Name", "ExpansionCode", "Expansion", "Rarity",
        "Language", "Condition", "ConditionFull", "ReverseHolo",
        "Comments", "Price_EUR", "Amount", "Total_EUR", "ProductUrl",
    ])

    for r in rows:
        article_id = r["article_id"] if r["article_id"] else ""
        # Format ArticleID in Excel-safe ="" wrapper if present
        article_id_formatted = f'="{article_id}"' if article_id else ""

        price = r["price"] or 0
        quantity = r["quantity"] or 1
        total = price * quantity

        # European price format with comma
        price_str = f"{price:.2f}".replace(".", ",")
        total_str = f"{total:.2f}".replace(".", ",")

        reverse_holo = "Y" if r["reverse_holo"] else "N"

        writer.writerow([
            article_id_formatted,
            r["card_name"],
            r["expansion_code"] or "",
            r["set_name"] or "",
            r["rarity"] or "",
            r["language"] or "",
            r["condition"] or "",
            r["condition_full"] or "",
            reverse_holo,
            r["comments"] or "",
            price_str,
            quantity,
            total_str,
            r["product_url"] or "",
        ])

    filename = f"cardmarketUpdate_{date.today().isoformat()}.csv"
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/price-history/{cm_product_id}")
async def get_product_price_history(cm_product_id: int, days: int = Query(30, ge=1, le=365)):
    """Get price history for a Cardmarket product."""
    return await get_price_history(cm_product_id, days)


@router.get("/price-alerts")
async def get_cardmarket_price_alerts():
    """Get price spike alerts for owned cards with unused copies."""
    return await get_price_alerts()


@router.post("/sync-prices")
async def trigger_price_sync():
    """Trigger a manual Cardmarket price data sync."""
    result = await sync_cardmarket_prices()
    return result


@router.get("/products")
async def list_matched_products(search: str = Query("", description="Filter by card name")):
    """List Cardmarket products matched to owned cards."""
    db = await get_db()
    if search:
        cursor = await db.execute(
            """SELECT cm_product_id, card_name, expansion_name
            FROM cardmarket_products WHERE card_name LIKE ?
            ORDER BY card_name LIMIT 100""",
            (f"%{search}%",),
        )
    else:
        cursor = await db.execute(
            "SELECT cm_product_id, card_name, expansion_name FROM cardmarket_products ORDER BY card_name LIMIT 100"
        )
    rows = await cursor.fetchall()
    return [{"cm_product_id": r[0], "card_name": r[1], "expansion": r[2]} for r in rows]


@router.post("/add-listing")
async def add_cardmarket_listing(req: AddListingRequest):
    """Add a manual listing to Cardmarket stock."""
    db = await get_db()
    await db.execute(
        """INSERT INTO cardmarket_listings
        (card_name, set_name, set_code, quantity, price, condition, language, is_foil, rarity, comments, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
        (req.card_name, req.set_name, req.set_code, req.quantity, req.price,
         req.condition, req.language, req.is_foil, req.rarity, req.comments),
    )
    await db.commit()
    return {"status": "created"}


@router.delete("/clear-listings")
async def clear_all_listings():
    """Delete all Cardmarket listings."""
    db = await get_db()
    await db.execute("DELETE FROM cardmarket_listings")
    await db.commit()
    return {"status": "cleared"}
