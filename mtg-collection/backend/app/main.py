"""MTG Collection Manager - FastAPI Application."""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db, close_db
from .logging_config import setup_logging
from .scheduler import start_scheduler, stop_scheduler
from .version import VERSION
from .routers import decks, collection, cardmarket, sync, cards, stats, wishlist, backup, mcp_setup

setup_logging()

try:
    from .mcp_server import mount_mcp_server, mcp as mcp_server
    _mcp_available = True
except Exception:
    _mcp_available = False
    mcp_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()

    start_scheduler()

    # Publish MQTT discovery configs at startup
    if settings.mqtt_enabled:
        import asyncio
        from .services.ha_publisher import publish_discovery, publish_stats
        asyncio.create_task(_startup_mqtt_publish())

    # Start MCP session manager (required for streamable HTTP transport)
    if _mcp_available and mcp_server is not None:
        async with mcp_server.session_manager.run():
            yield
    else:
        yield

    stop_scheduler()
    await close_db()


async def _startup_mqtt_publish():
    """Publish MQTT discovery configs and initial stats after startup."""
    import asyncio
    await asyncio.sleep(10)  # Wait for DB to be populated
    try:
        from .services.ha_publisher import publish_discovery, publish_stats
        await publish_discovery()
        await publish_stats()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Startup MQTT publish failed: %s", e)


app = FastAPI(
    title="MTG Collection Manager",
    version=VERSION,
    lifespan=lifespan,
    root_path=os.environ.get("INGRESS_ENTRY", "/"),
)

# CORS: disabled by default (same-origin via HA Ingress).
# Enable for standalone dev with CORS_ORIGINS=http://localhost:5173
cors_origins = os.environ.get("CORS_ORIGINS", "")
if cors_origins:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# API routes
app.include_router(decks.router, prefix="/api/decks", tags=["decks"])
app.include_router(collection.router, prefix="/api/collection", tags=["collection"])
app.include_router(cardmarket.router, prefix="/api/cardmarket", tags=["cardmarket"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(wishlist.router, prefix="/api/wishlist", tags=["wishlist"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
app.include_router(mcp_setup.router, prefix="/api/mcp", tags=["mcp"])


@app.get("/healthz", tags=["health"])
async def healthz():
    from .database import get_db
    from .version import VERSION
    from .scheduler import is_scheduler_running

    db_ok = False
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    body = {
        "status": "ok" if db_ok else "degraded",
        "version": VERSION,
        "db": db_ok,
        "scheduler_running": is_scheduler_running(),
    }

    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(content=body, status_code=503)
    return body

# Mount MCP server
if _mcp_available:
    try:
        mount_mcp_server(app)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("MCP server failed to mount: %s", e)

# Serve frontend (must be last)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
