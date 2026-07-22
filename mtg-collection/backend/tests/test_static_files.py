"""Serving the SPA: cache headers and client-side route fallback."""
import pytest
from app.static_files import IMMUTABLE, NO_CACHE, SpaStaticFiles
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """An app mounting a minimal built frontend, plus one API route."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(
        '<html><script src="./assets/index-abc123.js"></script></html>'
    )
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    (tmp_path / "favicon.ico").write_text("icon")

    app = FastAPI()

    @app.get("/api/stats")
    async def stats():
        return {"ok": True}

    app.mount("/", SpaStaticFiles(directory=str(tmp_path), html=True), name="static")
    return TestClient(app)


# --- cache headers ----------------------------------------------------------


def test_index_is_never_cached(client):
    """Its name is stable while the asset hashes change on every build."""
    for path in ("/", "/index.html"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == NO_CACHE


def test_hashed_assets_are_cached_forever(client):
    resp = client.get("/assets/index-abc123.js")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == IMMUTABLE


def test_unhashed_root_files_are_not_cached_forever(client):
    """favicon.ico keeps its name, so it must revalidate like the HTML."""
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == NO_CACHE


# --- SPA fallback -----------------------------------------------------------


def test_client_side_route_serves_the_shell(client):
    """Reloading or bookmarking /inbox used to 404."""
    resp = client.get("/inbox")
    assert resp.status_code == 200
    assert "<html>" in resp.text
    assert resp.headers["cache-control"] == NO_CACHE


def test_nested_client_side_route(client):
    resp = client.get("/decks/42")
    assert resp.status_code == 200
    assert "<html>" in resp.text


def test_missing_asset_stays_a_404(client):
    """Answering a missing .js with HTML turns a clear error into a MIME error."""
    resp = client.get("/assets/index-gone.js")
    assert resp.status_code == 404
    assert "<html>" not in resp.text


def test_unknown_api_path_stays_a_404(client):
    """The SPA shell must not swallow API errors."""
    for path in ("/api/nope", "/api/decks/does-not-exist"):
        resp = client.get(path)
        assert resp.status_code == 404, path
        assert "<html>" not in resp.text


def test_real_api_route_is_untouched(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_mcp_path_stays_a_404(client):
    resp = client.get("/mcp")
    assert resp.status_code == 404
    assert "<html>" not in resp.text
