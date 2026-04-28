"""Scryfall API client with rate limiting."""
import asyncio
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from ..version import VERSION

SCRYFALL_BASE = "https://api.scryfall.com"
USER_AGENT = f"MTGCollectionManager/{VERSION}"
RATE_LIMIT_DELAY = 0.1  # 100ms between requests


class ScryfallClient:
    def __init__(self):
        self._last_request = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=SCRYFALL_BASE,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json;q=0.9,*/*;q=0.8",
                },
                timeout=30.0,
            )
        return self._client

    async def _rate_limit(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        await self._rate_limit()
        client = await self._get_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def search_cards(self, query: str, page: int = 1) -> dict[str, Any]:
        return await self._get("/cards/search", params={"q": query, "page": page})

    async def get_card_by_id(self, scryfall_id: str) -> dict[str, Any]:
        return await self._get(f"/cards/{scryfall_id}")

    async def get_card_by_name(self, name: str, exact: bool = True) -> dict[str, Any]:
        param_key = "exact" if exact else "fuzzy"
        return await self._get("/cards/named", params={param_key: name})

    async def get_card_by_set(self, set_code: str, collector_number: str) -> dict[str, Any]:
        return await self._get(f"/cards/{set_code}/{collector_number}")

    async def autocomplete(self, query: str) -> list[str]:
        data = await self._get("/cards/autocomplete", params={"q": query})
        return data.get("data", [])

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def parse_scryfall_card(data: dict[str, Any]) -> dict[str, Any]:
    """Parse Scryfall card JSON into our DB-compatible format."""
    image_uris = data.get("image_uris", {})
    # Handle double-faced cards
    if not image_uris and "card_faces" in data:
        faces = data["card_faces"]
        if faces:
            image_uris = faces[0].get("image_uris", {})

    prices = data.get("prices", {})

    return {
        "scryfall_id": data["id"],
        "oracle_id": data.get("oracle_id", ""),
        "name": data.get("name", ""),
        "mana_cost": data.get("mana_cost", ""),
        "cmc": data.get("cmc", 0),
        "type_line": data.get("type_line", ""),
        "oracle_text": data.get("oracle_text", ""),
        "colors": json.dumps(data.get("colors", [])),
        "color_identity": json.dumps(data.get("color_identity", [])),
        "set_code": data.get("set", ""),
        "set_name": data.get("set_name", ""),
        "collector_number": data.get("collector_number", ""),
        "rarity": data.get("rarity", ""),
        "image_uri": image_uris.get("normal", ""),
        "image_art_crop": image_uris.get("art_crop", ""),
        "power": data.get("power", ""),
        "toughness": data.get("toughness", ""),
        "loyalty": data.get("loyalty", ""),
        "keywords": json.dumps(data.get("keywords", [])),
        "legalities": json.dumps(data.get("legalities", {})),
        "edhrec_rank": data.get("edhrec_rank"),
        "price_usd": prices.get("usd") or "",
        "price_eur": prices.get("eur") or "",
        "price_usd_foil": prices.get("usd_foil") or "",
        "price_eur_foil": prices.get("eur_foil") or "",
    }


# Singleton
scryfall = ScryfallClient()
