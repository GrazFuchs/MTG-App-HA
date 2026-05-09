"""Home Assistant MQTT Sensor Discovery publisher."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from ..config import get_settings
from ..version import VERSION

logger = logging.getLogger(__name__)

DEVICE_INFO = {
    "identifiers": ["mtg-collection-ha"],
    "name": "MTG Collection",
    "manufacturer": "mtg-collection-ha",
    "model": "Add-on",
}

# Device block used for per-item wishlist sensors
_WISHLIST_DEVICE_INFO = {
    "identifiers": ["mtg_collection_manager"],
    "name": "MTG Collection Manager",
    "model": f"v{VERSION}",
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
    # Spending / acquisition sensors (last 30 days)
    {
        "key": "spending_30d", "name": "MTG Spending 30d",
        "device_class": "monetary", "unit": "EUR", "state_class": "measurement",
        "icon": "mdi:cash-multiple",
    },
    {
        "key": "spending_30d_value", "name": "MTG Acquired Value 30d",
        "device_class": "monetary", "unit": "EUR", "state_class": "measurement",
        "icon": "mdi:trending-up",
    },
    {
        "key": "acquired_count_30d", "name": "MTG Acquired Count 30d",
        "icon": "mdi:cards-playing-heart-multiple",
    },
    # Listing health sensors
    {"key": "listings_underpriced", "name": "MTG Listings Underpriced", "icon": "mdi:tag-arrow-down"},
    {"key": "listings_overpriced", "name": "MTG Listings Overpriced", "icon": "mdi:tag-arrow-up"},
    {"key": "listings_fair", "name": "MTG Listings Fair", "icon": "mdi:tag-check"},
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

        # Spending stats (last 30 days)
        spending_30d = 0.0
        spending_30d_value = 0.0
        acquired_count_30d = 0
        try:
            from .queries import query_spending_stats_30d
            spending = await query_spending_stats_30d(db)
            spending_30d = spending["total_spent_eur"]
            spending_30d_value = spending["total_current_value_eur"]
            acquired_count_30d = spending["count"]
        except Exception:
            logger.debug("Could not fetch spending stats for MQTT")

        # Listing health counts
        listings_underpriced = 0
        listings_overpriced = 0
        listings_fair = 0
        try:
            from .listing_health import analyze_listings
            health = await analyze_listings()
            listings_underpriced = len(health.get("underpriced", []))
            listings_overpriced = len(health.get("overpriced", []))
            listings_fair = len(health.get("fair", []))
        except Exception:
            logger.debug("Could not fetch listing health for MQTT")

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
            "spending_30d": spending_30d,
            "spending_30d_value": spending_30d_value,
            "acquired_count_30d": acquired_count_30d,
            "listings_underpriced": listings_underpriced,
            "listings_overpriced": listings_overpriced,
            "listings_fair": listings_fair,
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


# ---------------------------------------------------------------------------
# Per-item wishlist sensors
# ---------------------------------------------------------------------------

def _build_wishlist_state(row) -> dict:
    """Build the state JSON dict for a wishlist MQTT sensor row."""
    target = float(row["target_price_eur"] or 0)
    cm_trend = row["cm_trend"] if "cm_trend" in row.keys() else None
    if cm_trend is not None:
        current_price: float | None = float(cm_trend)
    elif row["is_foil"]:
        raw = row["price_eur_foil"] if "price_eur_foil" in row.keys() else None
        current_price = float(raw) if raw else None
    else:
        raw = row["price_eur"] if "price_eur" in row.keys() else None
        current_price = float(raw) if raw else None

    is_deal = current_price is not None and target > 0 and current_price <= target
    delta_pct: float | None = None
    if current_price is not None and target > 0:
        delta_pct = round((current_price - target) / target * 100, 2)

    return {
        "card_name": row["card_name"] or "",
        "set_code": row["set_code"] or "",
        "is_foil": bool(row["is_foil"]),
        "target_price_eur": target,
        "current_price_eur": current_price,
        "is_deal": is_deal,
        "delta_pct": delta_pct,
        "priority": row["priority"] or 3,
        "is_ordered": bool(row["is_ordered"]) if "is_ordered" in row.keys() else False,
        "status": row["status"] or "wanted",
    }


def _build_wishlist_discovery(item_id: int, card_name: str, set_code: str, prefix: str) -> dict:
    """Build the MQTT discovery config payload for a wishlist item sensor."""
    display_set = f" ({set_code})" if set_code else ""
    return {
        "name": f"MTG Wishlist {card_name}{display_set}",
        "unique_id": f"mtg_wishlist_{item_id}",
        "state_topic": f"{prefix}/wishlist/{item_id}/state",
        "value_template": "{{ value_json.current_price_eur }}",
        "json_attributes_topic": f"{prefix}/wishlist/{item_id}/state",
        "unit_of_measurement": "EUR",
        "icon": "mdi:cards",
        "device_class": "monetary",
        "device": _WISHLIST_DEVICE_INFO,
    }


async def publish_wishlist_sensor_by_id(item_id: int) -> None:
    """Fetch one wishlist item from DB and publish its MQTT discovery + state."""
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
        cursor = await db.execute(
            """SELECT w.id, w.target_price_eur, w.is_foil, w.priority, w.status, w.is_ordered,
                   c.name AS card_name, c.set_code, c.price_eur, c.price_eur_foil,
                   (SELECT ph.trend FROM cardmarket_products cp
                    JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                    WHERE LOWER(cp.card_name) = LOWER(c.name)
                    ORDER BY ph.date DESC LIMIT 1) AS cm_trend
               FROM wishlist w
               LEFT JOIN cards c ON c.id = w.card_id
               WHERE w.id = ? AND w.removed_at IS NULL AND w.status = 'wanted'""",
            (item_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return

        prefix = settings.mqtt_topic_prefix
        card_name = row["card_name"] or ""
        set_code = row["set_code"] or ""
        state = _build_wishlist_state(row)
        discovery = _build_wishlist_discovery(item_id, card_name, set_code, prefix)

        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username or None,
            password=settings.mqtt_password or None,
        ) as client:
            await client.publish(
                f"homeassistant/sensor/mtg_wishlist_{item_id}/config",
                payload=json.dumps(discovery),
                retain=True,
            )
            await client.publish(
                f"{prefix}/wishlist/{item_id}/state",
                payload=json.dumps(state),
                retain=True,
            )
        logger.debug("Published wishlist MQTT sensor for item %d (%s)", item_id, card_name)
    except Exception:
        logger.exception("Failed to publish wishlist MQTT sensor for item %d", item_id)


async def publish_wishlist_sensors() -> None:
    """Publish all active wanted wishlist items as individual MQTT sensors.

    Only items with status='wanted' are published (including ordered ones, which
    are wanted items with is_ordered=1).  Items with status 'acquired', 'dropped',
    or 'not_received' are intentionally excluded — those are removed via
    delete_wishlist_sensor() when the status transition occurs.

    A 50 ms delay is inserted between individual item publishes to avoid
    overwhelming HA's MQTT processor on large wishlists.
    """
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
        cursor = await db.execute(
            """SELECT w.id, w.target_price_eur, w.is_foil, w.priority, w.status, w.is_ordered,
                   c.name AS card_name, c.set_code, c.price_eur, c.price_eur_foil,
                   (SELECT ph.trend FROM cardmarket_products cp
                    JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                    WHERE LOWER(cp.card_name) = LOWER(c.name)
                    ORDER BY ph.date DESC LIMIT 1) AS cm_trend
               FROM wishlist w
               LEFT JOIN cards c ON c.id = w.card_id
               WHERE w.removed_at IS NULL AND w.status = 'wanted'
               ORDER BY w.priority DESC, w.id"""
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.info("No active wishlist items to publish")
            return

        prefix = settings.mqtt_topic_prefix
        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username or None,
            password=settings.mqtt_password or None,
        ) as client:
            for i, row in enumerate(rows):
                item_id = row["id"]
                card_name = row["card_name"] or ""
                set_code = row["set_code"] or ""
                state = _build_wishlist_state(row)
                discovery = _build_wishlist_discovery(item_id, card_name, set_code, prefix)

                await client.publish(
                    f"homeassistant/sensor/mtg_wishlist_{item_id}/config",
                    payload=json.dumps(discovery),
                    retain=True,
                )
                await client.publish(
                    f"{prefix}/wishlist/{item_id}/state",
                    payload=json.dumps(state),
                    retain=True,
                )
                # 50 ms pause every item to avoid overwhelming HA's MQTT processor
                if i % 1 == 0:
                    await asyncio.sleep(0.05)

        logger.info("Published %d wishlist MQTT sensors", len(rows))
    except Exception:
        logger.exception("Failed to publish wishlist MQTT sensors")


async def delete_wishlist_sensor(item_id: int) -> None:
    """Remove a wishlist sensor from HA by publishing an empty retained payload on the discovery topic.

    MQTT Discovery spec: to un-discover an entity the retained config message must be
    overwritten with an empty payload **with retain=True**.  Using retain=False would
    leave the old retained message in the broker and the entity would reappear after
    HA or the broker restarts (ghost sensor).
    """
    settings = get_settings()
    if not settings.mqtt_enabled:
        return

    try:
        import aiomqtt
    except ImportError:
        return

    try:
        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username or None,
            password=settings.mqtt_password or None,
        ) as client:
            await client.publish(
                f"homeassistant/sensor/mtg_wishlist_{item_id}/config",
                payload="",
                retain=True,  # Must be True to overwrite and clear the retained config
            )
        logger.debug("Deleted wishlist MQTT sensor for item %d", item_id)
    except Exception:
        logger.exception("Failed to delete wishlist MQTT sensor for item %d", item_id)


# ---------------------------------------------------------------------------
# MQTT-based HA service registry
# ---------------------------------------------------------------------------

async def _handle_service_cmd(cmd: str, payload: dict) -> dict:
    """Dispatch an incoming service command and return a response dict."""
    if cmd == "trigger_sync":
        asyncio.create_task(_run_trigger_sync())
        return {"status": "started", "cmd": "trigger_sync"}

    if cmd == "sync_prices":
        asyncio.create_task(_run_sync_prices())
        return {"status": "started", "cmd": "sync_prices"}

    if cmd == "add_to_wishlist":
        return await _service_add_to_wishlist(payload)

    if cmd == "mark_acquired":
        return await _service_mark_acquired(payload)

    raise ValueError(f"Unknown service command: {cmd!r}")


async def _run_trigger_sync() -> None:
    """Background task: run full Archidekt sync."""
    try:
        from .sync_service import run_full_sync
        result = await run_full_sync()
        logger.info("MQTT-triggered sync completed: %s", result)
    except Exception:
        logger.exception("MQTT-triggered sync failed")


async def _run_sync_prices() -> None:
    """Background task: sync Cardmarket prices + republish sensors."""
    try:
        from .cardmarket_prices import sync_cardmarket_prices
        result = await sync_cardmarket_prices()
        logger.info("MQTT-triggered price sync completed: %s", result)
        await publish_wishlist_sensors()
        await publish_stats()
    except Exception:
        logger.exception("MQTT-triggered price sync failed")


async def _service_add_to_wishlist(payload: dict) -> dict:
    """Add a card to the wishlist via MQTT service call."""
    card_name = payload.get("card_name", "").strip()
    if not card_name:
        raise ValueError("card_name is required")
    priority = int(payload.get("priority", 3))

    from ..database import get_db
    db = await get_db()

    cursor = await db.execute(
        "SELECT id FROM cards WHERE LOWER(name) = LOWER(?) LIMIT 1", (card_name,)
    )
    card_row = await cursor.fetchone()
    if not card_row:
        raise ValueError(f"Card not found in local database: {card_name!r}")

    card_id = card_row[0]

    # Check for existing active wanted entry first to return a meaningful response
    existing_cursor = await db.execute(
        "SELECT id FROM wishlist WHERE card_id = ? AND status = 'wanted' AND removed_at IS NULL LIMIT 1",
        (card_id,),
    )
    existing = await existing_cursor.fetchone()
    if existing:
        return {"status": "already_exists", "item_id": existing[0], "card_name": card_name}

    cursor = await db.execute(
        """INSERT INTO wishlist (card_id, priority, status)
           VALUES (?, ?, 'wanted')""",
        (card_id, priority),
    )
    await db.commit()
    new_id = cursor.lastrowid
    if new_id:
        asyncio.create_task(publish_wishlist_sensor_by_id(new_id))
    return {"status": "ok", "item_id": new_id, "card_name": card_name}


async def _service_mark_acquired(payload: dict) -> dict:
    """Mark a wishlist item as acquired via MQTT service call."""
    item_id = payload.get("item_id")
    if item_id is None:
        raise ValueError("item_id is required")
    item_id = int(item_id)
    source = payload.get("source")
    paid_price_eur = payload.get("paid_price_eur")

    from ..database import get_db
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, status FROM wishlist WHERE id = ? AND removed_at IS NULL", (item_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Wishlist item {item_id} not found")
    if row["status"] == "acquired":
        return {"status": "already_acquired", "item_id": item_id}

    await db.execute(
        """UPDATE wishlist
           SET status = 'acquired', acquired_at = CURRENT_TIMESTAMP,
               is_ordered = 0,
               paid_price_eur = COALESCE(?, paid_price_eur),
               source = COALESCE(?, source)
           WHERE id = ?""",
        (paid_price_eur, source, item_id),
    )
    await db.commit()
    asyncio.create_task(delete_wishlist_sensor(item_id))
    return {"status": "acquired", "item_id": item_id}


async def service_subscriber_loop() -> None:
    """Long-running MQTT subscriber for HA service calls.

    Subscribes to ``{prefix}/service/+`` and dispatches commands to internal
    handlers. Publishes results back to ``{prefix}/service/{cmd}/response``.
    Reconnects automatically after failures.
    """
    settings = get_settings()
    if not settings.mqtt_enabled:
        return

    try:
        import aiomqtt
    except ImportError:
        logger.warning("aiomqtt not installed, service subscriber disabled")
        return

    prefix = settings.mqtt_topic_prefix
    service_topic = f"{prefix}/service/+"

    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_username or None,
                password=settings.mqtt_password or None,
            ) as client:
                await client.subscribe(service_topic)
                logger.info("MQTT service subscriber listening on %s", service_topic)
                async for msg in client.messages:
                    topic_parts = msg.topic.value.split("/")
                    cmd = topic_parts[-1]
                    # Skip response topics to avoid loops
                    if "response" in topic_parts:
                        continue
                    try:
                        raw = msg.payload.decode() if msg.payload else "{}"
                        payload = json.loads(raw or "{}")
                        result = await _handle_service_cmd(cmd, payload)
                    except Exception as exc:
                        result = {"error": str(exc), "cmd": cmd}
                    response_topic = f"{prefix}/service/{cmd}/response"
                    try:
                        await client.publish(response_topic, payload=json.dumps(result))
                    except Exception:
                        logger.exception("Failed to publish service response for %s", cmd)
        except Exception:
            logger.exception("MQTT service subscriber disconnected, retrying in 30s")
            await asyncio.sleep(30)
