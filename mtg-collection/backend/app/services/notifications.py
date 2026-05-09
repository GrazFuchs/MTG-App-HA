"""Price-spike notification service (webhook + HA service call + persistent notifications)."""
import logging
import os
from datetime import date
from typing import Any

import httpx

from ..config import get_settings
from ..database import get_db

logger = logging.getLogger(__name__)


def _get_supervisor_token() -> str:
    """Get HA Supervisor token from environment."""
    return os.environ.get("SUPERVISOR_TOKEN", "")


async def send_persistent_notification(
    title: str,
    message: str,
    deep_link: str | None = None,
    notification_id: str | None = None,
) -> None:
    """Create a persistent_notification in HA via Supervisor API.

    Only runs when ``SUPERVISOR_TOKEN`` is present (i.e. inside an HA add-on).

    Args:
        title:           Notification title shown in HA.
        message:         Notification body (Markdown supported).
        deep_link:       Optional relative path within the add-on UI (e.g. "/cardmarket").
                         Resolved to a full Ingress URL automatically.
        notification_id: Optional stable ID; re-creating with the same ID replaces the old one.
    """
    token = _get_supervisor_token()
    if not token:
        return

    if deep_link:
        # Resolve the add-on Ingress slug from the environment; fall back to a
        # generic path that opens the Ingress panel for this add-on.
        ingress_slug = os.environ.get("INGRESS_TOKEN", "")
        if ingress_slug:
            ingress_url = f"/api/hassio_ingress/{ingress_slug}{deep_link}"
        else:
            ingress_url = deep_link
        message = f"{message}\n\n[Open in MTG Collection]({ingress_url})"

    if notification_id is None:
        notification_id = f"mtg_alert_{abs(hash(title)) % 10**8}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://supervisor/core/api/services/persistent_notification/create",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "title": title,
                    "message": message,
                    "notification_id": notification_id,
                },
            )
            resp.raise_for_status()
            logger.info("Persistent notification created: %s", title)
    except Exception:
        logger.exception("Failed to create persistent notification: %s", title)


async def send_price_spike_notifications(alerts: list[dict[str, Any]]) -> int:
    """Filter qualifying alerts and send notifications. Returns count of notifications sent."""
    settings = get_settings()

    has_channels = (
        settings.notify_webhook_url
        or settings.notify_via_ha_service
        or _get_supervisor_token()
    )
    if not has_channels:
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

        # Persistent notification via Supervisor API.
        # send_persistent_notification() never raises (it catches internally), so we
        # guard here to avoid a false-positive: without a token nothing is sent but
        # the function returns without error — we must NOT credit that as a success.
        persistent_ok = False
        if _get_supervisor_token():
            try:
                await send_persistent_notification(
                    title="MTG Price Spike",
                    message=message,
                    deep_link="/cardmarket",
                    notification_id=f"mtg_price_spike_{card_name.lower().replace(' ', '_')[:40]}",
                )
                persistent_ok = True
            except Exception:
                pass  # logged inside send_persistent_notification

        if success or persistent_ok:
            await db.execute(
                "INSERT OR IGNORE INTO notification_log (card_name, alert_date) VALUES (?, ?)",
                (card_name, today),
            )
            sent += 1

    if sent:
        await db.commit()
        logger.info("Sent %d price spike notifications", sent)

    return sent

