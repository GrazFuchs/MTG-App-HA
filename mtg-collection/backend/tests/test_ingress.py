"""Deep links into the add-on UI (ingress path resolution)."""
import pytest
from app import config
from app.services import ha_metrics, ha_publisher, ingress
from conftest import FakeMqttClient

ENTRY = "/api/hassio_ingress/abc123XYZ"


@pytest.fixture
def under_supervisor(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "ingress_entry", ENTRY)


def test_no_base_outside_supervisor():
    """INGRESS_ENTRY stays "/" in standalone Docker — there is no absolute link."""
    assert ingress.ingress_base() == ""
    assert ingress.ingress_url("/inbox") == ""
    assert ingress.deep_links() == {}


def test_base_strips_a_trailing_slash(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "ingress_entry", f"{ENTRY}/")
    assert ingress.ingress_base() == ENTRY


def test_urls_are_absolute_ingress_paths(under_supervisor):
    assert ingress.ingress_url("/inbox") == f"{ENTRY}/inbox"
    assert ingress.ingress_url("/") == ENTRY


def test_deep_links_cover_the_ui_routes(under_supervisor):
    links = ingress.deep_links()
    assert links["inbox"] == f"{ENTRY}/inbox"
    assert links["cardmarket"] == f"{ENTRY}/cardmarket"
    assert links["dashboard"] == ENTRY
    assert set(links) == set(ingress.DEEP_LINKS)


def test_metrics_expose_base_and_links(under_supervisor):
    m = ha_metrics.addon_metrics()
    assert m.states["ingress_url"] == ENTRY
    assert m.attributes["ingress_url"]["wishlist"] == f"{ENTRY}/wishlist"


def test_metrics_publish_nothing_without_ingress():
    m = ha_metrics.addon_metrics()
    assert m.states["ingress_url"] is None  # → sensor stays unknown in HA


def test_sensor_is_part_of_the_discovery_set():
    keys = {e.key for e in ha_publisher.active_entities()}
    assert "ingress_url" in keys


@pytest.mark.anyio
async def test_stats_publish_includes_the_link(fake_mqtt, under_supervisor):
    await ha_publisher.publish_stats()

    published = dict((t, p) for t, p, _ in FakeMqttClient.all_published())
    assert published["mtg-collection/ingress_url"] == ENTRY
    assert "mtg-collection/ingress_url/attributes" in published


@pytest.mark.anyio
async def test_stats_publish_omits_an_unknown_link(fake_mqtt):
    await ha_publisher.publish_stats()

    topics = [t for t, _, _ in FakeMqttClient.all_published()]
    assert "mtg-collection/ingress_url" not in topics


# --- persistent notifications ----------------------------------------------


@pytest.fixture
def sent_notification(monkeypatch):
    """Capture the payload a persistent notification would POST to Supervisor."""
    from app.services import notifications

    sent: dict = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            sent.update(kwargs.get("json", {}))
            return _Resp()

    monkeypatch.setattr(notifications, "_get_supervisor_token", lambda: "token")
    monkeypatch.setattr(notifications.httpx, "AsyncClient", _Client)
    return sent


@pytest.mark.anyio
async def test_notification_deep_link_is_resolved(sent_notification, under_supervisor):
    """Regression: the link used INGRESS_TOKEN, which nothing ever sets."""
    from app.services import notifications

    await notifications.send_persistent_notification(
        "Title", "Body", deep_link="/cardmarket"
    )

    assert f"{ENTRY}/cardmarket" in sent_notification["message"]


@pytest.mark.anyio
async def test_notification_omits_an_unresolvable_link(sent_notification):
    """A bare '/cardmarket' would resolve against HA itself and 404."""
    from app.services import notifications

    await notifications.send_persistent_notification(
        "Title", "Body", deep_link="/cardmarket"
    )

    assert "Open in MTG Collection" not in sent_notification["message"]
    assert sent_notification["message"] == "Body"
