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
        decklist = "\n".join(f"1 {n}" for n in card_names)
        if commander_name:
            decklist += f"\n\nCommander\n1 {commander_name}"

        resp = await client.post("/find-my-combos/", json={"main": decklist})
        resp.raise_for_status()
        data = resp.json()
        # Normalize response: Spellbook may return results or included/almost_included
        if "results" in data and "included" not in data:
            return {"included": data.get("results", []), "almost_included": []}
        return {
            "included": data.get("included", data.get("results", [])),
            "almost_included": data.get("almost_included", data.get("almostIncluded", [])),
        }

    async def get_combo_detail(self, combo_id: str) -> dict[str, Any]:
        """Fetch full details for a specific combo."""
        client = await self._get_client()
        resp = await client.get(f"/variants/{combo_id}/")
        resp.raise_for_status()
        return resp.json()


spellbook = SpellbookClient()
