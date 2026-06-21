"""MTGStocks routes: long-term price history, collection movers, buy/sell signals."""
import logging

from fastapi import APIRouter, Query

from ..config import get_settings
from ..services.mtgstocks_prices import (
    get_long_term_history,
    get_collection_movers,
    get_buy_sell_signals,
    sync_mtgstocks_prints,
    sync_mtgstocks_prices,
    sync_mtgstocks_interests,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def mtgstocks_status():
    """Whether the MTGStocks integration is enabled (gates the UI)."""
    return {"enabled": get_settings().mtgstocks_enabled}


@router.get("/price-history/{card_id}")
async def mtgstocks_price_history(card_id: int, days: int = Query(365, ge=1, le=3650)):
    """Long-term MTGStocks (TCGplayer USD) price series for a card, plus all-time high/low."""
    return await get_long_term_history(card_id, days)


@router.get("/movers")
async def mtgstocks_movers(limit: int = Query(40, ge=1, le=200)):
    """Latest market movers among owned cards."""
    return await get_collection_movers(limit)


@router.get("/signals")
async def mtgstocks_signals():
    """Buy signals (wishlist near all-time low) and sell signals (owned near all-time high)."""
    return await get_buy_sell_signals()


@router.post("/sync")
async def mtgstocks_sync():
    """Trigger a full MTGStocks sync (mapping -> prices -> interests)."""
    prints = await sync_mtgstocks_prints()
    prices = await sync_mtgstocks_prices()
    interests = await sync_mtgstocks_interests()
    return {"prints": prints, "prices": prices, "interests": interests}
