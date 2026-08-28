"""Commander Spellbook API client for combo detection."""
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)

from ..version import VERSION

SPELLBOOK_BASE = "https://backend.commanderspellbook.com"
USER_AGENT = f"MTGCollectionManager/{VERSION}"


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

        # The answer nests under `results` and is bucketed by how far the deck
        # is from the combo (verified against the live API, 2026-08-28):
        #   included                                    every card present
        #   almostIncluded                              one card short
        #   almostIncludedByAddingColors                ... and outside the
        #                                               colour identity
        #   includedByChangingCommanders                ... with another
        #   almostIncludedByChangingCommanders          commander
        #   almostIncludedByAddingColorsAndChangingCommanders
        # Only the first two are usable advice for *this* deck. The rest are
        # counted into the log rather than silently dropped, so a decision not
        # to store them stays visible.
        results = data.get("results", data)
        if isinstance(results, dict):
            included = results.get("included", [])
            almost = results.get("almost_included", results.get("almostIncluded", []))
            out_of_scope = sum(
                len(results.get(bucket, []))
                for bucket in (
                    "includedByChangingCommanders",
                    "almostIncludedByAddingColors",
                    "almostIncludedByChangingCommanders",
                    "almostIncludedByAddingColorsAndChangingCommanders",
                )
            )
        else:
            included = []
            almost = []
            out_of_scope = 0

        logger.info(
            "Spellbook: %d complete, %d one card short, %d ignored "
            "(need other colours or another commander)",
            len(included), len(almost), out_of_scope,
        )
        return {"included": included, "almost_included": almost}

    async def get_combo_detail(self, combo_id: str) -> dict[str, Any]:
        """Fetch full details for a specific combo."""
        client = await self._get_client()
        resp = await client.get(f"/variants/{combo_id}/")
        resp.raise_for_status()
        return resp.json()


spellbook = SpellbookClient()
