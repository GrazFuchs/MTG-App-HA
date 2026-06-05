"""Commander Spellbook API client for combo detection."""
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)

SPELLBOOK_BASE = "https://backend.commanderspellbook.com"
USER_AGENT = "MTGCollectionManager/0.9.0"


class SpellbookClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=SPELLBOOK_BASE,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=30.0,
            )
        return self._client

    async def find_combos_in_decklist(
        self,
        card_names: list[str],
        commander_name: str | None = None,
    ) -> dict[str, Any]:
        """Find combos contained in (or one card away from) a decklist.

        Returns:
            {
                "included": [list of full combos with all cards present],
                "almost_included": [combos missing 1 card],
            }
        """
        client = await self._get_client()
        main_list = [{"card": name, "quantity": 1} for name in card_names]
        commanders_list = []
        if commander_name:
            commanders_list = [{"card": commander_name, "quantity": 1}]

        payload: dict[str, Any] = {"main": main_list}
        if commanders_list:
            payload["commanders"] = commanders_list

        logger.debug("Spellbook request: %d cards, commander=%s", len(card_names), commander_name)
        resp = await client.post("/find-my-combos/", json=payload)
        resp.raise_for_status()
        data = resp.json()

        # API nests combos under results.included / results.almost_included
        results = data.get("results", data)
        if isinstance(results, dict):
            included = results.get("included", [])
            almost = results.get("almost_included", results.get("almostIncluded", []))
        else:
            included = []
            almost = []

        logger.info("Spellbook returned %d included, %d almost_included combos", len(included), len(almost))
        return {"included": included, "almost_included": almost}

    async def get_combo_detail(self, combo_id: str) -> dict[str, Any]:
        """Fetch full details for a specific combo."""
        client = await self._get_client()
        resp = await client.get(f"/variants/{combo_id}/")
        resp.raise_for_status()
        return resp.json()


spellbook = SpellbookClient()
