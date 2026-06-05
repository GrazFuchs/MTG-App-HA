"""Collection API routes."""
import json
from fastapi import APIRouter, HTTPException, Query, Response
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
async def list_collection_sets(response: Response):
    """Return distinct set names present in the collection."""
    response.headers["Cache-Control"] = "public, max-age=60"
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


def _duplicates_conditions(search: str, color: str, set_code: str):
    """Build WHERE conditions shared by duplicates endpoints."""
    conditions = ["COALESCE(c.type_line, '') NOT LIKE '%Basic Land%'"]
    params: list = []

    if search:
        conditions.append("c.name LIKE ?")
        params.append(f"%{search}%")
    if set_code:
        conditions.append("LOWER(c.set_code) = LOWER(?)")
        params.append(set_code)
    if color:
        for clr in color.split(","):
            clr = clr.strip().upper()
            if clr in ("W", "U", "B", "R", "G"):
                # Match monocolor only: must contain the color AND not be multicolor
                conditions.append(
                    "(c.color_identity LIKE ? AND c.color_identity NOT LIKE '%,%')"
                )
                params.append(f'%"{clr}"%')
            elif clr == "M":
                conditions.append("c.color_identity LIKE '%,%'")
            elif clr == "C":
                conditions.append("(c.color_identity = '[]' OR c.color_identity IS NULL)")
            elif clr == "L":
                conditions.append("c.type_line LIKE '%Land%'")

    return " AND ".join(conditions), params


# The core CTE used by both list_duplicates and duplicates/sets.
# It produces one row per (card_id, set_code, is_foil) with extras computed.
_DUPLICATES_CTE = """
    WITH deck_usage AS (
        SELECT c2.name, SUM(dc.quantity) as in_decks
        FROM deck_cards dc JOIN cards c2 ON c2.id = dc.card_id
        GROUP BY c2.name
    ),
    global_owned AS (
        SELECT c3.name, SUM(col2.quantity + col2.foil_quantity) as total_global
        FROM collection col2 JOIN cards c3 ON c3.id = col2.card_id
        GROUP BY c3.name
    ),
    printing_rows AS (
        SELECT c.id as card_id, c.name, c.set_code, c.set_name, c.rarity,
               c.image_uri, c.price_eur, c.price_eur_foil, c.color_identity,
               c.type_line, c.collector_number,
               0 as is_foil,
               SUM(col.quantity) as total_copies,
               COALESCE(du.in_decks, 0) as in_decks,
               COALESCE(go.total_global, 0) as total_global
        FROM collection col
        JOIN cards c ON c.id = col.card_id
        LEFT JOIN deck_usage du ON du.name = c.name
        LEFT JOIN global_owned go ON go.name = c.name
        WHERE {where}
        GROUP BY c.id, c.set_code
        HAVING SUM(col.quantity) > 0

        UNION ALL

        SELECT c.id as card_id, c.name, c.set_code, c.set_name, c.rarity,
               c.image_uri, c.price_eur, c.price_eur_foil, c.color_identity,
               c.type_line, c.collector_number,
               1 as is_foil,
               SUM(col.foil_quantity) as total_copies,
               COALESCE(du.in_decks, 0) as in_decks,
               COALESCE(go.total_global, 0) as total_global
        FROM collection col
        JOIN cards c ON c.id = col.card_id
        LEFT JOIN deck_usage du ON du.name = c.name
        LEFT JOIN global_owned go ON go.name = c.name
        WHERE {where}
        GROUP BY c.id, c.set_code
        HAVING SUM(col.foil_quantity) > 0
    ),
    with_extras AS (
        SELECT pr.*,
               MAX(pr.total_global - pr.in_decks, 0) as extras_global,
               pr.total_copies as extras,
               COALESCE((
                   SELECT SUM(l.quantity) FROM cardmarket_listings l
                   WHERE LOWER(l.card_name) = LOWER(pr.name)
               ), 0) as listed_quantity
        FROM printing_rows pr
        WHERE pr.total_global > pr.in_decks AND pr.total_global > 1
    )
"""


@router.get("/duplicates")
async def list_duplicates(
    search: str = Query("", description="Search by card name"),
    color: str = Query("", description="W,U,B,R,G,M,C,L (CSV)"),
    set_code: str = Query(""),
    include_listed: bool = Query(False, description="Include rows fully covered by listings"),
    sort_by: str = Query("extras_value", description="extras, extras_value, name, set, color"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List duplicate cards at printing level (card+set+foil)."""
    db = await get_db()
    where, params = _duplicates_conditions(search, color, set_code)

    # Build the CTE with conditions injected
    cte = _DUPLICATES_CTE.replace("{where}", where)

    # Having filter: only rows with extras_after_listings > 0 unless include_listed
    having_filter = "" if include_listed else "WHERE extras_after_listings > 0"

    COLOR_ORDER_SQL = """
        CASE
            WHEN type_line LIKE '%Land%' THEN 8
            WHEN color_identity = '[]' THEN 7
            WHEN color_identity LIKE '%,%' THEN 6
            WHEN color_identity LIKE '%"W"%' THEN 1
            WHEN color_identity LIKE '%"U"%' THEN 2
            WHEN color_identity LIKE '%"B"%' THEN 3
            WHEN color_identity LIKE '%"R"%' THEN 4
            WHEN color_identity LIKE '%"G"%' THEN 5
            ELSE 9
        END
    """

    sort_col = {
        "extras": "extras_after_listings",
        "extras_value": "extra_value",
        "name": "LOWER(name)",
        "set": "LOWER(set_name)",
        "color": COLOR_ORDER_SQL,
    }.get(sort_by, "extra_value")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    offset = (page - 1) * page_size

    # params are used twice in the CTE (once per UNION leg)
    doubled_params = params + params

    count_query = f"""
        {cte}
        SELECT COUNT(*) FROM (
            SELECT *, MAX(extras - listed_quantity, 0) as extras_after_listings
            FROM with_extras
        ) sub {having_filter}
    """
    count_cursor = await db.execute(count_query, doubled_params)
    total = (await count_cursor.fetchone())[0]

    final_query = f"""
        {cte},
        final AS (
            SELECT *,
                MAX(extras - listed_quantity, 0) as extras_after_listings,
                CAST(COALESCE(NULLIF(
                    CASE WHEN is_foil THEN price_eur_foil ELSE price_eur END, ''), '0') AS REAL)
                    * MAX(extras - listed_quantity, 0) as extra_value
            FROM with_extras
        )
        SELECT * FROM final
        {having_filter}
        ORDER BY {sort_col} {direction}, LOWER(name) ASC
        LIMIT ? OFFSET ?
    """

    params_q = doubled_params + [page_size, offset]
    cursor = await db.execute(final_query, params_q)
    rows = await cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "card_name": r["name"],
            "set_name": r["set_name"],
            "set_code": r["set_code"],
            "rarity": r["rarity"],
            "image_uri": r["image_uri"],
            "is_foil": bool(r["is_foil"]),
            "price_eur": r["price_eur"] or "",
            "price_eur_foil": r["price_eur_foil"] or "",
            "total_copies": r["total_copies"],
            "in_decks": r["in_decks"],
            "extras": r["extras"],
            "listed_quantity": r["listed_quantity"],
            "extras_after_listings": r["extras_after_listings"],
            "card_id": r["card_id"],
            "collector_number": r["collector_number"],
            "color_identity": json.loads(r["color_identity"] or "[]"),
            "type_line": r["type_line"] or "",
        })

    return {"items": results, "total": total, "page": page, "page_size": page_size}


@router.get("/duplicates/sets")
async def list_duplicate_sets(
    search: str = Query(""),
    color: str = Query(""),
):
    """Return distinct sets that appear in the duplicates result set."""
    db = await get_db()
    where, params = _duplicates_conditions(search, color, "")
    cte = _DUPLICATES_CTE.replace("{where}", where)
    doubled_params = params + params

    query = f"""
        {cte}
        SELECT DISTINCT set_code, set_name
        FROM (
            SELECT *, MAX(extras - listed_quantity, 0) as extras_after_listings
            FROM with_extras
        )
        WHERE extras_after_listings > 0
        ORDER BY set_name
    """
    cursor = await db.execute(query, doubled_params)
    rows = await cursor.fetchall()
    return [{"set_code": r["set_code"], "set_name": r["set_name"]} for r in rows]


@router.get("/duplicates/printings")
async def list_card_printings(
    card_name: str = Query(..., description="Exact card name to find printings for"),
):
    """Return all printings of a card with extras info for cross-set selling."""
    db = await get_db()

    cursor = await db.execute(
        """
        WITH deck_usage AS (
            SELECT c2.name, SUM(dc.quantity) as in_decks
            FROM deck_cards dc JOIN cards c2 ON c2.id = dc.card_id
            GROUP BY c2.name
        ),
        global_owned AS (
            SELECT c3.name, SUM(col2.quantity + col2.foil_quantity) as total_global
            FROM collection col2 JOIN cards c3 ON c3.id = col2.card_id
            GROUP BY c3.name
        ),
        non_foil AS (
            SELECT c.id as card_id, c.name, c.set_code, c.set_name, c.rarity,
                   c.image_uri, c.price_eur, c.price_eur_foil, c.collector_number,
                   0 as is_foil,
                   SUM(col.quantity) as total_copies
            FROM collection col JOIN cards c ON c.id = col.card_id
            WHERE LOWER(c.name) = LOWER(?)
            GROUP BY c.id, c.set_code
            HAVING SUM(col.quantity) > 0
        ),
        foil AS (
            SELECT c.id as card_id, c.name, c.set_code, c.set_name, c.rarity,
                   c.image_uri, c.price_eur, c.price_eur_foil, c.collector_number,
                   1 as is_foil,
                   SUM(col.foil_quantity) as total_copies
            FROM collection col JOIN cards c ON c.id = col.card_id
            WHERE LOWER(c.name) = LOWER(?)
            GROUP BY c.id, c.set_code
            HAVING SUM(col.foil_quantity) > 0
        ),
        all_printings AS (
            SELECT * FROM non_foil UNION ALL SELECT * FROM foil
        )
        SELECT ap.*,
               COALESCE(du.in_decks, 0) as in_decks,
               COALESCE(go.total_global, 0) as total_global,
               COALESCE((
                   SELECT SUM(l.quantity) FROM cardmarket_listings l
                   WHERE LOWER(l.card_name) = LOWER(ap.name)
                     AND LOWER(COALESCE(l.set_code, l.expansion_code, '')) = LOWER(ap.set_code)
                     AND l.is_foil = ap.is_foil
               ), 0) as listed_for_printing
        FROM all_printings ap
        LEFT JOIN deck_usage du ON du.name = ap.name
        LEFT JOIN global_owned go ON go.name = ap.name
        ORDER BY ap.set_name, ap.is_foil
        """,
        (card_name, card_name),
    )
    rows = await cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "card_name": r["name"],
            "set_name": r["set_name"],
            "set_code": r["set_code"],
            "rarity": r["rarity"],
            "image_uri": r["image_uri"],
            "is_foil": bool(r["is_foil"]),
            "price_eur": r["price_eur"] or "",
            "price_eur_foil": r["price_eur_foil"] or "",
            "total_copies": r["total_copies"],
            "in_decks": r["in_decks"],
            "total_global": r["total_global"],
            "listed_for_printing": r["listed_for_printing"],
            "card_id": r["card_id"],
            "collector_number": r["collector_number"],
        })

    return results
