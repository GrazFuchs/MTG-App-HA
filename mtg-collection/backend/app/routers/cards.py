"""Card search routes (Scryfall proxy)."""
from fastapi import APIRouter, Query
from ..clients.scryfall import scryfall
from ..clients.edhrec import edhrec, parse_edhrec_recommendations, parse_edhrec_combos, slugify_commander

router = APIRouter()


@router.get("/search")
async def search_cards(q: str = Query(..., description="Scryfall search query"), page: int = 1):
    data = await scryfall.search_cards(q, page=page)
    return data


@router.get("/named")
async def get_card_by_name(name: str = Query(...), exact: bool = True):
    return await scryfall.get_card_by_name(name, exact=exact)


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
