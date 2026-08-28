"""Home Assistant MQTT Sensor Discovery publisher."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from . import ha_mqtt
from .ha_entities import (
    WISHLIST_DEVICE_INFO,
    Entity,
    discovery_payload,
    discovery_topic,
)

logger = logging.getLogger(__name__)


def utc_iso(sqlite_ts: str | None) -> str | None:
    """Normalise a SQLite ``CURRENT_TIMESTAMP`` string to timezone-aware ISO 8601.

    SQLite stores ``YYYY-MM-DD HH:MM:SS`` in UTC but without an offset. HA
    rejects such a naive value on a ``device_class: timestamp`` sensor, which
    kept ``sensor.mtg_last_sync_at`` permanently ``unknown``. Values that
    already carry an offset pass through unchanged; unparseable input returns
    ``None`` so the sensor stays ``unknown`` instead of erroring in HA.
    """
    if not sqlite_ts:
        return None
    try:
        parsed = datetime.fromisoformat(str(sqlite_ts).replace(" ", "T"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


# `state_class` drives HA's long-term statistics.  Counts use `measurement`;
# `device_class: monetary` only accepts `total` (HA rejects `measurement` there
# with an "impossible state class" warning).
AGGREGATE_SENSORS = [
    Entity(key="total_cards", name="Total Cards", icon="mdi:cards", state_class="measurement"),
    Entity(
        key="unique_cards", name="Unique Cards",
        icon="mdi:cards-outline", state_class="measurement",
    ),
    Entity(
        key="total_value_eur", name="Total Value EUR",
        device_class="monetary", unit="EUR", state_class="total",
    ),
    Entity(
        key="total_value_usd", name="Total Value USD",
        device_class="monetary", unit="USD", state_class="total",
    ),
    Entity(
        key="total_decks", name="Total Decks",
        icon="mdi:cards-playing-outline", state_class="measurement",
    ),
    Entity(key="last_sync_status", name="Last Sync Status", icon="mdi:sync"),
    Entity(key="last_sync_at", name="Last Sync At", device_class="timestamp"),
    Entity(
        key="active_price_alerts", name="Active Price Alerts",
        icon="mdi:alert-decagram", state_class="measurement",
    ),
    # Spending / acquisition sensors (last 30 days)
    Entity(
        key="spending_30d", name="MTG Spending 30d",
        device_class="monetary", unit="EUR", state_class="total",
        icon="mdi:cash-multiple",
    ),
    Entity(
        key="spending_30d_value", name="MTG Acquired Value 30d",
        device_class="monetary", unit="EUR", state_class="total",
        icon="mdi:trending-up",
    ),
    Entity(
        key="acquired_count_30d", name="MTG Acquired Count 30d",
        icon="mdi:cards-playing-heart-multiple", state_class="measurement",
    ),
    # Listing health sensors
    Entity(
        key="listings_underpriced", name="MTG Listings Underpriced",
        icon="mdi:tag-arrow-down", state_class="measurement",
    ),
    Entity(
        key="listings_overpriced", name="MTG Listings Overpriced",
        icon="mdi:tag-arrow-up", state_class="measurement",
    ),
    Entity(
        key="listings_fair", name="MTG Listings Fair",
        icon="mdi:tag-check", state_class="measurement",
    ),
]

# Inbox / acquisition triage
INBOX_SENSORS = [
    Entity(
        key="inbox_pending", name="MTG Inbox Pending",
        icon="mdi:tray-full", state_class="measurement", has_attributes=True,
    ),
    Entity(
        key="inbox_needs_sell", name="MTG Inbox Needs Sell",
        icon="mdi:tag-arrow-right", state_class="measurement",
    ),
    Entity(
        key="inbox_needs_keep", name="MTG Inbox Needs Keep",
        icon="mdi:archive-check", state_class="measurement",
    ),
    Entity(
        key="inbox_pending_value_eur", name="MTG Inbox Pending Value",
        device_class="monetary", unit="EUR", state_class="total",
        icon="mdi:cash-clock",
    ),
    Entity(
        key="inbox_oldest_age_days", name="MTG Inbox Oldest Age",
        unit="d", state_class="measurement", icon="mdi:clock-alert-outline",
    ),
    Entity(
        key="inbox_decided_30d", name="MTG Inbox Decided 30d",
        icon="mdi:check-decagram", state_class="measurement", has_attributes=True,
    ),
    Entity(
        key="inbox_has_pending", name="MTG Inbox Has Pending",
        component="binary_sensor", icon="mdi:tray-alert",
        extra={"payload_on": "ON", "payload_off": "OFF"},
    ),
]

# Selling: advisor candidates, duplicate surplus, unlisted backlog
SELL_SENSORS = [
    Entity(
        key="sell_candidates", name="MTG Sell Candidates",
        icon="mdi:tag-multiple", state_class="measurement", has_attributes=True,
    ),
    Entity(
        key="sell_potential_eur", name="MTG Sell Potential",
        device_class="monetary", unit="EUR", state_class="total",
        icon="mdi:cash-plus",
    ),
    Entity(
        key="duplicates_surplus_cards", name="MTG Duplicates Surplus",
        icon="mdi:content-duplicate", state_class="measurement",
    ),
    Entity(
        key="duplicates_surplus_value_eur", name="MTG Duplicates Surplus Value",
        device_class="monetary", unit="EUR", state_class="total",
        icon="mdi:cash-multiple",
    ),
    Entity(
        key="unlisted_value_eur", name="MTG Unlisted Value",
        device_class="monetary", unit="EUR", state_class="total",
        icon="mdi:tag-off", has_attributes=True,
    ),
]

# Add-on itself
ADDON_SENSORS = [
    Entity(
        key="ingress_url", name="MTG Ingress URL",
        icon="mdi:link-variant", has_attributes=True,
    ),
]

# Deck performance (overall; per-deck sensors are published dynamically)
DECK_SENSORS = [
    Entity(
        key="games_30d", name="MTG Games 30d",
        icon="mdi:cards-playing", state_class="measurement",
    ),
    Entity(
        key="winrate_30d", name="MTG Win Rate 30d",
        icon="mdi:trophy", unit="%", state_class="measurement", has_attributes=True,
    ),
    Entity(key="last_game_at", name="MTG Last Game At", device_class="timestamp"),
    Entity(
        key="last_game_result", name="MTG Last Game Result",
        icon="mdi:flag-checkered", has_attributes=True,
    ),
]

# MTGStocks all-time-high/low signals — only published while the optional
# MTGStocks integration is enabled.
SIGNAL_SENSORS = [
    Entity(
        key="signals_buy", name="MTG Buy Signals",
        icon="mdi:trending-down", state_class="measurement", has_attributes=True,
    ),
    Entity(
        key="signals_sell", name="MTG Sell Signals",
        icon="mdi:trending-up", state_class="measurement", has_attributes=True,
    ),
]


def _mtgstocks_enabled() -> bool:
    from ..config import get_settings

    return bool(get_settings().mtgstocks_enabled)


def active_entities() -> list[Entity]:
    """Every static entity that should currently exist in HA.

    Per-deck sensors are not listed here — they depend on the database and are
    published by :func:`publish_deck_sensors`.
    """
    entities = (
        AGGREGATE_SENSORS + ADDON_SENSORS + INBOX_SENSORS + SELL_SENSORS + DECK_SENSORS
    )
    if _mtgstocks_enabled():
        entities += SIGNAL_SENSORS
    return entities


def _deck_entity(deck_id: int, deck_name: str, prefix: str) -> Entity:
    """Win-rate sensor for one deck.

    Keyed by deck id, not name: renaming a deck in Archidekt must not orphan
    the entity and its history.
    """
    state_topic = f"{prefix}/deck/{deck_id}/state"
    return Entity(
        key=f"deck_{deck_id}_winrate",
        name=f"MTG Deck {deck_name} Win Rate",
        unique_id=f"mtg_deck_{deck_id}_winrate",
        state_topic=state_topic,
        value_template="{{ value_json.win_rate }}",
        json_attributes_topic=state_topic,
        unit="%",
        icon="mdi:trophy-outline",
        state_class="measurement",
    )


async def publish_discovery():
    """Publish HA MQTT Discovery config for all aggregate sensors.

    Entities of disabled integrations get their retained config cleared, so
    turning MTGStocks off removes the signal sensors from HA instead of
    leaving them behind with a stale value.
    """
    if not ha_mqtt.is_available():
        return

    prefix = ha_mqtt.topic_prefix()
    availability = ha_mqtt.status_topic()
    entities = active_entities()
    retired = [e for e in SIGNAL_SENSORS if e not in entities]

    try:
        async with ha_mqtt.session() as client:
            for entity in entities:
                await client.publish(
                    discovery_topic(entity),
                    payload=json.dumps(discovery_payload(entity, prefix, availability)),
                    retain=True,
                )
            for entity in retired:
                await client.publish(discovery_topic(entity), payload="", retain=True)
        logger.info("MQTT discovery configs published for %d entities", len(entities))
    except Exception:
        logger.exception("Failed to publish MQTT discovery configs")


async def _publish_metrics(client, prefix: str, metrics) -> None:
    """Publish a Metrics bundle: states, plus attributes where present.

    A `None` state means "no value yet" and is skipped, so the entity stays
    unknown in HA instead of receiving an unparseable empty payload.
    """
    for key, value in metrics.states.items():
        if value is None:
            continue
        await client.publish(f"{prefix}/{key}", payload=str(value), retain=True)
    for key, attributes in metrics.attributes.items():
        await client.publish(
            f"{prefix}/{key}/attributes", payload=json.dumps(attributes), retain=True
        )


async def publish_stats():
    """Fetch stats from DB and publish to MQTT state topics."""
    if not ha_mqtt.is_available():
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

        prefix = ha_mqtt.topic_prefix()
        values = {
            "total_cards": int(row[0]),
            "unique_cards": int(row[1]),
            "total_value_eur": round(float(row[2]), 2),
            "total_value_usd": round(float(row[3]), 2),
            "total_decks": deck_count,
            "last_sync_status": sync_row["status"] if sync_row else "never",
            "last_sync_at": utc_iso(sync_row["finished_at"]) if sync_row else None,
            "active_price_alerts": alert_count,
            "spending_30d": spending_30d,
            "spending_30d_value": spending_30d_value,
            "acquired_count_30d": acquired_count_30d,
            "listings_underpriced": listings_underpriced,
            "listings_overpriced": listings_overpriced,
            "listings_fair": listings_fair,
        }

        # Inbox / sell metrics.  Each block degrades independently so one bad
        # query cannot take the whole stats publish down.
        bundles = []
        for name, factory in _metric_bundles(db):
            try:
                bundles.append(await factory())
            except Exception:
                logger.exception("Could not compute %s metrics for MQTT", name)

        async with ha_mqtt.session() as client:
            for key, value in values.items():
                await client.publish(
                    f"{prefix}/{key}",
                    payload=str(value),
                    retain=True,
                )
            for bundle in bundles:
                await _publish_metrics(client, prefix, bundle)

        published = len(values) + sum(len(b.states) for b in bundles)
        logger.info("MQTT stats published: %d sensors updated", published)
    except Exception:
        logger.exception("Failed to publish MQTT stats")


def _metric_bundles(db):
    """The metric factories that make up a full stats refresh."""
    from . import ha_metrics

    async def _addon():
        return ha_metrics.addon_metrics()

    bundles = [
        ("addon", _addon),
        ("inbox", lambda: ha_metrics.inbox_metrics(db)),
        ("sell", lambda: ha_metrics.sell_metrics(db)),
    ]
    if _mtgstocks_enabled():
        bundles.append(("signals", ha_metrics.signal_metrics))
    return bundles


async def publish_inbox_sensors() -> None:
    """Refresh only the inbox sensors (after a triage decision)."""
    if not ha_mqtt.is_available():
        return

    from ..database import get_db
    from . import ha_metrics

    try:
        db = await get_db()
        metrics = await ha_metrics.inbox_metrics(db)
        async with ha_mqtt.session() as client:
            await _publish_metrics(client, ha_mqtt.topic_prefix(), metrics)
        logger.debug("MQTT inbox sensors published")
    except Exception:
        logger.exception("Failed to publish inbox MQTT sensors")


async def publish_deck_sensors() -> None:
    """Publish the overall play sensors and one win-rate sensor per active deck.

    Every deck is visited: active ones get their discovery + state, inactive
    ones get their retained discovery config cleared, so a deck that stops
    being played disappears from HA again.  Walking all decks keeps this
    stateless — no bookkeeping to lose across restarts.
    """
    if not ha_mqtt.is_available():
        return

    from ..database import get_db
    from . import ha_metrics

    try:
        db = await get_db()
        prefix = ha_mqtt.topic_prefix()
        availability = ha_mqtt.status_topic()

        overall = await ha_metrics.deck_performance_metrics(db)
        decks = await ha_metrics.deck_stats(db)

        async with ha_mqtt.session() as client:
            await _publish_metrics(client, prefix, overall)

            for deck in decks:
                entity = _deck_entity(deck["deck_id"], deck["deck_name"], prefix)
                if not deck["is_active"]:
                    await client.publish(discovery_topic(entity), payload="", retain=True)
                    continue

                await client.publish(
                    discovery_topic(entity),
                    payload=json.dumps(discovery_payload(entity, prefix, availability)),
                    retain=True,
                )
                await client.publish(
                    entity.resolved_state_topic(prefix),
                    payload=json.dumps({
                        "win_rate": deck["win_rate"],
                        "games": deck["games"],
                        "wins": deck["wins"],
                        "losses": deck["losses"],
                        "draws": deck["draws"],
                        "last_played": deck["last_played"],
                        "deck_name": deck["deck_name"],
                        # The bracket rides along on the deck's existing sensor
                        # rather than getting one of its own. ⚠️ That means it
                        # only reaches HA for decks played in the last 90 days
                        # — the sensor does not exist for the others.
                        "bracket": deck["bracket"],
                        "bracket_source": deck["bracket_source"],
                    }),
                    retain=True,
                )
                await asyncio.sleep(0.05)  # pace HA's MQTT processor

        active = sum(1 for d in decks if d["is_active"])
        logger.info("MQTT deck sensors published: %d active of %d decks", active, len(decks))
    except Exception:
        logger.exception("Failed to publish deck MQTT sensors")


# ---------------------------------------------------------------------------
# Game-logger form
# ---------------------------------------------------------------------------


async def publish_form_entities() -> None:
    """Publish the game-logger discovery configs and the current field values.

    Re-run after a sync so the deck dropdown follows the database.  A stored
    deck that has disappeared from the options is reset, because HA refuses a
    select state that is not one of its options.
    """
    if not ha_mqtt.is_available():
        return

    from ..database import get_db
    from . import ha_form

    try:
        db = await get_db()
        prefix = ha_mqtt.topic_prefix()
        availability = ha_mqtt.status_topic()

        options, _mapping = await ha_form.deck_options(db)
        values = await ha_form.load_state(db)

        if values["deck"] not in options:
            values["deck"] = ha_form.NO_DECK
            await ha_form.set_field(db, "deck", ha_form.NO_DECK)

        async with ha_mqtt.session() as client:
            for entity in ha_form.form_entities(prefix, options):
                await client.publish(
                    discovery_topic(entity),
                    payload=json.dumps(discovery_payload(entity, prefix, availability)),
                    retain=True,
                )
            for key, value in values.items():
                await client.publish(
                    ha_form.state_topic(prefix, key), payload=value, retain=True
                )

        logger.info("MQTT game-logger form published (%d deck options)", len(options) - 1)
    except Exception:
        logger.exception("Failed to publish game-logger form")


async def _publish_form_status(text: str) -> None:
    from . import ha_form

    await ha_mqtt.publish(
        ha_form.state_topic(ha_mqtt.topic_prefix(), ha_form.STATUS_KEY),
        payload=text,
        retain=True,
    )


async def _on_form_message(topic: str, payload: bytes) -> None:
    """Handle one `{prefix}/form/{field}/set` command from HA."""
    from ..database import get_db
    from . import ha_form

    key = topic.split("/")[-2]
    raw = payload.decode(errors="replace") if payload else ""
    db = await get_db()
    prefix = ha_mqtt.topic_prefix()

    if key == ha_form.SUBMIT_KEY:
        result = await ha_form.submit(db)
        await _publish_form_status(ha_form.status_text(result))
        if "error" not in result:
            # Reset the visible form and refresh the play statistics
            values = await ha_form.load_state(db)
            async with ha_mqtt.session() as client:
                for field, value in values.items():
                    await client.publish(
                        ha_form.state_topic(prefix, field), payload=value, retain=True
                    )
            asyncio.create_task(publish_deck_sensors())
        return

    try:
        value = await ha_form.set_field(db, key, raw)
    except ValueError as exc:
        # Leave HA showing the previous value and say why on the status sensor
        logger.warning("Rejected form command for %s: %s", key, exc)
        await _publish_form_status(f"Ignored {key}: {exc}"[:255])
        return

    await ha_mqtt.publish(ha_form.state_topic(prefix, key), payload=value, retain=True)


_inbox_publish_task: asyncio.Task | None = None
INBOX_PUBLISH_DEBOUNCE_S = 5.0


def schedule_inbox_publish() -> None:
    """Publish the inbox sensors shortly, coalescing rapid triage decisions.

    Recomputing the suggestion split costs a few queries per pending event, so
    working through the inbox card by card must not trigger one full refresh
    per click.  A pending publish already covers any decision made before it
    fires.
    """
    global _inbox_publish_task
    if not ha_mqtt.is_available():
        return
    if _inbox_publish_task is not None and not _inbox_publish_task.done():
        return

    async def _delayed() -> None:
        await asyncio.sleep(INBOX_PUBLISH_DEBOUNCE_S)
        await publish_inbox_sensors()

    _inbox_publish_task = asyncio.create_task(_delayed())


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


def _wishlist_entity(item_id: int, card_name: str, set_code: str, prefix: str) -> Entity:
    """Describe the HA entity for one wishlist item.

    No `state_class`: a per-item price is not a meaningful long-term statistic,
    and `monetary` would force `total` (running-sum) semantics onto it.
    """
    display_set = f" ({set_code})" if set_code else ""
    state_topic = f"{prefix}/wishlist/{item_id}/state"
    return Entity(
        key=f"wishlist_{item_id}",
        name=f"MTG Wishlist {card_name}{display_set}",
        unique_id=f"mtg_wishlist_{item_id}",
        state_topic=state_topic,
        value_template="{{ value_json.current_price_eur }}",
        json_attributes_topic=state_topic,
        unit="EUR",
        icon="mdi:cards",
        device_class="monetary",
        device=WISHLIST_DEVICE_INFO,
    )


async def publish_wishlist_sensor_by_id(item_id: int) -> None:
    """Fetch one wishlist item from DB and publish its MQTT discovery + state."""
    if not ha_mqtt.is_available():
        return

    from ..database import get_db

    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT w.id, w.target_price_eur, w.is_foil, w.priority, w.status, w.is_ordered,
                   c.name AS card_name, c.set_code, c.price_eur, c.price_eur_foil,
                   (SELECT ph.trend FROM cardmarket_products cp
                    JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                    WHERE cp.card_id = c.id
                    ORDER BY ph.date DESC LIMIT 1) AS cm_trend
               FROM wishlist w
               LEFT JOIN cards c ON c.id = w.card_id
               WHERE w.id = ? AND w.removed_at IS NULL AND w.status = 'wanted'""",
            (item_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return

        prefix = ha_mqtt.topic_prefix()
        card_name = row["card_name"] or ""
        set_code = row["set_code"] or ""
        state = _build_wishlist_state(row)
        entity = _wishlist_entity(item_id, card_name, set_code, prefix)

        async with ha_mqtt.session() as client:
            await client.publish(
                discovery_topic(entity),
                payload=json.dumps(
                    discovery_payload(entity, prefix, ha_mqtt.status_topic())
                ),
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
    if not ha_mqtt.is_available():
        return

    from ..database import get_db

    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT w.id, w.target_price_eur, w.is_foil, w.priority, w.status, w.is_ordered,
                   c.name AS card_name, c.set_code, c.price_eur, c.price_eur_foil,
                   (SELECT ph.trend FROM cardmarket_products cp
                    JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                    WHERE cp.card_id = c.id
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

        prefix = ha_mqtt.topic_prefix()
        availability = ha_mqtt.status_topic()
        async with ha_mqtt.session() as client:
            for i, row in enumerate(rows):
                item_id = row["id"]
                card_name = row["card_name"] or ""
                set_code = row["set_code"] or ""
                state = _build_wishlist_state(row)
                entity = _wishlist_entity(item_id, card_name, set_code, prefix)

                await client.publish(
                    discovery_topic(entity),
                    payload=json.dumps(discovery_payload(entity, prefix, availability)),
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
    if not ha_mqtt.is_available():
        return

    await ha_mqtt.publish(
        f"homeassistant/sensor/mtg_wishlist_{item_id}/config",
        payload="",
        retain=True,  # Must be True to overwrite and clear the retained config
    )
    logger.debug("Deleted wishlist MQTT sensor for item %d", item_id)


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

    if cmd == "log_game":
        return await _service_log_game(payload)

    if cmd == "triage":
        return await _service_triage(payload)

    if cmd == "create_listing":
        return await _service_create_listing(payload)

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


async def _service_log_game(payload: dict) -> dict:
    """Log a played game.  The deck may be given by id or by name."""
    from ..database import get_db
    from .game_log import DeckLookupError, log_game

    db = await get_db()
    try:
        result = await log_game(db, payload)
    except DeckLookupError as exc:
        return {"error": str(exc), "candidates": exc.candidates, "cmd": "log_game"}

    asyncio.create_task(publish_deck_sensors())
    return result


async def _service_triage(payload: dict) -> dict:
    """Decide one inbox item — the write half of an actionable notification.

    Delegates to the API handler rather than repeating the booking logic
    (listing creation, decision snapshot).  Imported lazily because the
    acquisitions router imports this module for the sensor refresh.
    """
    from fastapi import HTTPException

    from ..models.schemas import TriageDecisionRequest
    from ..routers.acquisitions import decide_triage

    event_id = payload.get("event_id")
    if event_id is None:
        raise ValueError("event_id is required")

    fields = {k: v for k, v in payload.items() if k != "event_id"}
    # A decision made from HA is a manual one unless stated otherwise.
    if fields.get("action") in ("keep", "sold_new", "swap"):
        fields.setdefault("source", "other")

    try:
        return await decide_triage(int(event_id), TriageDecisionRequest(**fields))
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code, "cmd": "triage"}


async def _service_create_listing(payload: dict) -> dict:
    """Create a Cardmarket listing (e.g. straight from a duplicates alert)."""
    from ..routers.cardmarket import AddListingRequest, add_cardmarket_listing

    return await add_cardmarket_listing(AddListingRequest(**payload))


async def _on_service_message(topic: str, payload: bytes) -> None:
    """Dispatch one ``{prefix}/service/{cmd}`` message and answer on ``/response``."""
    topic_parts = topic.split("/")
    cmd = topic_parts[-1]
    # Skip response topics to avoid loops
    if "response" in topic_parts:
        return

    try:
        raw = payload.decode() if payload else "{}"
        result = await _handle_service_cmd(cmd, json.loads(raw or "{}"))
    except Exception as exc:
        result = {"error": str(exc), "cmd": cmd}

    await ha_mqtt.publish(
        f"{ha_mqtt.topic_prefix()}/service/{cmd}/response", payload=json.dumps(result)
    )


def start_ha_mqtt() -> None:
    """Register the HA subscriptions and start the MQTT manager.

    Subscribes to ``{prefix}/service/+`` (results go back to
    ``{prefix}/service/{cmd}/response``) and to the game-logger command topics.
    The manager handles reconnects.
    """
    if not ha_mqtt.is_available():
        return

    from . import ha_form

    prefix = ha_mqtt.topic_prefix()
    ha_mqtt.register_handler(f"{prefix}/service/+", _on_service_message)
    ha_mqtt.register_handler(ha_form.command_topic_filter(prefix), _on_form_message)
    ha_mqtt.start()
