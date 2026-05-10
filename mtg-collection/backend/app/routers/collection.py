"""Collection API routes."""
import json
from fastapi import APIRouter, HTTPException, Query
from ..database import get_db
from ..models.schemas import CollectionEntry, CollectionAddRequest, CardResponse
from ..clients.scryfall import scryfall, parse_scryfall_card
from ..services.sync_service import upsert_card

router = APIRouter()


@router.get("/")
async def list_collection(
    search: str = Query("", description="Search by card name"),
    color: str = Query("", description="Filter by color (W,U,B,R,G)"),
    rarity: str = Query("", description="Filter by rarity"),
    set_code: str = Query("", description="Filter by set code"),
    deck_id: int = Query(0, description="Filter by deck ID (cards used in this deck)"),
    sort_by: str = Query("name", description="Sort field"),
    sort_dir: str = Query("asc", description="Sort direction"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    db = await get_db()
    conditions = []
    params: list = []

    if search:
        conditions.append("c.name LIKE ?")
        params.append(f"%{search}%")
    if color:
        for clr in color.split(","):
            conditions.append("c.color_identity LIKE ?")
            params.append(f'%"{clr.strip()}"%')
    if rarity:
        conditions.append("c.rarity = ?")
        params.append(rarity.lower())
    if set_code:
        conditions.append("c.set_code = ?")
        params.append(set_code.lower())
    if deck_id:
        conditions.append("""c.name IN (
            SELECT c3.name FROM deck_cards dc3
            JOIN cards c3 ON c3.id = dc3.card_id
            WHERE dc3.deck_id = ?
        )""")
        params.append(deck_id)

    where = " AND ".join(conditions) if conditions else "1=1"

    sort_col = {
        "name": "LOWER(c.name)",
        "price_eur": (
            "CAST(CASE "
            "WHEN col.foil_quantity > 0 AND col.quantity = 0 "
            "THEN COALESCE(NULLIF(c.price_eur_foil, ''), NULLIF(c.price_eur, ''), '0') "
            "ELSE COALESCE(NULLIF(c.price_eur, ''), NULLIF(c.price_eur_foil, ''), '0') "
            "END AS REAL)"
        ),
        "price_usd": (
            "CAST(CASE "
            "WHEN col.foil_quantity > 0 AND col.quantity = 0 "
            "THEN COALESCE(NULLIF(c.price_usd_foil, ''), NULLIF(c.price_usd, ''), '0') "
            "ELSE COALESCE(NULLIF(c.price_usd, ''), NULLIF(c.price_usd_foil, ''), '0') "
            "END AS REAL)"
        ),
        "rarity": "LOWER(c.rarity)",
        "set": "LOWER(c.set_name)",
        "quantity": "(col.quantity + col.foil_quantity)",
        "added_at": "col.added_at",
        "date_added": "col.added_at",
        "archidekt_tags": "LOWER(col.archidekt_tags)",
        "tags": "LOWER(col.archidekt_tags)",
    }.get(sort_by, "LOWER(c.name)")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    offset = (page - 1) * page_size

    # Count total matching entries
    count_query = f"""
        SELECT COUNT(*) FROM collection col JOIN cards c ON c.id = col.card_id
        WHERE {where}
    """
    count_cursor = await db.execute(count_query, params[:])
    total = (await count_cursor.fetchone())[0]

    query = f"""
        WITH deck_usage AS (
            SELECT c2.name, SUM(dc.quantity) as total_in_decks
            FROM deck_cards dc
            JOIN cards c2 ON c2.id = dc.card_id
            GROUP BY c2.name
        )
        SELECT c.*, col.id as col_id, col.quantity, col.foil_quantity,
        col.condition, col.language, col.archidekt_tags, col.notes, col.added_at,
        COALESCE(du.total_in_decks, 0) as in_decks,
        COALESCE(cm_match.listing_count, 0) as cardmarket_listing_count,
        COALESCE(cm_match.listed_qty, 0) as cardmarket_listed_qty
        FROM collection col JOIN cards c ON c.id = col.card_id
        LEFT JOIN deck_usage du ON du.name = c.name
        LEFT JOIN (
            SELECT card_id, set_code, is_foil,
                   COUNT(*) as listing_count, SUM(quantity) as listed_qty
            FROM cardmarket_listings
            WHERE card_id IS NOT NULL
            GROUP BY card_id, set_code, is_foil
        ) cm_match ON cm_match.card_id = c.id
                  AND cm_match.set_code = c.set_code
                  AND cm_match.is_foil = (col.foil_quantity > 0 AND col.quantity = 0)
        WHERE {where}
        ORDER BY {sort_col} {direction}, LOWER(c.name) ASC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    results = []
    for r in rows:
        card = CardResponse(
            id=r["id"], scryfall_id=r["scryfall_id"], oracle_id=r["oracle_id"],
            name=r["name"], mana_cost=r["mana_cost"], cmc=r["cmc"],
            type_line=r["type_line"], oracle_text=r["oracle_text"],
            colors=json.loads(r["colors"] or "[]"),
            color_identity=json.loads(r["color_identity"] or "[]"),
            set_code=r["set_code"], set_name=r["set_name"],
            collector_number=r["collector_number"], rarity=r["rarity"],
            image_uri=r["image_uri"], image_art_crop=r["image_art_crop"],
            power=r["power"], toughness=r["toughness"], loyalty=r["loyalty"],
            keywords=json.loads(r["keywords"] or "[]"),
            edhrec_rank=r["edhrec_rank"],
            price_usd=r["price_usd"], price_eur=r["price_eur"],
            price_usd_foil=r["price_usd_foil"], price_eur_foil=r["price_eur_foil"],
            updated_at=r["updated_at"],
        )
        results.append(CollectionEntry(
            id=r["col_id"], card=card, quantity=r["quantity"],
            foil_quantity=r["foil_quantity"], condition=r["condition"],
            language=r["language"], archidekt_tags=r["archidekt_tags"] or "",
            notes=r["notes"] or "",
            added_at=r["added_at"],
            in_decks=r["in_decks"],
            cardmarket_listing_count=r["cardmarket_listing_count"],
            cardmarket_listed_qty=r["cardmarket_listed_qty"],
        ))

    return {"items": results, "total": total, "page": page, "page_size": page_size}


@router.get("/sets")
async def list_collection_sets():
    """Return distinct set names present in the collection."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT DISTINCT c.set_code, c.set_name
        FROM collection col JOIN cards c ON c.id = col.card_id
        WHERE c.set_name != ''
        ORDER BY c.set_name"""
    )
    rows = await cursor.fetchall()
    return [{"set_code": r[0], "set_name": r[1]} for r in rows]


@router.post("/", response_model=CollectionEntry)
async def add_to_collection(req: CollectionAddRequest):
    db = await get_db()

    # Check if card already exists in our DB
    cursor = await db.execute(
        "SELECT id FROM cards WHERE scryfall_id=?", (req.scryfall_id,)
    )
    card_row = await cursor.fetchone()

    if not card_row:
        # Fetch from Scryfall
        try:
            data = await scryfall.get_card_by_id(req.scryfall_id)
            card_data = parse_scryfall_card(data)
            card_id = await upsert_card(db, card_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch card: {e}")
    else:
        card_id = card_row[0]

    await db.execute(
        """INSERT INTO collection (card_id, quantity, foil_quantity, condition, language, archidekt_tags, notes)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(card_id, condition, language) DO UPDATE SET
            quantity = collection.quantity + excluded.quantity,
            foil_quantity = collection.foil_quantity + excluded.foil_quantity""",
        (card_id, req.quantity, req.foil_quantity, req.condition, req.language, "", req.notes),
    )
    await db.commit()

    # Return the created entry
    cursor = await db.execute(
        """SELECT c.*, col.id as col_id, col.quantity, col.foil_quantity,
        col.condition, col.language, col.archidekt_tags, col.notes, col.added_at
        FROM collection col JOIN cards c ON c.id = col.card_id
        WHERE col.card_id=? AND col.condition=? AND col.language=?""",
        (card_id, req.condition, req.language),
    )
    r = await cursor.fetchone()
    card = CardResponse(
        id=r["id"], scryfall_id=r["scryfall_id"], oracle_id=r["oracle_id"],
        name=r["name"], mana_cost=r["mana_cost"], cmc=r["cmc"],
        type_line=r["type_line"], oracle_text=r["oracle_text"],
        colors=json.loads(r["colors"] or "[]"),
        color_identity=json.loads(r["color_identity"] or "[]"),
        set_code=r["set_code"], set_name=r["set_name"],
        collector_number=r["collector_number"], rarity=r["rarity"],
        image_uri=r["image_uri"], image_art_crop=r["image_art_crop"],
        price_usd=r["price_usd"], price_eur=r["price_eur"],
    )
    return CollectionEntry(
        id=r["col_id"], card=card, quantity=r["quantity"],
        foil_quantity=r["foil_quantity"], condition=r["condition"],
        language=r["language"], archidekt_tags=r["archidekt_tags"] or "",
        notes=r["notes"] or "", added_at=r["added_at"],
    )


@router.delete("/{entry_id}")
async def remove_from_collection(entry_id: int):
    db = await get_db()
    await db.execute("DELETE FROM collection WHERE id=?", (entry_id,))
    await db.commit()
    return {"status": "deleted"}


@router.get("/duplicates")
async def list_duplicates(
    search: str = Query("", description="Search by card name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List cards where total owned copies exceed total copies used in decks."""
    db = await get_db()
    conditions = []
    params: list = []

    if search:
        conditions.append("c.name LIKE ?")
        params.append(f"%{search}%")

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    count_query = f"""
        SELECT COUNT(*) FROM (
            SELECT c.name
            FROM collection col JOIN cards c ON c.id = col.card_id
            WHERE {where}
            AND c.type_line NOT LIKE '%Basic Land%'
            GROUP BY c.name
            HAVING SUM(col.quantity + col.foil_quantity) >
                COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc JOIN cards c2 ON c2.id = dc.card_id WHERE c2.name = c.name), 0)
                AND SUM(col.quantity + col.foil_quantity) > 1
        )
    """
    count_cursor = await db.execute(count_query, params[:])
    total = (await count_cursor.fetchone())[0]

    query = f"""
        SELECT c.name, c.set_name, c.set_code, c.rarity, c.image_uri,
            c.price_eur, c.price_eur_foil,
            SUM(col.quantity) as total_qty, SUM(col.foil_quantity) as total_foil,
            COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc JOIN cards c2 ON c2.id = dc.card_id WHERE c2.name = c.name), 0) as in_decks,
            c.id as card_id, c.collector_number
        FROM collection col JOIN cards c ON c.id = col.card_id
        WHERE {where}
        AND c.type_line NOT LIKE '%Basic Land%'
        GROUP BY c.name
        HAVING (total_qty + total_foil) > in_decks AND (total_qty + total_foil) > 1
        ORDER BY (CAST(COALESCE(NULLIF(c.price_eur, ''), '0') AS REAL) *
            ((total_qty + total_foil) - in_decks)) DESC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    results = []
    for r in rows:
        total_copies = r["total_qty"] + r["total_foil"]
        in_decks = r["in_decks"]
        extras = total_copies - in_decks
        results.append({
            "card_name": r["name"],
            "set_name": r["set_name"],
            "set_code": r["set_code"],
            "rarity": r["rarity"],
            "image_uri": r["image_uri"],
            "price_eur": r["price_eur"] or "",
            "price_eur_foil": r["price_eur_foil"] or "",
            "total_copies": total_copies,
            "in_decks": in_decks,
            "extras": extras,
            "card_id": r["card_id"],
            "collector_number": r["collector_number"],
        })

    return {"items": results, "total": total, "page": page, "page_size": page_size}
