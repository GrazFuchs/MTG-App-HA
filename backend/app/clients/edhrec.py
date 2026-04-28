"""EDHREC client (unofficial JSON endpoints)."""
import asyncio
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from ..version import VERSION

EDHREC_JSON_BASE = "https://json.edhrec.com/pages"
USER_AGENT = f"MTGCollectionManager/{VERSION}"
CACHE_TTL = 86400  # 24 hours


class EDHRECClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=EDHREC_JSON_BASE,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=30.0,
            )
        return self._client

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < CACHE_TTL:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any):
        self._cache[key] = (time.time(), data)

    async def _get(self, path: str) -> dict[str, Any] | None:
        cached = self._get_cached(path)
        if cached is not None:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(path)
            if resp.status_code == 200:
                data = resp.json()
                self._set_cached(path, data)
                return data
            logger.warning("EDHREC returned %d for %s", resp.status_code, path)
        except Exception as e:
            logger.warning("EDHREC request failed for %s: %s", path, e)

        return None

    async def get_commander_recommendations(self, commander_slug: str) -> dict[str, Any] | None:
        """Get top cards and recommendations for a commander."""
        return await self._get(f"/commanders/{commander_slug}.json")

    async def get_commanders_by_color(self, color_combo: str) -> dict[str, Any] | None:
        """Get list of commanders for a color combination (e.g., 'golgari')."""
        return await self._get(f"/commanders/{color_combo}.json")

    async def get_combos(self, commander_slug: str) -> dict[str, Any] | None:
        """Get combos for a commander."""
        return await self._get(f"/combos/{commander_slug}.json")

    async def get_top_cards(self, category: str = "all") -> dict[str, Any] | None:
        """Get top cards by category."""
        if category == "all":
            return await self._get("/top.json")
        return await self._get(f"/top/{category}.json")

    async def get_themes(self, theme_slug: str) -> dict[str, Any] | None:
        """Get theme-based recommendations."""
        return await self._get(f"/themes/{theme_slug}.json")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def parse_edhrec_recommendations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse EDHREC commander page into a list of recommended cards."""
    results = []
    container = data.get("container", {})
    json_dict = container.get("json_dict", {})
    cardlists = json_dict.get("cardlists", [])

    for cardlist in cardlists:
        header = cardlist.get("header", "")
        cardviews = cardlist.get("cardviews", [])
        for cv in cardviews:
            results.append({
                "name": cv.get("name", ""),
                "sanitized": cv.get("sanitized", ""),
                "url": cv.get("url", ""),
                "inclusion": cv.get("inclusion", 0),
                "num_decks": cv.get("num_decks", 0),
                "synergy": cv.get("synergy", 0),
                "category": header,
            })
    return results


def parse_edhrec_combos(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse EDHREC combos page."""
    results = []
    container = data.get("container", {})
    json_dict = container.get("json_dict", {})
    combos = json_dict.get("cardlists", [])

    for combo_list in combos:
        for combo in combo_list.get("cardviews", []):
            results.append({
                "cards": combo.get("names", []),
                "color_identity": combo.get("color_identity", []),
                "result": combo.get("result", ""),
                "link": combo.get("url", ""),
            })
    return results


def slugify_commander(name: str) -> str:
    """Turn a commander name into an EDHREC URL slug."""
    import re
    slug = name.lower()
    slug = slug.replace("'", "").replace(",", "").replace(".", "")
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    # Handle double-faced cards: use front face
    if " // " in name:
        slug = slugify_commander(name.split(" // ")[0])
    return slug


# Singleton
edhrec = EDHRECClient()
