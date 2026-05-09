"""Card search routes (Scryfall proxy)."""
from fastapi import APIRouter, HTTPException, Query
from ..clients.scryfall import scryfall
from ..clients.edhrec import edhrec, parse_edhrec_recommendations, parse_edhrec_combos, slugify_commander
from ..models.schemas import CardPrinting
from ..database import get_db

router = APIRouter()


@router.get("/printings", response_model=list[CardPrinting])
async def get_card_printings(name: str = Query(..., description="Exact card name")):
    """Get all printings of a card across all sets (cached 24h)."""
    printings = await scryfall.get_card_printings(name)
    if not printings:
        raise HTTPException(status_code=404, detail=f"No printings found for '{name}'")
    return printings


@router.get("/search")
async def search_cards(q: str = Query(..., description="Scryfall search query"), page: int = 1):
    data = await scryfall.search_cards(q, page=page)
    # Enrich with owned_quantity and in_decks
    cards = data.get("data", [])
    if cards:
        db = await get_db()
        names = [c.get("name", "") for c in cards]
        # Batch lookup ownership
        placeholders = ",".join(["?"] * len(names))
        cursor = await db.execute(
            f"""SELECT c.name,
                   COALESCE(SUM(col.quantity), 0) as owned_quantity,
                   COALESCE(SUM(col.foil_quantity), 0) as owned_foil_quantity
            FROM cards c
            LEFT JOIN collection col ON col.card_id = c.id
            WHERE c.name IN ({placeholders})
            GROUP BY c.name""",
            names,
        )
        ownership: dict[str, dict] = {}
        for r in await cursor.fetchall():
            ownership[r["name"]] = {
                "owned_quantity": r["owned_quantity"],
                "owned_foil_quantity": r["owned_foil_quantity"],
            }

        # Batch lookup deck usage
        cursor = await db.execute(
            f"""SELECT c.name, GROUP_CONCAT(DISTINCT d.name) as deck_names
            FROM cards c
            JOIN deck_cards dc ON dc.card_id = c.id
            JOIN decks d ON d.id = dc.deck_id
            WHERE c.name IN ({placeholders})
            GROUP BY c.name""",
            names,
        )
        deck_usage: dict[str, list[str]] = {}
        for r in await cursor.fetchall():
            deck_usage[r["name"]] = (r["deck_names"] or "").split(",") if r["deck_names"] else []

        # Enrich response
        for card in cards:
            name = card.get("name", "")
            own = ownership.get(name, {})
            card["owned_quantity"] = own.get("owned_quantity", 0)
            card["owned_foil_quantity"] = own.get("owned_foil_quantity", 0)
            card["in_decks"] = deck_usage.get(name, [])

    return data


@router.get("/named")
async def get_card_by_name(name: str = Query(...), exact: bool = True):
    data = await scryfall.get_card_by_name(name, exact=exact)
    # Enrich with owned info
    db = await get_db()
    cursor = await db.execute(
        """SELECT COALESCE(SUM(col.quantity), 0) as owned_quantity,
               COALESCE(SUM(col.foil_quantity), 0) as owned_foil_quantity
        FROM cards c
        LEFT JOIN collection col ON col.card_id = c.id
        WHERE LOWER(c.name) = LOWER(?)""",
        (data.get("name", name),),
    )
    row = await cursor.fetchone()
    if row:
        data["owned_quantity"] = row["owned_quantity"]
        data["owned_foil_quantity"] = row["owned_foil_quantity"]
    else:
        data["owned_quantity"] = 0
        data["owned_foil_quantity"] = 0

    # Deck usage
    cursor = await db.execute(
        """SELECT GROUP_CONCAT(DISTINCT d.name) as deck_names
        FROM cards c
        JOIN deck_cards dc ON dc.card_id = c.id
        JOIN decks d ON d.id = dc.deck_id
        WHERE LOWER(c.name) = LOWER(?)""",
        (data.get("name", name),),
    )
    row = await cursor.fetchone()
    data["in_decks"] = (row["deck_names"] or "").split(",") if row and row["deck_names"] else []

    return data


@router.get("/autocomplete")
async def autocomplete(q: str = Query(..., min_length=2)):
    suggestions = await scryfall.autocomplete(q)
    return {"data": suggestions}


@router.get("/edhrec/recommendations/{commander_name}")
async def get_edhrec_recommendations(commander_name: str):
    slug = slugify_commander(commander_name)
    data = await edhrec.get_commander_recommendations(slug)
    if not data:
        return {"recommendations": [], "error": "No data found"}
    recs = parse_edhrec_recommendations(data)
    return {"recommendations": recs}


@router.get("/edhrec/combos/{commander_name}")
async def get_edhrec_combos(commander_name: str):
    slug = slugify_commander(commander_name)
    data = await edhrec.get_combos(slug)
    if not data:
        return {"combos": [], "error": "No data found"}
    combos = parse_edhrec_combos(data)
    return {"combos": combos}
