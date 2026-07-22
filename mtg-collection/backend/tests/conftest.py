"""pytest configuration and shared fixtures for backend tests.

`ASGITransport` does not run the FastAPI lifespan, so the database is never
initialised automatically during tests. The autouse `_database` fixture below
gives every test a fresh, isolated, file-backed SQLite database (schema +
migrations applied) and resets the module-level connection globals afterwards.
"""
import os

import pytest
import pytest_asyncio

os.environ.setdefault("HA_URL", "http://localhost:8123")
os.environ.setdefault("HA_TOKEN", "test-token")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(autouse=True)
async def _database(tmp_path, monkeypatch):
    """Initialise a fresh database in a per-test temp dir."""
    from app import config, database

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OPTIONS_PATH", str(tmp_path / "options.json"))
    config.get_settings.cache_clear()

    await database.init_db()
    try:
        yield
    finally:
        await database.close_db()
        config.get_settings.cache_clear()


class FakeMqttClient:
    """Stands in for aiomqtt.Client; records what would hit the broker."""

    instances: list["FakeMqttClient"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.published: list[tuple[str, object, bool]] = []
        self.subscribed: list[str] = []
        FakeMqttClient.instances.append(self)

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
            import asyncio

            await asyncio.Event().wait()  # blocks until cancelled
            yield  # pragma: no cover

        return _idle()

    @classmethod
    def all_published(cls) -> list[tuple[str, object, bool]]:
        """Every message across all connections, in order."""
        return [msg for client in cls.instances for msg in client.published]


class FakeWill:
    def __init__(self, topic, payload=None, qos=0, retain=False):
        self.topic = topic
        self.payload = payload
        self.retain = retain


@pytest.fixture
def fake_mqtt(monkeypatch):
    """Enable MQTT and swap aiomqtt for the recording fake client."""
    from app import config
    from app.services import ha_mqtt

    FakeMqttClient.instances = []
    fake_module = type("_FakeAiomqtt", (), {"Client": FakeMqttClient, "Will": FakeWill})
    monkeypatch.setattr(ha_mqtt, "_aiomqtt_module", fake_module)
    monkeypatch.setattr(ha_mqtt, "_aiomqtt_checked", True)
    monkeypatch.setattr(ha_mqtt, "_client", None)
    monkeypatch.setattr(ha_mqtt, "_handlers", [])
    monkeypatch.setattr(ha_mqtt, "_manager_task", None)
    monkeypatch.setattr(config.get_settings(), "mqtt_enabled", True)
    yield
