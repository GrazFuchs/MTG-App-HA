"""Statistics routes."""
from fastapi import APIRouter, Response
from ..database import get_db
from ..models.schemas import CollectionStats
from ..services.queries import query_collection_stats

router = APIRouter()


@router.get("/", response_model=CollectionStats)
async def get_stats(response: Response):
    response.headers["Cache-Control"] = "public, max-age=30"
    db = await get_db()
    stats = await query_collection_stats(db)
    return CollectionStats(**stats)


@router.get("/value-history")
async def get_value_history(days: int = 90):
    db = await get_db()
    cursor = await db.execute(
        "SELECT date, total_cards, unique_cards, value_eur, value_usd FROM value_snapshots ORDER BY date DESC LIMIT ?",
        (days,),
    )
    rows = await cursor.fetchall()
    return [
        {"date": r["date"], "total_cards": r["total_cards"], "unique_cards": r["unique_cards"],
         "value_eur": r["value_eur"], "value_usd": r["value_usd"]}
        for r in reversed(rows)
    ]
