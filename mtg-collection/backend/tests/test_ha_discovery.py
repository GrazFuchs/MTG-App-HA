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
    assert [e.object_id for e in ha_publisher.AGGREGATE_SENSORS] == EXPECTED_UNIQUE_IDS


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


def test_wishlist_entity_shape_unchanged():
    entity = ha_publisher._wishlist_entity(42, "Sol Ring", "C21", "mtg-collection")
    payload = discovery_payload(entity, "mtg-collection", "mtg-collection/status")

    assert discovery_topic(entity) == "homeassistant/sensor/mtg_wishlist_42/config"
    assert payload["unique_id"] == "mtg_wishlist_42"
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
    assert len(published) == len(ha_publisher.AGGREGATE_SENSORS)
    assert all(retain for _, _, retain in published)

    topics = [t for t, _, _ in published]
    assert "homeassistant/sensor/mtg_collection_total_cards/config" in topics

    payload = json.loads(published[0][1])
    assert payload["availability_topic"] == "mtg-collection/status"


@pytest.mark.anyio
async def test_stats_publish_uses_one_connection(fake_mqtt):
    await ha_publisher.publish_stats()

    assert len(_FakeClient.instances) == 1
    topics = [t for t, _, _ in _FakeClient.instances[0].published]
    assert "mtg-collection/total_cards" in topics
    assert "mtg-collection/listings_fair" in topics


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
