"""Home Assistant MQTT Sensor Discovery publisher."""
import json
import logging
from datetime import datetime, timezone

from ..config import get_settings

logger = logging.getLogger(__name__)

DEVICE_INFO = {
    "identifiers": ["mtg-collection-ha"],
    "name": "MTG Collection",
    "manufacturer": "mtg-collection-ha",
    "model": "Add-on",
}

SENSOR_DEFINITIONS = [
    {"key": "total_cards", "name": "Total Cards", "icon": "mdi:cards"},
    {"key": "unique_cards", "name": "Unique Cards", "icon": "mdi:cards-outline"},
    {
        "key": "total_value_eur", "name": "Total Value EUR",
        "device_class": "monetary", "unit": "EUR", "state_class": "measurement",
    },
    {
        "key": "total_value_usd", "name": "Total Value USD",
        "device_class": "monetary", "unit": "USD", "state_class": "measurement",
    },
    {"key": "total_decks", "name": "Total Decks", "icon": "mdi:cards-playing-outline"},
    {"key": "last_sync_status", "name": "Last Sync Status", "icon": "mdi:sync"},
    {"key": "last_sync_at", "name": "Last Sync At", "device_class": "timestamp"},
    {
        "key": "active_price_alerts", "name": "Active Price Alerts",
        "icon": "mdi:alert-decagram",
    },
]


async def publish_discovery():
    """Publish HA MQTT Discovery config for all sensors."""
    settings = get_settings()
    if not settings.mqtt_enabled:
        return

    try:
        import aiomqtt
    except ImportError:
        logger.warning("aiomqtt not installed, MQTT publishing disabled")
        return

    prefix = settings.mqtt_topic_prefix

    try:
        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username or None,
            password=settings.mqtt_password or None,
        ) as client:
            for sensor in SENSOR_DEFINITIONS:
                key = sensor["key"]
                config_topic = f"homeassistant/sensor/mtg_collection_{key}/config"
                config_payload = {
                    "name": sensor["name"],
                    "unique_id": f"mtg_collection_{key}",
                    "state_topic": f"{prefix}/{key}",
                    "device": DEVICE_INFO,
                }
                if "device_class" in sensor:
                    config_payload["device_class"] = sensor["device_class"]
                if "unit" in sensor:
                    config_payload["unit_of_measurement"] = sensor["unit"]
                if "state_class" in sensor:
                    config_payload["state_class"] = sensor["state_class"]
                if "icon" in sensor:
                    config_payload["icon"] = sensor["icon"]

                await client.publish(
                    config_topic,
                    payload=json.dumps(config_payload),
                    retain=True,
                )
            logger.info("MQTT discovery configs published for %d sensors", len(SENSOR_DEFINITIONS))
    except Exception:
        logger.exception("Failed to publish MQTT discovery configs")


async def publish_stats():
    """Fetch stats from DB and publish to MQTT state topics."""
    settings = get_settings()
    if not settings.mqtt_enabled:
        return

    try:
        import aiomqtt
    except ImportError:
        return

    from ..database import get_db

    try:
        db = await get_db()

        # Collection stats
        cursor = await db.execute(
            """SELECT
                COALESCE(SUM(col.quantity + col.foil_quantity), 0),
                COUNT(DISTINCT col.card_id),
                COALESCE(SUM(
                    CASE WHEN c.price_eur != '' THEN CAST(c.price_eur AS REAL) * col.quantity ELSE 0 END
                    + CASE WHEN c.price_eur_foil != '' THEN CAST(c.price_eur_foil AS REAL) * col.foil_quantity ELSE 0 END
                ), 0),
                COALESCE(SUM(
                    CASE WHEN c.price_usd != '' THEN CAST(c.price_usd AS REAL) * col.quantity ELSE 0 END
                    + CASE WHEN c.price_usd_foil != '' THEN CAST(c.price_usd_foil AS REAL) * col.foil_quantity ELSE 0 END
                ), 0)
            FROM collection col JOIN cards c ON c.id = col.card_id"""
        )
        row = await cursor.fetchone()

        cursor2 = await db.execute("SELECT COUNT(*) FROM decks")
        deck_count = (await cursor2.fetchone())[0]

        # Last sync
        cursor3 = await db.execute(
            "SELECT status, finished_at FROM sync_log ORDER BY started_at DESC LIMIT 1"
        )
        sync_row = await cursor3.fetchone()

        # Price alerts count
        try:
            from .cardmarket_prices import get_price_alerts
            alerts = await get_price_alerts()
            alert_count = len(alerts) if isinstance(alerts, list) else 0
        except Exception:
            alert_count = 0

        prefix = settings.mqtt_topic_prefix
        values = {
            "total_cards": int(row[0]),
            "unique_cards": int(row[1]),
            "total_value_eur": round(float(row[2]), 2),
            "total_value_usd": round(float(row[3]), 2),
            "total_decks": deck_count,
            "last_sync_status": sync_row["status"] if sync_row else "never",
            "last_sync_at": sync_row["finished_at"] if sync_row else datetime.now(timezone.utc).isoformat(),
            "active_price_alerts": alert_count,
        }

        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username or None,
            password=settings.mqtt_password or None,
        ) as client:
            for key, value in values.items():
                await client.publish(
                    f"{prefix}/{key}",
                    payload=str(value),
                    retain=True,
                )
        logger.info("MQTT stats published: %d sensors updated", len(values))
    except Exception:
        logger.exception("Failed to publish MQTT stats")
