"""pytest configuration for backend smoke tests."""
import os
import pytest

# Use an in-memory SQLite database for tests so no real data file is required.
os.environ.setdefault("DATABASE_URL", ":memory:")
os.environ.setdefault("HA_URL", "http://localhost:8123")
os.environ.setdefault("HA_TOKEN", "test-token")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
