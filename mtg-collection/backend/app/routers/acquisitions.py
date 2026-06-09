"""Acquisitions / Inbox triage API routes."""
import json

from fastapi import APIRouter, HTTPException, Query

from ..clients.scryfall import parse_scryfall_card, scryfall
from ..database import get_db
from ..models.schemas import (
    AcquisitionEventResponse,
    CardResponse,
    InboxAcquisitionStats,
    TriageDecisionRequest,
)
from ..services.queries import basic_land_exclusion_sql
from ..services.sync_service import upsert_card
from ..services.triage_advisor import get_suggestion

router = APIRouter()


# Colour-bucket ordering used for the "color" sort, mirroring the Inbox headers.
_COLOR_ORDER_SQL = """
    CASE
        WHEN COALESCE(c.color_identity, '[]') IN ('[]', '') THEN 7
        WHEN c.color_identity LIKE '%,%' THEN 6
        WHEN c.color_identity LIKE '%"W"%' THEN 1
        WHEN c.color_identity LIKE '%"U"%' THEN 2
        WHEN c.color_identity LIKE '%"B"%' THEN 3
        WHEN c.color_identity LIKE '%"R"%' THEN 4
        WHEN c.color_identity LIKE '%"G"%' THEN 5
        ELSE 8
    END
"""


def _pending_filter_conditions(search: str, color: str) -> tuple[list[str], list]:
    """Build optional name-search / colour-bucket conditions for /pending."""
    conditions: list[str] = []
    params: list = []
    if search:
        conditions.append("c.name LIKE ?")
        params.append(f"%{search}%")
    clr = color.strip()
    if clr in ("W", "U", "B", "R", "G"):
        # Mono of this colour (matches the single-colour Inbox header buckets).
        conditions.append("(c.color_identity LIKE ? AND c.color_identity NOT LIKE '%,%')")
        params.append(f'%"{clr}"%')
    elif clr == "Multi":
        conditions.append("c.color_identity LIKE '%,%'")
    elif clr == "Colorless":
        conditions.append("COALESCE(c.color_identity, '[]') IN ('[]', '')")
    return conditions, params


def _pending_order_by(sort: str) -> str:
    """Map a sort key to an ORDER BY clause for /pending."""
    if sort == "set":
        return "LOWER(c.set_name) ASC, LOWER(c.name) ASC"
    if sort == "name":
        return "LOWER(c.name) ASC"
    if sort == "color":
        return f"{_COLOR_ORDER_SQL} ASC, LOWER(c.name) ASC"
    return "ae.created_at DESC"


def _build_card_response(r) -> CardResponse:
    return CardResponse(
        id=r["id"],
        scryfall_id=r["scryfall_id"],
        oracle_id=r["oracle_id"],
        name=r["name"],
        mana_cost=r["mana_cost"],
        cmc=r["cmc"],
        type_line=r["type_line"],
        oracle_text=r["oracle_text"],
        colors=json.loads(r["colors"] or "[]"),
        color_identity=json.loads(r["color_identity"] or "[]"),
        set_code=r["set_code"],
        set_name=r["set_name"],
        collector_number=r["collector_number"],
        rarity=r["rarity"],
        image_uri=r["image_uri"],
        image_art_crop=r["image_art_crop"],
        power=r["power"],
        toughness=r["toughness"],
        loyalty=r["loyalty"],
        keywords=json.loads(r["keywords"] or "[]"),
        edhrec_rank=r["edhrec_rank"],
        price_usd=r["price_usd"],
        price_eur=r["price_eur"],
        price_usd_foil=r["price_usd_foil"],
        price_eur_foil=r["price_eur_foil"],
        updated_at=r["updated_at"],
    )


@router.get("/pending")
async def list_pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_value_eur: float = Query(0, ge=0),
    filter: str = Query("", description="needs_sell | needs_keep | empty = all pending"),
    search: str = Query("", description="Filter by card name"),
    color: str = Query("", description="Colour bucket: W/U/B/R/G/Multi/Colorless"),
    sort: str = Query("newest", description="newest | set | name | color"),
):
    db = await get_db()

    # Shared WHERE/ORDER built from basic-land exclusion + optional filters.
    value_filter = ""
    value_params: list = []
    if min_value_eur > 0:
        value_filter = " AND CAST(COALESCE(NULLIF(c.price_eur, ''), '0') AS REAL) >= ?"
        value_params.append(min_value_eur)

    extra_conditions, extra_params = _pending_filter_conditions(search, color)
    extra_sql = "".join(f" AND {c}" for c in extra_conditions)
    order_by = _pending_order_by(sort)

    where_clause = (
        "WHERE ae.triage_state = 'pending' "
        f"AND {basic_land_exclusion_sql('c')}{value_filter}{extra_sql}"
    )
    filter_params: list = value_params + extra_params

    # When a suggestion filter is applied, we must compute all items to filter post-query
    needs_suggestion_filter = filter in ("needs_sell", "needs_keep")

    if needs_suggestion_filter:
        # Load all pending (no pagination at SQL level)
        cursor = await db.execute(
            f"""SELECT ae.*, c.*,
                ae.id as event_id, ae.condition as event_condition,
                ae.language as event_language, ae.created_at as event_created_at,
                ae.notes as event_notes
            FROM acquisition_events ae
            JOIN cards c ON c.id = ae.card_id
            {where_clause}
            ORDER BY {order_by}""",
            list(filter_params),
        )
        all_rows = await cursor.fetchall()

        all_items = []
        for r in all_rows:
            card = _build_card_response(r)
            event_row = {
                "id": r["event_id"],
                "card_id": r["card_id"],
                "collection_id": r["collection_id"],
                "is_foil": bool(r["is_foil"]),
                "qty_delta": r["qty_delta"],
            }
            suggestion, existing_printings, in_decks = await get_suggestion(db, event_row)
            all_items.append(AcquisitionEventResponse(
                id=r["event_id"],
                created_at=r["event_created_at"],
                qty_delta=r["qty_delta"],
                is_foil=bool(r["is_foil"]),
                condition=r["event_condition"],
                language=r["event_language"],
                triage_state=r["triage_state"],
                card=card,
                in_decks=in_decks,
                existing_printings=existing_printings,
                suggestion=suggestion,
            ))

        if filter == "needs_sell":
            all_items = [i for i in all_items if i.suggestion.action in ("sold_new", "swap")]
        elif filter == "needs_keep":
            all_items = [i for i in all_items if i.suggestion.action == "keep"]

        total = len(all_items)
        offset = (page - 1) * page_size
        items = all_items[offset:offset + page_size]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # Normal (no suggestion filter): paginate at SQL level
    count_cursor = await db.execute(
        f"""SELECT COUNT(*) FROM acquisition_events ae
        JOIN cards c ON c.id = ae.card_id
        {where_clause}""",
        list(filter_params),
    )
    total = (await count_cursor.fetchone())[0]

    offset = (page - 1) * page_size
    query_params = list(filter_params)
    query_params.extend([page_size, offset])

    cursor = await db.execute(
        f"""SELECT ae.*, c.*,
            ae.id as event_id, ae.condition as event_condition,
            ae.language as event_language, ae.created_at as event_created_at,
            ae.notes as event_notes
        FROM acquisition_events ae
        JOIN cards c ON c.id = ae.card_id
        {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?""",
        query_params,
    )
    rows = await cursor.fetchall()

    items = []
    for r in rows:
        card = _build_card_response(r)

        # Build event row dict for advisor
        event_row = {
            "id": r["event_id"],
            "card_id": r["card_id"],
            "collection_id": r["collection_id"],
            "is_foil": bool(r["is_foil"]),
            "qty_delta": r["qty_delta"],
        }
        suggestion, existing_printings, in_decks = await get_suggestion(db, event_row)

        items.append(AcquisitionEventResponse(
            id=r["event_id"],
            created_at=r["event_created_at"],
            qty_delta=r["qty_delta"],
            is_foil=bool(r["is_foil"]),
            condition=r["event_condition"],
            language=r["event_language"],
            triage_state=r["triage_state"],
            card=card,
            in_decks=in_decks,
            existing_printings=existing_printings,
            suggestion=suggestion,
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/stats", response_model=InboxAcquisitionStats)
async def acquisition_stats():
    db = await get_db()

    # Pending count (exclude basic lands)
    cursor = await db.execute(
        f"""SELECT COUNT(*) FROM acquisition_events ae
        JOIN cards c ON c.id = ae.card_id
        WHERE ae.triage_state = 'pending'
          AND {basic_land_exclusion_sql('c')}"""
    )
    pending_count = (await cursor.fetchone())[0]

    # Decided last 30 days
    cursor = await db.execute(
        """SELECT COUNT(*) FROM acquisition_events
        WHERE triage_state != 'pending'
        AND triage_decision_at >= datetime('now', '-30 days')"""
    )
    decided_last_30d = (await cursor.fetchone())[0]

    # By state last 30 days
    cursor = await db.execute(
        """SELECT triage_state, COUNT(*) as cnt FROM acquisition_events
        WHERE triage_state != 'pending'
        AND triage_decision_at >= datetime('now', '-30 days')
        GROUP BY triage_state"""
    )
    by_state_30d = {row["triage_state"]: row["cnt"] for row in await cursor.fetchall()}

    return InboxAcquisitionStats(
        pending_count=pending_count,
        decided_last_30d=decided_last_30d,
        by_state_30d=by_state_30d,
    )


@router.post("/backfill-colors")
async def backfill_colors():
    """Re-fetch colour data from Scryfall for pending-inbox cards that lack it.

    Archidekt occasionally returns a thin card without an oracleCard, leaving
    `color_identity` empty — which makes every card fall into the Colorless
    bucket in the Inbox. This enriches those cards from Scryfall by id.
    """
    db = await get_db()
    cursor = await db.execute(
        f"""SELECT DISTINCT c.id, c.scryfall_id FROM acquisition_events ae
        JOIN cards c ON c.id = ae.card_id
        WHERE ae.triage_state = 'pending'
          AND COALESCE(c.color_identity, '[]') IN ('[]', '')
          AND COALESCE(c.scryfall_id, '') != ''
          AND {basic_land_exclusion_sql('c')}"""
    )
    candidates = await cursor.fetchall()

    enriched = 0
    failed = 0
    for row in candidates:
        try:
            data = await scryfall.get_card_by_id(row["scryfall_id"])
            await upsert_card(db, parse_scryfall_card(data))
            enriched += 1
        except Exception:
            failed += 1
    await db.commit()
    return {"candidates": len(candidates), "enriched": enriched, "failed": failed}


@router.post("/{event_id}/decide")
async def decide_triage(event_id: int, req: TriageDecisionRequest):
    db = await get_db()

    # Fetch event
    cursor = await db.execute(
        "SELECT * FROM acquisition_events WHERE id = ?", (event_id,)
    )
    event = await cursor.fetchone()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event["triage_state"] != "pending":
        raise HTTPException(status_code=400, detail="Already decided")

    # Cross-field validation
    if req.action in ("keep", "sold_new", "swap") and req.source is None:
        raise HTTPException(status_code=422, detail="source is required for keep/sold_new/swap")
    if req.action in ("sold_new", "swap") and req.listing_price_eur is None:
        raise HTTPException(status_code=422, detail="listing_price_eur is required for sold_new/swap")
    if req.sell_qty is not None and req.action == "sold_new":
        if req.sell_qty > event["qty_delta"]:
            raise HTTPException(status_code=422, detail=f"sell_qty ({req.sell_qty}) exceeds qty_delta ({event['qty_delta']})")

    linked_listing_id = None
    triage_state = req.action
    if req.action == "swap":
        triage_state = "swapped"

    if req.action in ("sold_new", "swap"):
        # Determine which card to list
        if req.action == "sold_new":
            # List the new card
            cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (event["card_id"],))
        else:
            # swap: list the old card
            sell_col_id = req.sell_collection_id
            if sell_col_id is None:
                # Compute suggestion to get the default
                event_row = {
                    "card_id": event["card_id"],
                    "collection_id": event["collection_id"],
                    "is_foil": bool(event["is_foil"]),
                    "qty_delta": event["qty_delta"],
                }
                suggestion, _, _ = await get_suggestion(db, event_row)
                sell_col_id = suggestion.sell_collection_id
            if sell_col_id is None:
                raise HTTPException(status_code=422, detail="sell_collection_id required for swap (no suggestion available)")

            cursor = await db.execute(
                """SELECT c.* FROM collection col JOIN cards c ON c.id = col.card_id
                WHERE col.id = ?""",
                (sell_col_id,),
            )

        card_to_list = await cursor.fetchone()
        if not card_to_list:
            raise HTTPException(status_code=400, detail="Card for listing not found")

        # Create cardmarket listing
        is_foil_listing = int(event["is_foil"]) if req.action == "sold_new" else 0
        if req.action == "swap" and sell_col_id is not None:
            # For swap, check if the OLD collection entry is foil
            foil_cursor = await db.execute(
                "SELECT quantity, foil_quantity FROM collection WHERE id = ?", (sell_col_id,)
            )
            foil_row = await foil_cursor.fetchone()
            if foil_row and foil_row["foil_quantity"] > 0 and foil_row["quantity"] == 0:
                is_foil_listing = 1

        listing_cursor = await db.execute(
            """INSERT INTO cardmarket_listings
            (card_name, set_name, set_code, quantity, price, condition, language, is_foil, rarity, comments, source, card_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'triage', ?)""",
            (
                card_to_list["name"],
                card_to_list["set_name"] or "",
                card_to_list["set_code"] or "",
                req.sell_qty if req.action == "sold_new" and req.sell_qty else (req.listing_quantity or 1),
                req.listing_price_eur,
                req.listing_condition or "NM",
                req.listing_language or "English",
                is_foil_listing,
                card_to_list["rarity"] or "",
                card_to_list["id"],
            ),
        )
        linked_listing_id = listing_cursor.lastrowid

    # Update event
    await db.execute(
        """UPDATE acquisition_events
        SET triage_state = ?, triage_decision_at = CURRENT_TIMESTAMP,
            source = ?, linked_listing_id = ?, notes = ?
        WHERE id = ?""",
        (triage_state, req.source, linked_listing_id, req.notes or "", event_id),
    )
    await db.commit()

    return {"status": "ok", "event_id": event_id, "triage_state": triage_state}


@router.post("/{event_id}/undo")
async def undo_triage(event_id: int):
    db = await get_db()

    cursor = await db.execute(
        "SELECT * FROM acquisition_events WHERE id = ?", (event_id,)
    )
    event = await cursor.fetchone()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event["triage_state"] == "pending":
        raise HTTPException(status_code=400, detail="Event is already pending")

    # Delete linked listing if any
    if event["linked_listing_id"]:
        await db.execute(
            "DELETE FROM cardmarket_listings WHERE id = ?",
            (event["linked_listing_id"],),
        )

    # Reset event to pending
    await db.execute(
        """UPDATE acquisition_events
        SET triage_state = 'pending', triage_decision_at = NULL,
            source = NULL, linked_listing_id = NULL, notes = ''
        WHERE id = ?""",
        (event_id,),
    )
    await db.commit()

    return {"status": "ok", "event_id": event_id, "triage_state": "pending"}
