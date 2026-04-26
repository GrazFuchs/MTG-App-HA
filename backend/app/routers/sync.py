"""Sync management routes."""
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from ..database import get_db
from ..models.schemas import SyncLogEntry, SyncStatus
from ..config import get_settings
from ..services.sync_service import run_full_sync, run_full_resync, is_sync_running
from ..clients.flaresolverr import flaresolverr

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=SyncStatus)
async def get_sync_status():
    db = await get_db()
    settings = get_settings()

    cursor = await db.execute(
        "SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 1"
    )
    row = await cursor.fetchone()

    last_sync = None
    if row:
        last_sync = SyncLogEntry(
            id=row["id"], source=row["source"], status=row["status"],
            started_at=row["started_at"], finished_at=row["finished_at"],
            items_synced=row["items_synced"], error=row["error"] or "",
        )

    cursor2 = await db.execute("SELECT COUNT(*) FROM decks")
    deck_count = (await cursor2.fetchone())[0]

    flaresolverr_available = False
    if flaresolverr.is_configured:
        try:
            flaresolverr_available = await flaresolverr.is_available()
        except Exception:
            logger.exception("FlareSolverr availability check failed")

    return SyncStatus(
        last_sync=last_sync,
        sync_enabled=settings.sync_enabled,
        next_sync_hour=settings.sync_hour,
        archidekt_username=settings.archidekt_username,
        archidekt_authenticated=bool(settings.archidekt_password),
        cardmarket_configured=bool(settings.cardmarket_username),
        flaresolverr_configured=flaresolverr.is_configured,
        flaresolverr_available=flaresolverr_available,
        synced_decks=deck_count,
    )


@router.post("/trigger")
async def trigger_sync(background_tasks: BackgroundTasks):
    if is_sync_running():
        raise HTTPException(status_code=409, detail="A sync is already in progress")
    background_tasks.add_task(_run_sync)
    return {"status": "sync_started"}


@router.post("/trigger-resync")
async def trigger_resync(background_tasks: BackgroundTasks):
    if is_sync_running():
        raise HTTPException(status_code=409, detail="A sync is already in progress")
    background_tasks.add_task(_run_resync)
    return {"status": "resync_started"}


async def _run_resync():
    try:
        await run_full_resync()
    except Exception:
        logger.exception("Background resync crashed")
    # Also sync Cardmarket
    try:
        from ..services.cardmarket_import import sync_cardmarket_stock
        from ..config import get_settings
        if get_settings().cardmarket_username:
            await sync_cardmarket_stock()
    except Exception:
        logger.exception("Background cardmarket sync (after resync) crashed")
    # Publish updated stats to MQTT
    try:
        from ..services.ha_publisher import publish_stats
        await publish_stats()
    except Exception:
        logger.exception("MQTT stats publish after resync failed")


async def _run_sync():
    try:
        await run_full_sync()
    except Exception:
        logger.exception("Background sync crashed")
    # Also sync Cardmarket
    try:
        from ..services.cardmarket_import import sync_cardmarket_stock
        from ..config import get_settings
        if get_settings().cardmarket_username:
            await sync_cardmarket_stock()
    except Exception:
        logger.exception("Background cardmarket sync crashed")
    # Publish updated stats to MQTT
    try:
        from ..services.ha_publisher import publish_stats
        await publish_stats()
    except Exception:
        logger.exception("MQTT stats publish after sync failed")


@router.get("/history", response_model=list[SyncLogEntry])
async def get_sync_history():
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 20"
    )
    rows = await cursor.fetchall()
    return [
        SyncLogEntry(
            id=r["id"], source=r["source"], status=r["status"],
            started_at=r["started_at"], finished_at=r["finished_at"],
            items_synced=r["items_synced"], error=r["error"] or "",
        )
        for r in rows
    ]


@router.get("/probe-archidekt")
async def probe_archidekt():
    """Debug endpoint: check Archidekt API connectivity."""
    from ..clients.archidekt import archidekt

    results = {"authenticated": archidekt.is_authenticated}

    if not archidekt.is_authenticated:
        settings = get_settings()
        if settings.archidekt_username and settings.archidekt_password:
            await archidekt.login(settings.archidekt_username, settings.archidekt_password)
            results["authenticated"] = archidekt.is_authenticated

    if not archidekt.is_authenticated:
        results["note"] = "Not authenticated"

    return results
