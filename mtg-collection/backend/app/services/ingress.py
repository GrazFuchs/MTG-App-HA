"""Resolving links into the add-on's own UI.

The Supervisor hands the add-on its ingress path (``/api/hassio_ingress/<token>``)
at startup; ``run.sh`` reads it from ``/addons/self/info`` and exports it as
``INGRESS_ENTRY``.  Everything that wants to link into the UI — persistent
notifications, the HA sensor — resolves through here, so the token lives in one
place.
"""
from __future__ import annotations

from ..config import get_settings

# UI routes worth linking to from a dashboard (see frontend/src/App.tsx).
DEEP_LINKS = {
    "dashboard": "/",
    "decks": "/decks",
    "collection": "/collection",
    "inbox": "/inbox",
    "duplicates": "/duplicates",
    "cardmarket": "/cardmarket",
    "wishlist": "/wishlist",
    "settings": "/settings",
}


def ingress_base() -> str:
    """The add-on's ingress path without a trailing slash, or "" when unknown.

    Empty outside a Supervisor environment (standalone Docker, tests), where
    ``INGRESS_ENTRY`` stays at its "/" default and no absolute link exists.
    """
    entry = (get_settings().ingress_entry or "").strip()
    if entry in ("", "/"):
        return ""
    return entry.rstrip("/")


def ingress_url(path: str = "/") -> str:
    """Resolve a UI path to a link HA can follow.

    Returns "" when the ingress path is unknown — callers must not fall back to
    the bare path, which would resolve against Home Assistant itself and 404.
    """
    base = ingress_base()
    if not base:
        return ""
    return f"{base}{path}" if path != "/" else base


def deep_links() -> dict[str, str]:
    """All known UI routes as resolved ingress links (empty when unknown)."""
    if not ingress_base():
        return {}
    return {name: ingress_url(path) for name, path in DEEP_LINKS.items()}
