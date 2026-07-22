"""Sprint 28: MQTT discovery payloads + connection layer.

The `unique_id` assertions are a regression guard: changing one orphans the
existing entity (and its history) in HA's entity registry.
"""
import asyncio
import json

import pytest
from app.services import ha_mqtt, ha_publisher
from app.services.ha_entities import (
    WISHLIST_DEVICE_INFO,
    Entity,
    discovery_payload,
    discovery_topic,
)

# Frozen list of the aggregate sensors as HA knows them today.
EXPECTED_UNIQUE_IDS = [
    "mtg_collection_total_cards",
    "mtg_collection_unique_cards",
    "mtg_collection_total_value_eur",
    "mtg_collection_total_value_usd",
    "mtg_collection_total_decks",
    "mtg_collection_last_sync_status",
    "mtg_collection_last_sync_at",
    "mtg_collection_active_price_alerts",
    "mtg_collection_spending_30d",
    "mtg_collection_spending_30d_value",
    "mtg_collection_acquired_count_30d",
    "mtg_collection_listings_underpriced",
    "mtg_collection_listings_overpriced",
    "mtg_collection_listings_fair",
]


def test_aggregate_unique_ids_are_stable():
    assert [e.resolved_unique_id for e in ha_publisher.AGGREGATE_SENSORS] == EXPECTED_UNIQUE_IDS


def test_aggregate_discovery_topics_unchanged():
    topics = [discovery_topic(e) for e in ha_publisher.AGGREGATE_SENSORS]
    assert topics[0] == "homeassistant/sensor/mtg_collection_total_cards/config"
    assert all(t.startswith("homeassistant/sensor/") for t in topics)


def test_aggregate_state_topics_use_prefix():
    payload = discovery_payload(
        ha_publisher.AGGREGATE_SENSORS[0], "mtg-collection", "mtg-collection/status"
    )
    assert payload["state_topic"] == "mtg-collection/total_cards"


def test_every_entity_has_availability():
    for entity in ha_publisher.AGGREGATE_SENSORS:
        payload = discovery_payload(entity, "mtg-collection", "mtg-collection/status")
        assert payload["availability_topic"] == "mtg-collection/status"
        assert payload["payload_available"] == "online"
        assert payload["payload_not_available"] == "offline"


def test_counts_have_state_class_for_statistics():
    by_key = {e.key: e for e in ha_publisher.AGGREGATE_SENSORS}
    assert by_key["total_cards"].state_class == "measurement"
    assert by_key["listings_fair"].state_class == "measurement"
    # Text/timestamp sensors must not claim a state class
    assert by_key["last_sync_status"].state_class == ""
    assert by_key["last_sync_at"].state_class == ""


def test_monetary_sensors_use_total_state_class():
    """HA rejects `measurement` for device_class monetary."""
    for entity in ha_publisher.AGGREGATE_SENSORS:
        if entity.device_class == "monetary":
            assert entity.state_class == "total", entity.key


def test_optional_fields_are_omitted_when_empty():
    payload = discovery_payload(
        Entity(key="plain", name="Plain"), "mtg-collection", "mtg-collection/status"
    )
    assert "icon" not in payload
    assert "unit_of_measurement" not in payload
    assert "state_class" not in payload
    assert "device_class" not in payload


def test_extra_keys_are_merged():
    entity = Entity(
        key="log_result",
        name="Result",
        component="select",
        extra={"options": ["win", "loss"], "command_topic": "x/set"},
    )
    payload = discovery_payload(entity, "mtg-collection", "mtg-collection/status")
    assert payload["options"] == ["win", "loss"]
    assert payload["command_topic"] == "x/set"
    assert discovery_topic(entity) == "homeassistant/select/mtg_collection_log_result/config"


def test_entity_ids_are_predictable():
    """object_id pins the generated entity_id to sensor.mtg_<key>."""
    by_key = {e.key: e for e in ha_publisher.active_entities()}
    assert by_key["total_cards"].object_id == "mtg_total_cards"
    assert by_key["inbox_pending"].object_id == "mtg_inbox_pending"
    assert by_key["unlisted_value_eur"].object_id == "mtg_unlisted_value_eur"
    # …while the registry identity stays on its historical value
    assert by_key["total_cards"].resolved_unique_id == "mtg_collection_total_cards"


def test_attributes_topic_derived_from_state_topic():
    entity = ha_publisher.INBOX_SENSORS[0]
    payload = discovery_payload(entity, "mtg-collection", "mtg-collection/status")
    assert payload["json_attributes_topic"] == "mtg-collection/inbox_pending/attributes"

    plain = ha_publisher.AGGREGATE_SENSORS[0]
    assert "json_attributes_topic" not in discovery_payload(
        plain, "mtg-collection", "mtg-collection/status"
    )


def test_wishlist_entity_shape_unchanged():
    entity = ha_publisher._wishlist_entity(42, "Sol Ring", "C21", "mtg-collection")
    payload = discovery_payload(entity, "mtg-collection", "mtg-collection/status")

    assert discovery_topic(entity) == "homeassistant/sensor/mtg_wishlist_42/config"
    assert payload["unique_id"] == "mtg_wishlist_42"
    assert payload["object_id"] == "mtg_wishlist_42"
    assert payload["name"] == "MTG Wishlist Sol Ring (C21)"
    assert payload["state_topic"] == "mtg-collection/wishlist/42/state"
    assert payload["json_attributes_topic"] == "mtg-collection/wishlist/42/state"
    assert payload["value_template"] == "{{ value_json.current_price_eur }}"
    assert payload["unit_of_measurement"] == "EUR"
    assert payload["device"] == WISHLIST_DEVICE_INFO
    # A per-item price is not a long-term statistic
    assert "state_class" not in payload


def test_wishlist_entity_without_set_code():
    entity = ha_publisher._wishlist_entity(7, "Sol Ring", "", "mtg-collection")
    assert entity.name == "MTG Wishlist Sol Ring"


def test_payload_is_json_serialisable():
    for entity in ha_publisher.AGGREGATE_SENSORS:
        json.dumps(discovery_payload(entity, "p", "p/status"))


# --- connection layer -------------------------------------------------------


def test_mqtt_disabled_by_default():
    assert ha_mqtt.is_available() is False


def test_status_topic_follows_prefix(monkeypatch):
    from app import config

    monkeypatch.setattr(
        config.get_settings(), "mqtt_topic_prefix", "custom-prefix", raising=False
    )
    assert ha_mqtt.status_topic() == "custom-prefix/status"


@pytest.mark.anyio
async def test_publishers_are_noops_when_disabled():
    """Every publisher must return quietly when MQTT is off."""
    await ha_publisher.publish_discovery()
    await ha_publisher.publish_stats()
    await ha_publisher.publish_wishlist_sensors()
    await ha_publisher.publish_wishlist_sensor_by_id(1)
    await ha_publisher.delete_wishlist_sensor(1)
    await ha_mqtt.publish("some/topic", "payload")
    await ha_mqtt.shutdown()
    ha_publisher.start_ha_mqtt()
    assert ha_mqtt._client is None


@pytest.mark.anyio
async def test_session_prefers_manager_client(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(ha_mqtt, "_client", sentinel)
    async with ha_mqtt.session() as client:
        assert client is sentinel


@pytest.mark.anyio
async def test_dispatch_routes_to_matching_handler(monkeypatch):
    from aiomqtt.topic import Topic

    seen = []

    async def handler(topic: str, payload: bytes) -> None:
        seen.append((topic, payload))

    monkeypatch.setattr(ha_mqtt, "_handlers", [("mtg-collection/service/+", handler)])

    class _Msg:
        topic = Topic("mtg-collection/service/trigger_sync")
        payload = b"{}"

    class _Other:
        topic = Topic("mtg-collection/wishlist/1/state")
        payload = b"{}"

    await ha_mqtt._dispatch(_Msg())
    await ha_mqtt._dispatch(_Other())

    assert seen == [("mtg-collection/service/trigger_sync", b"{}")]


@pytest.mark.anyio
async def test_dispatch_swallows_handler_errors(monkeypatch):
    from aiomqtt.topic import Topic

    async def boom(topic: str, payload: bytes) -> None:
        raise RuntimeError("handler exploded")

    monkeypatch.setattr(ha_mqtt, "_handlers", [("a/+", boom)])

    class _Msg:
        topic = Topic("a/b")
        payload = b""

    await ha_mqtt._dispatch(_Msg())  # must not raise


# --- end-to-end against a fake broker ---------------------------------------


class _FakeClient:
    """Stands in for aiomqtt.Client; records what would hit the broker."""

    instances: list["_FakeClient"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.published: list[tuple[str, object, bool]] = []
        self.subscribed: list[str] = []
        _FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def publish(self, topic, payload=None, retain=False, qos=0):
        self.published.append((topic, payload, retain))

    async def subscribe(self, topic_filter):
        self.subscribed.append(topic_filter)

    @property
    def messages(self):
        async def _idle():
            await asyncio.Event().wait()  # blocks until cancelled
            yield  # pragma: no cover

        return _idle()


class _FakeWill:
    def __init__(self, topic, payload=None, qos=0, retain=False):
        self.topic = topic
        self.payload = payload
        self.retain = retain


@pytest.fixture
def fake_mqtt(monkeypatch):
    """Enable MQTT and swap aiomqtt for the fake client."""
    from app import config

    _FakeClient.instances = []
    fake_module = type("_FakeAiomqtt", (), {"Client": _FakeClient, "Will": _FakeWill})
    monkeypatch.setattr(ha_mqtt, "_aiomqtt_module", fake_module)
    monkeypatch.setattr(ha_mqtt, "_aiomqtt_checked", True)
    monkeypatch.setattr(ha_mqtt, "_client", None)
    monkeypatch.setattr(ha_mqtt, "_handlers", [])
    monkeypatch.setattr(ha_mqtt, "_manager_task", None)
    monkeypatch.setattr(config.get_settings(), "mqtt_enabled", True)
    yield


@pytest.mark.anyio
async def test_discovery_publishes_every_sensor_retained(fake_mqtt):
    await ha_publisher.publish_discovery()

    assert len(_FakeClient.instances) == 1  # one fallback connection for the batch
    published = _FakeClient.instances[0].published
    # Active entities, plus a cleared config for each disabled MTGStocks sensor
    assert len(published) == len(ha_publisher.active_entities()) + len(
        ha_publisher.SIGNAL_SENSORS
    )
    assert all(retain for _, _, retain in published)

    topics = [t for t, _, _ in published]
    assert "homeassistant/sensor/mtg_collection_total_cards/config" in topics
    assert "homeassistant/sensor/mtg_collection_inbox_pending/config" in topics
    assert "homeassistant/binary_sensor/mtg_collection_inbox_has_pending/config" in topics

    payload = json.loads(published[0][1])
    assert payload["availability_topic"] == "mtg-collection/status"


@pytest.mark.anyio
async def test_stats_publish_uses_one_connection(fake_mqtt):
    await ha_publisher.publish_stats()

    assert len(_FakeClient.instances) == 1
    topics = [t for t, _, _ in _FakeClient.instances[0].published]
    assert "mtg-collection/total_cards" in topics
    assert "mtg-collection/listings_fair" in topics
    # Inbox and sell metrics ride along with the stats refresh
    assert "mtg-collection/inbox_pending" in topics
    assert "mtg-collection/inbox_pending/attributes" in topics
    assert "mtg-collection/sell_candidates" in topics
    assert "mtg-collection/unlisted_value_eur" in topics


@pytest.mark.anyio
async def test_signal_sensors_only_published_when_mtgstocks_enabled(fake_mqtt, monkeypatch):
    from app import config

    keys = {e.key for e in ha_publisher.active_entities()}
    assert "signals_buy" not in keys

    monkeypatch.setattr(config.get_settings(), "mtgstocks_enabled", True)
    keys = {e.key for e in ha_publisher.active_entities()}
    assert {"signals_buy", "signals_sell"} <= keys


@pytest.mark.anyio
async def test_disabled_signal_configs_are_cleared(fake_mqtt):
    await ha_publisher.publish_discovery()

    cleared = [
        (t, p) for t, p, _ in _FakeClient.instances[0].published if p == ""
    ]
    assert [t for t, _ in cleared] == [
        "homeassistant/sensor/mtg_collection_signals_buy/config",
        "homeassistant/sensor/mtg_collection_signals_sell/config",
    ]


@pytest.mark.anyio
async def test_inbox_publish_is_debounced(fake_mqtt, monkeypatch):
    monkeypatch.setattr(ha_publisher, "INBOX_PUBLISH_DEBOUNCE_S", 0.02)
    monkeypatch.setattr(ha_publisher, "_inbox_publish_task", None)

    calls = []

    async def _record():
        calls.append(1)

    monkeypatch.setattr(ha_publisher, "publish_inbox_sensors", _record)

    for _ in range(5):  # five rapid triage decisions
        ha_publisher.schedule_inbox_publish()

    await asyncio.sleep(0.1)
    assert calls == [1]


@pytest.mark.anyio
async def test_delete_wishlist_sensor_clears_retained_config(fake_mqtt):
    await ha_publisher.delete_wishlist_sensor(42)

    published = _FakeClient.instances[0].published
    assert published == [("homeassistant/sensor/mtg_wishlist_42/config", "", True)]


@pytest.mark.anyio
async def test_manager_announces_online_and_subscribes(fake_mqtt):
    ha_publisher.start_ha_mqtt()
    for _ in range(100):  # let the manager task reach the connected state
        if ha_mqtt._client is not None:
            break
        await asyncio.sleep(0.01)

    client = _FakeClient.instances[0]
    assert client.subscribed == ["mtg-collection/service/+"]
    assert ("mtg-collection/status", "online", True) in client.published
    assert client.kwargs["will"].payload == "offline"
    assert ha_mqtt._client is client

    # Publishing while the manager is connected must reuse its client
    await ha_mqtt.publish("mtg-collection/total_cards", "5")
    assert len(_FakeClient.instances) == 1

    await ha_mqtt.shutdown()
    assert ("mtg-collection/status", "offline", True) in client.published
    assert ha_mqtt._client is None


@pytest.mark.anyio
async def test_service_message_answers_on_response_topic(fake_mqtt):
    await ha_publisher._on_service_message("mtg-collection/service/add_to_wishlist", b"{}")

    published = _FakeClient.instances[0].published
    topic, payload, _ = published[0]
    assert topic == "mtg-collection/service/add_to_wishlist/response"
    # No card_name in the payload → error is reported back, not raised
    assert "error" in json.loads(payload)


@pytest.mark.anyio
async def test_service_response_topics_are_ignored(fake_mqtt):
    await ha_publisher._on_service_message(
        "mtg-collection/service/trigger_sync/response", b"{}"
    )
    assert _FakeClient.instances == []


# --- sprint 30: game logging service + deck sensors --------------------------


@pytest.mark.anyio
async def test_log_game_service_returns_game_id(fake_mqtt):
    from _helpers import insert_deck
    from app.database import get_db

    db = await get_db()
    deck_id = await insert_deck(db, "Atraxa")

    await ha_publisher._on_service_message(
        "mtg-collection/service/log_game",
        b'{"deck": "Atraxa", "result": "win", "turns": 8}',
    )

    topic, payload, _ = _FakeClient.instances[0].published[0]
    assert topic == "mtg-collection/service/log_game/response"
    body = json.loads(payload)
    assert body["status"] == "logged"
    assert body["deck_id"] == deck_id


@pytest.mark.anyio
async def test_log_game_service_reports_ambiguous_deck(fake_mqtt):
    from _helpers import insert_deck
    from app.database import get_db

    db = await get_db()
    await insert_deck(db, "Krenko Goblins")
    await insert_deck(db, "Krenko Mob Boss")

    await ha_publisher._on_service_message(
        "mtg-collection/service/log_game", b'{"deck": "Krenko", "result": "win"}'
    )

    body = json.loads(_FakeClient.instances[0].published[0][1])
    assert "matches 2 decks" in body["error"]
    assert len(body["candidates"]) == 2


@pytest.mark.anyio
async def test_log_game_service_reports_validation_errors(fake_mqtt):
    from _helpers import insert_deck
    from app.database import get_db

    db = await get_db()
    await insert_deck(db, "Atraxa")

    await ha_publisher._on_service_message(
        "mtg-collection/service/log_game", b'{"deck": "Atraxa", "result": "victory"}'
    )

    body = json.loads(_FakeClient.instances[0].published[0][1])
    assert "error" in body


@pytest.mark.anyio
async def test_create_listing_service(fake_mqtt):
    from app.database import get_db

    await ha_publisher._on_service_message(
        "mtg-collection/service/create_listing",
        b'{"card_name": "Sol Ring", "price": 1.5, "quantity": 2}',
    )

    body = json.loads(_FakeClient.instances[0].published[0][1])
    assert body["status"] == "created"

    db = await get_db()
    cursor = await db.execute("SELECT card_name, quantity FROM cardmarket_listings")
    assert [tuple(r) for r in await cursor.fetchall()] == [("Sol Ring", 2)]


@pytest.mark.anyio
async def test_triage_service_reports_api_errors(fake_mqtt):
    await ha_publisher._on_service_message(
        "mtg-collection/service/triage", b'{"event_id": 999, "action": "keep"}'
    )

    body = json.loads(_FakeClient.instances[0].published[0][1])
    assert body["status_code"] == 404


@pytest.mark.anyio
async def test_triage_service_decides_an_event(fake_mqtt):
    from _helpers import add_acquisition_event, insert_card
    from app.database import get_db

    db = await get_db()
    card = await insert_card(db, "Sol Ring")
    event_id = await add_acquisition_event(db, card)

    await ha_publisher._on_service_message(
        "mtg-collection/service/triage",
        f'{{"event_id": {event_id}, "action": "keep"}}'.encode(),
    )

    body = json.loads(_FakeClient.instances[0].published[0][1])
    assert body["status"] == "ok"
    assert body["triage_state"] == "keep"

    cursor = await db.execute(
        "SELECT triage_state, source FROM acquisition_events WHERE id = ?", (event_id,)
    )
    row = await cursor.fetchone()
    assert row["triage_state"] == "keep"
    assert row["source"] == "other"  # defaulted for HA-initiated decisions


@pytest.mark.anyio
async def test_states_without_a_value_are_not_published(fake_mqtt):
    """Never played → the timestamp sensor must not get an empty payload."""
    await ha_publisher.publish_deck_sensors()

    topics = [t for t, _, _ in _FakeClient.instances[0].published]
    assert "mtg-collection/games_30d" in topics
    assert "mtg-collection/last_game_at" not in topics


@pytest.mark.anyio
async def test_deck_sensors_publish_active_and_clear_inactive(fake_mqtt):
    from _helpers import insert_deck
    from app.database import get_db

    db = await get_db()
    active = await insert_deck(db, "Atraxa")
    stale = await insert_deck(db, "Old Deck")
    await db.execute(
        "INSERT INTO deck_games (deck_id, played_at, result)"
        " VALUES (?, date('now','-2 days'), 'win')",
        (active,),
    )
    await db.execute(
        "INSERT INTO deck_games (deck_id, played_at, result)"
        " VALUES (?, date('now','-200 days'), 'loss')",
        (stale,),
    )
    await db.commit()

    await ha_publisher.publish_deck_sensors()

    published = dict((t, p) for t, p, _ in _FakeClient.instances[0].published)

    # Overall sensors
    assert published["mtg-collection/games_30d"] == "1"
    assert published["mtg-collection/last_game_result"] == "win"

    # Active deck: discovery + state
    config = json.loads(published[f"homeassistant/sensor/mtg_deck_{active}_winrate/config"])
    assert config["unique_id"] == f"mtg_deck_{active}_winrate"
    assert config["name"] == "MTG Deck Atraxa Win Rate"
    assert config["value_template"] == "{{ value_json.win_rate }}"
    state = json.loads(published[f"mtg-collection/deck/{active}/state"])
    assert state["win_rate"] == 100.0
    assert state["games"] == 1

    # Inactive deck: retained config cleared, no state
    assert published[f"homeassistant/sensor/mtg_deck_{stale}_winrate/config"] == ""
    assert f"mtg-collection/deck/{stale}/state" not in published
