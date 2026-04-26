"""Statistics routes."""
from fastapi import APIRouter
from ..database import get_db
from ..models.schemas import CollectionStats
from ..services.queries import query_collection_stats

router = APIRouter()


@router.get("/", response_model=CollectionStats)
async def get_stats():
    db = await get_db()
    stats = await query_collection_stats(db)
    return CollectionStats(**stats)
