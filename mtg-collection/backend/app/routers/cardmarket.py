"""Cardmarket routes (CSV import/export, API sync, listing)."""
import csv
import io
import json
import logging
from datetime import date

from fastapi import APIRouter, Query, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import get_db
from ..models.schemas import CardmarketListing, CardmarketImportResult, CardResponse
from ..services.queries import parse_color_identity
from ..services.cardmarket_import import import_cardmarket_csv
from ..services.cardmarket_prices import get_price_history, get_price_alerts, sync_cardmarket_prices
from ..services.listing_health import analyze_listings

logger = logging.getLogger(__name__)
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


@router.get("/listings")
async def list_cardmarket_listings(
    search: str = Query("", description="Filter by card name"),
    color: str = Query("", description="W/U/B/R/G/M/C/L"),
    set_code: str = Query("", description="Filter by set code"),
    source: str = Query("", description="manual | import"),
    sort_by: str = Query("name", description="name, price, qty, set, color, source"),
    sort_dir: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    db = await get_db()
    offset = (page - 1) * page_size

    conditions = ["1=1"]
    params: list = []

    if search:
        conditions.append("l.card_name LIKE ?")
        params.append(f"%{search}%")
    if set_code:
        conditions.append("LOWER(l.set_code) = LOWER(?)")
        params.append(set_code)
    if source in ("manual", "import"):
        conditions.append("l.source = ?")
        params.append(source)

    # Color filter/sort applied in Python after resolving the matching card.
    color_filter = color.upper() if color.upper() in ("W", "U", "B", "R", "G", "M", "C", "L") else ""

    # Listing-level sort done in SQL; the "color" sort is applied in Python below
    # since the colour comes from the joined card.
    sort_map = {
        "name": "LOWER(l.card_name)",
        "price": "l.price",
        "qty": "l.quantity",
        "set": "LOWER(l.set_code)",
        "source": "CASE WHEN l.source = 'manual' THEN 0 ELSE 1 END",
    }
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
    sql_sort = sort_map.get(sort_by)
    order_sql = (
        f"ORDER BY {sql_sort} {direction}, LOWER(l.card_name) ASC"
        if sql_sort else "ORDER BY LOWER(l.card_name) ASC"
    )

    where = " AND ".join(conditions)

    # Fetch listing rows plainly. We intentionally do NOT join cards in SQL via a
    # correlated subquery (that errored with "no such column" on some SQLite
    # builds, making the whole listings view come back empty). Instead we resolve
    # exactly one best-match card per listing in Python — which also prevents the
    # earlier row multiplication when a card name has several printings.
    listing_rows = await (await db.execute(
        f"SELECT l.* FROM cardmarket_listings l WHERE {where} {order_sql}", params
    )).fetchall()

    # Pre-fetch candidate cards for the listing names in one query.
    names = {(r["card_name"] or "").lower() for r in listing_rows if r["card_name"]}
    cards_by_name: dict[str, list] = {}
    if names:
        placeholders = ",".join("?" * len(names))
        card_rows = await (await db.execute(
            f"SELECT * FROM cards WHERE LOWER(name) IN ({placeholders}) ORDER BY updated_at DESC",
            list(names),
        )).fetchall()
        for cr in card_rows:
            cards_by_name.setdefault((cr["name"] or "").lower(), []).append(cr)

    def _match_card(listing):
        candidates = cards_by_name.get((listing["card_name"] or "").lower(), [])
        if not candidates:
            return None
        lset = (listing["set_code"] or "").lower()
        if lset:
            for cr in candidates:
                if (cr["set_code"] or "").lower() == lset:
                    return cr
        return candidates[0]  # already ordered by updated_at DESC

    def _color_bucket(card) -> str:
        if card is None:
            return "C"
        ci = parse_color_identity(card["color_identity"])
        if "Land" in (card["type_line"] or ""):
            return "L"
        if len(ci) == 0:
            return "C"
        if len(ci) >= 2:
            return "M"
        return ci[0]

    enriched = [(r, _match_card(r)) for r in listing_rows]

    if color_filter:
        enriched = [(lst, card) for (lst, card) in enriched if _color_bucket(card) == color_filter]

    if sort_by == "color":
        order_index = {"W": 1, "U": 2, "B": 3, "R": 4, "G": 5, "M": 6, "C": 7, "L": 8}

        def _color_key(pair):
            listing, card = pair
            return order_index.get(_color_bucket(card), 9), (listing["card_name"] or "").lower()

        enriched.sort(key=_color_key, reverse=(direction == "DESC"))

    total = len(enriched)
    page_rows = enriched[offset:offset + page_size]

    result = []
    for r, card_row in page_rows:
        card_obj: CardResponse | None = None
        if card_row is not None:
            card_obj = CardResponse(
                id=card_row["id"],
                scryfall_id=card_row["scryfall_id"] or "",
                oracle_id=card_row["oracle_id"],
                name=card_row["name"] or "",
                mana_cost=card_row["mana_cost"] or "",
                cmc=card_row["cmc"] or 0,
                type_line=card_row["type_line"] or "",
                oracle_text=card_row["oracle_text"] or "",
                colors=parse_color_identity(card_row["colors"]),
                color_identity=parse_color_identity(card_row["color_identity"]),
                set_code=card_row["set_code"] or "",
                set_name=card_row["set_name"] or "",
                collector_number=card_row["collector_number"] or "",
                rarity=card_row["rarity"] or "",
                image_uri=card_row["image_uri"] or "",
                image_art_crop=card_row["image_art_crop"] or "",
                power=card_row["power"] or "",
                toughness=card_row["toughness"] or "",
                loyalty=card_row["loyalty"] or "",
                keywords=json.loads(card_row["keywords"] or "[]"),
                edhrec_rank=card_row["edhrec_rank"],
                price_usd=card_row["price_usd"] or "",
                price_eur=card_row["price_eur"] or "",
                price_usd_foil=card_row["price_usd_foil"] or "",
                price_eur_foil=card_row["price_eur_foil"] or "",
                updated_at=card_row["updated_at"],
            )
        result.append(CardmarketListing(
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
            card=card_obj,
        ))
    return {"items": result, "total": total, "page": page, "page_size": page_size}


@router.get("/stats")
async def cardmarket_stats(response: Response):
    response.headers["Cache-Control"] = "public, max-age=30"
    db = await get_db()
    cursor = await db.execute(
        """SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT card_name) as unique_cards,
            COALESCE(SUM(quantity), 0) as total_quantity,
            COALESCE(SUM(price * quantity), 0) as total_value
        FROM cardmarket_listings"""
    )
    row = await cursor.fetchone()
    return {
        "unique_cards": row[1],
        "total_rows": row[0],
        "total_quantity": row[2],
        "total_value": round(row[3], 2),
        # Backward-compat: kept for HA MQTT publisher (deprecated, remove next sprint)
        "unique_listings": row[0],
    }


@router.post("/import", response_model=CardmarketImportResult)
async def upload_cardmarket_csv(file: UploadFile = File(...)):
    content = await file.read()
    logger.info(
        "Cardmarket CSV upload: filename=%r, content_type=%r, size=%d bytes",
        file.filename, file.content_type, len(content),
    )
    if not content:
        logger.error("Cardmarket CSV upload: received empty file body")
        return CardmarketImportResult(
            total_rows=0, imported=0, errors=1,
            error_details=["Upload received empty file. This may be a Home Assistant Ingress issue — try reloading the page."],
        )
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


@router.get("/listings/health")
async def listing_health(threshold_pct: float = Query(15.0, ge=0, le=100)):
    """Analyze Cardmarket listings vs current trend price.

    Returns four buckets: underpriced, overpriced, fair, no_match.
    """
    return await analyze_listings(threshold_pct)
