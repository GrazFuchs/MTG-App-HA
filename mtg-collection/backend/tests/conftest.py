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
