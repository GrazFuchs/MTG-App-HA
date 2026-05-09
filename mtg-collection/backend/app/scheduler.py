"""APScheduler-based daily sync scheduler."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _sync_job():
    """Run the sync as a scheduled job."""
    from .services.sync_service import run_full_sync
    from .services.cardmarket_prices import sync_cardmarket_prices
    settings = get_settings()

    if not settings.sync_enabled:
        logger.info("Sync is disabled, skipping scheduled sync")
        return

    # Archidekt sync
    if settings.archidekt_username or settings.archidekt_deck_ids:
        logger.info("Starting scheduled Archidekt sync...")
        try:
            result = await run_full_sync()
            logger.info("Scheduled Archidekt sync completed: %s", result)
        except Exception as e:
            logger.error("Scheduled Archidekt sync failed: %s", e)

    # Cardmarket price data sync (daily)
    logger.info("Starting scheduled Cardmarket price sync...")
    try:
        result = await sync_cardmarket_prices()
        logger.info("Scheduled Cardmarket price sync completed: %s", result)
    except Exception as e:
        logger.error("Scheduled Cardmarket price sync failed: %s", e)

    # Send price spike notifications after price sync
    try:
        from .services.cardmarket_prices import get_price_alerts
        from .services.notifications import send_price_spike_notifications
        alerts = await get_price_alerts()
        if alerts:
            sent = await send_price_spike_notifications(alerts)
            if sent:
                logger.info("Sent %d price spike notifications", sent)
    except Exception as e:
        logger.error("Price spike notifications failed: %s", e)

    # Publish stats to MQTT after all syncs
    try:
        from .services.ha_publisher import publish_stats, publish_wishlist_sensors
        await publish_stats()
        await publish_wishlist_sensors()
    except Exception as e:
        logger.error("MQTT stats/wishlist publish failed: %s", e)

    # Record daily value snapshot
    try:
        from .database import get_db
        from .services.queries import record_value_snapshot
        db = await get_db()
        await record_value_snapshot(db)
        logger.info("Value snapshot recorded")
    except Exception as e:
        logger.error("Value snapshot recording failed: %s", e)


def start_scheduler():
    global _scheduler
    settings = get_settings()

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _sync_job,
        trigger=CronTrigger(hour=settings.sync_hour, minute=0),
        id="daily_archidekt_sync",
        name="Daily Archidekt Sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started. Daily sync at %02d:00", settings.sync_hour)


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def is_scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running
