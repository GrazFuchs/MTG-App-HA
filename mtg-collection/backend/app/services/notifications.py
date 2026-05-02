"""Price-spike notification service (webhook + HA service call)."""
import logging
from datetime import date
from typing import Any

import httpx

from ..config import get_settings
from ..database import get_db

logger = logging.getLogger(__name__)


async def send_price_spike_notifications(alerts: list[dict[str, Any]]) -> int:
    """Filter qualifying alerts and send notifications. Returns count of notifications sent."""
    settings = get_settings()

    if not settings.notify_webhook_url and not settings.notify_via_ha_service:
        return 0

    db = await get_db()
    today = date.today().isoformat()
    sent = 0

    for alert in alerts:
        trend = alert.get("trend", 0)
        if trend < settings.notify_min_alert_value_eur:
            continue

        card_name = alert["card_name"]

        # Anti-duplicate: check if already notified today
        cursor = await db.execute(
            "SELECT 1 FROM notification_log WHERE card_name = ? AND alert_date = ?",
            (card_name, today),
        )
        if await cursor.fetchone():
            continue

        # Build notification payload
        message = (
            f"Price spike: {card_name} — "
            f"€{alert.get('avg30', 0):.2f} → €{trend:.2f} "
            f"(+{alert.get('spike_pct', 0):.0f}%), "
            f"{alert.get('unused_copies', 0)} unused copies"
        )

        success = False

        # Webhook
        if settings.notify_webhook_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        settings.notify_webhook_url,
                        json={
                            "card_name": card_name,
                            "expansion": alert.get("expansion", ""),
                            "trend": trend,
                            "avg30": alert.get("avg30", 0),
                            "spike_pct": alert.get("spike_pct", 0),
                            "unused_copies": alert.get("unused_copies", 0),
                            "message": message,
                        },
                    )
                    resp.raise_for_status()
                    success = True
            except Exception:
                logger.exception("Webhook notification failed for %s", card_name)

        # HA Service call via Supervisor API
        if settings.notify_via_ha_service:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "http://supervisor/core/api/services/"
                        + settings.notify_via_ha_service.replace(".", "/"),
                        json={
                            "title": "MTG Price Spike",
                            "message": message,
                        },
                        headers={
                            "Authorization": "Bearer " + _get_supervisor_token(),
                        },
                    )
                    resp.raise_for_status()
                    success = True
            except Exception:
                logger.exception("HA service notification failed for %s", card_name)

        if success:
            await db.execute(
                "INSERT OR IGNORE INTO notification_log (card_name, alert_date) VALUES (?, ?)",
                (card_name, today),
            )
            sent += 1

    if sent:
        await db.commit()
        logger.info("Sent %d price spike notifications", sent)

    return sent


def _get_supervisor_token() -> str:
    """Get HA Supervisor token from environment."""
    import os
    return os.environ.get("SUPERVISOR_TOKEN", "")
