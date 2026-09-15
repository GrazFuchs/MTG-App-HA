"""Archidekt API client with authentication support."""
import asyncio
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from ..services.formats import format_name
from ..version import VERSION

ARCHIDEKT_BASE = "https://archidekt.com"
USER_AGENT = f"MTGCollectionManager/{VERSION}"

# Rate limiting: pause between API calls to avoid 429
API_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 4  # retries on 429 with exponential backoff


class ArchidektClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._cookies: dict[str, str] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
            if self._token:
                headers["Authorization"] = f"JWT {self._token}"
            self._client = httpx.AsyncClient(
                base_url=ARCHIDEKT_BASE,
                headers=headers,
                cookies=self._cookies,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def login(self, username: str, password: str) -> bool:
        """Authenticate with Archidekt and store JWT token."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

        async with httpx.AsyncClient(
            base_url=ARCHIDEKT_BASE,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            timeout=30.0,
        ) as client:
            resp = await client.post(
                "/api/rest-auth/login/",
                json={"username": username, "password": password},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("key") or data.get("token")
                if self._token:
                    # Capture cookies from login response
                    self._cookies = dict(resp.cookies)
                    # Set JWT cookie for SSR pages (Archidekt uses cookie auth for web pages)
                    self._cookies["jwt"] = self._token
                    logger.info("Archidekt login successful for %s", username)
                    return True
            logger.warning("Archidekt login failed: status=%s", resp.status_code)
            return False

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    async def _request_with_backoff(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an HTTP request with exponential backoff on 429."""
        client = await self._get_client()
        await asyncio.sleep(API_DELAY)

        for attempt in range(MAX_RETRIES + 1):
            resp = await getattr(client, method)(url, **kwargs)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    wait = 2 ** (attempt + 2)  # 4, 8, 16, 32s
                    logger.warning("429 on %s (attempt %d/%d), waiting %ds...", url, attempt + 1, MAX_RETRIES, wait)
                    await asyncio.sleep(wait)
                    continue
            break
        return resp

    async def get_deck(self, deck_id: int) -> dict[str, Any]:
        """Fetch a single deck by ID. Returns full deck JSON with cards."""
        resp = await self._request_with_backoff("get", f"/api/decks/{deck_id}/")
        if resp.status_code == 404:
            raise ValueError(f"Deck {deck_id} not found or is private")
        resp.raise_for_status()
        return resp.json()

    async def get_deck_small(self, deck_id: int) -> dict[str, Any]:
        """Fetch deck metadata without cards (lighter endpoint)."""
        resp = await self._request_with_backoff("get", f"/api/decks/{deck_id}/small/")
        if resp.status_code == 404:
            raise ValueError(f"Deck {deck_id} not found or is private")
        resp.raise_for_status()
        return resp.json()

    async def get_folder(self, folder_id: int) -> dict[str, Any]:
        """Fetch folder metadata by ID. Returns folder name, parent, etc."""
        resp = await self._request_with_backoff("get", f"/api/decks/folders/{folder_id}/")
        if resp.status_code == 404:
            return {"id": folder_id, "name": ""}
        resp.raise_for_status()
        return resp.json()

    async def get_user_deck_ids(self, username: str) -> list[int]:
        """Discover deck IDs for a user (includes private decks when authenticated)."""
        client = await self._get_client()
        all_ids: list[int] = []

        # Try API-based discovery first (user profile may list decks)
        if self.is_authenticated:
            try:
                resp = await client.get("/api/rest-auth/user/")
                if resp.status_code == 200:
                    user_data = resp.json()
                    logger.info("User profile keys: %s", list(user_data.keys()) if isinstance(user_data, dict) else type(user_data))
                    # Check for deck info in user profile
                    if isinstance(user_data, dict) and "decks" in user_data:
                        for d in user_data["decks"]:
                            did = d.get("id") if isinstance(d, dict) else d
                            if did and did not in all_ids:
                                all_ids.append(int(did))
                        if all_ids:
                            logger.info("Found %d decks from user profile API", len(all_ids))
                            return all_ids
            except Exception as e:
                logger.warning("User profile deck discovery failed: %s", e)

        # HTML scraping with auth cookies (cookies enable private deck visibility)
        page = 1
        while True:
            await asyncio.sleep(API_DELAY)
            resp = await client.get(
                "/search/decks",
                params={"ownerUsername": username, "orderBy": "-updatedAt", "page": page},
            )
            if resp.status_code != 200:
                logger.warning("Deck search page %d returned %d", page, resp.status_code)
                break

            html = resp.text
            ids = [int(m) for m in re.findall(r'/decks/(\d+)/', html)]
            new_ids = list(dict.fromkeys(i for i in ids if i not in set(all_ids)))

            if not new_ids:
                break

            all_ids.extend(new_ids)
            logger.info("Discovered %d decks on page %d for user %s", len(new_ids), page, username)

            if f"page={page + 1}" not in html and 'Next' not in html:
                break
            page += 1

        logger.info("Total discovered decks for %s: %d", username, len(all_ids))
        return all_ids

    async def get_collection(self, user_id: int, page: int = 1) -> dict[str, Any]:
        """Fetch a user's collection page via v1 GET API.

        v2 doesn't support GET or POST properly (405 always), so use v1 directly.
        v1 supports pagination via ?page= parameter.
        Uses exponential backoff on 429.
        """
        resp = await self._request_with_backoff(
            "get",
            f"/api/collection/{user_id}/",
            params={"page": page},
        )
        if resp.status_code in (401, 403):
            raise PermissionError("Authentication required for collection access")
        resp.raise_for_status()
        data = resp.json()
        # v1 may return a list (single page) or a dict with pagination
        if isinstance(data, list):
            return {"results": data, "next": None}
        return data

    async def get_full_collection(self, user_id: int) -> list[dict[str, Any]]:
        """Fetch all pages of a user's collection."""
        all_cards: list[dict[str, Any]] = []
        page = 1

        while True:
            data = await self.get_collection(user_id, page=page)
            results = data.get("results", data.get("cards", []))
            if not results:
                break
            all_cards.extend(results)
            logger.info("Fetched collection page %d (%d cards, total %d)", page, len(results), len(all_cards))

            if not data.get("next"):
                break
            page += 1

        logger.info("Total collection cards: %d", len(all_cards))
        return all_cards

    async def search_user_decks(self, username: str, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        """Search for decks by a user (includes private if authenticated)."""
        deck_ids = await self.get_user_deck_ids(username)
        if not deck_ids:
            return {"results": [], "count": 0}

        results = []
        for did in deck_ids:
            try:
                deck = await self.get_deck_small(did)
                results.append(deck)
            except Exception as e:
                logger.warning("Could not fetch deck %d: %s", did, e)

        return {"results": results, "count": len(results)}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def parse_archidekt_deck(data: dict[str, Any]) -> dict[str, Any]:
    """Parse Archidekt deck JSON into our format."""
    owner = data.get("owner", {})
    cards_data = data.get("cards", [])

    commander_name = ""
    for card_entry in cards_data:
        categories = card_entry.get("categories") or []
        if "Commander" in categories:
            card_info = card_entry.get("card", {})
            oracle = card_info.get("oracleCard", {})
            commander_name = oracle.get("name", card_info.get("displayName", ""))
            break

    # Extract bracket. Archidekt's deck payload carries it as "edhBracket"
    # (verified 2026-08-23 against GET /api/decks/{id}/ — neither "bracket"
    # nor "deckBracket" exists there; both are kept only as legacy fallbacks).
    # The value is null unless the deck owner set a bracket on Archidekt.
    bracket = data.get("edhBracket") or data.get("bracket") or data.get("deckBracket") or 0
    if isinstance(bracket, str):
        try:
            bracket = int(bracket)
        except ValueError:
            bracket = 0

    format_id = data.get("deckFormat")
    try:
        format_id = int(format_id) if format_id is not None else None
    except (TypeError, ValueError):
        format_id = None

    return {
        "archidekt_id": data.get("id"),
        "name": data.get("name", ""),
        # The number is stored alongside the name it resolves to. The name is
        # a lookup that was wrong for every number above 6 until 0.47.0; the
        # number is what Archidekt actually said.
        "format": format_name(format_id),
        "archidekt_format_id": format_id,
        "description": data.get("description", ""),
        "featured_image": data.get("featured", ""),
        "commander_name": commander_name,
        "owner_username": owner.get("username", ""),
        "view_count": data.get("viewCount", 0),
        "created_at": data.get("createdAt"),
        "updated_at": data.get("updatedAt"),
        "bracket": bracket,
        # Which pile each of the deck's categories belongs to, so the card
        # parser can answer it per entry. See `deck_boards`.
        "boards": deck_boards(data),
    }


# ---------------------------------------------------------------------------
# Which pile is a card in?
# ---------------------------------------------------------------------------

#: The one category name Archidekt treats as a real sideboard. Everything else
#: a user invents ("Slot In", "Backlog", "Considering") is just a category, and
#: whether it counts towards the deck is the user's own setting -- which is
#: exactly what `includedInDeck` reports.
_SIDEBOARD_CATEGORY = "sideboard"

BOARD_MAIN = "main"
BOARD_SIDE = "side"
BOARD_MAYBE = "maybe"


def deck_boards(data: dict[str, Any]) -> dict[str, str]:
    """Map each deck-wide category name to 'main', 'side' or 'maybe'.

    Archidekt keeps this on the deck, not on the card: every category carries
    `includedInDeck`, and the user decides per category whether it counts. That
    is the answer we want, and it beats the hardcoded name list the frontend
    has been using -- "Slot In" is not a sideboard because it is called that,
    it is outside the deck because the owner said so.

    ⚠️ The flag alone is not enough, and this was measured rather than assumed
    (2026-09-15, deck 26328851): **`Sideboard` carries `includedInDeck: true`.**
    Archidekt counts the sideboard towards the deck's price and its card count,
    so main and sideboard are indistinguishable by the flag. Hence one name
    rule on top of it -- for the one name Archidekt itself defines.

    A category the deck does not declare falls back to 'main': an undeclared
    category is one nobody excluded.
    """
    boards: dict[str, str] = {}
    for category in data.get("categories") or []:
        name = (category.get("name") or "").strip()
        if not name:
            continue
        if not category.get("includedInDeck", True):
            boards[name] = BOARD_MAYBE
        elif name.lower() == _SIDEBOARD_CATEGORY:
            boards[name] = BOARD_SIDE
        else:
            boards[name] = BOARD_MAIN
    return boards


def board_of(categories: list[str], boards: dict[str, str]) -> str:
    """The pile a card entry sits in, given the deck's category map.

    A card can carry several categories ("Ramp, Plan Enablers"). The strictest
    one wins: anything outside the deck makes the whole entry outside the deck,
    because a card cannot be half in the maybeboard. Archidekt shows such an
    entry under its excluded category too.
    """
    seen = {boards.get(c.strip(), BOARD_MAIN) for c in categories if c and c.strip()}
    if BOARD_MAYBE in seen:
        return BOARD_MAYBE
    if BOARD_SIDE in seen:
        return BOARD_SIDE
    return BOARD_MAIN


def _type_line(oracle: dict[str, Any]) -> str:
    """Assemble a Scryfall-shaped type line from Archidekt's three type lists.

    Archidekt hands the type line out in pieces (`superTypes`, `types`,
    `subTypes`) and has no canonical string of its own. Scryfall's spelling is
    the house form — "Legendary Creature — Pirate Shark" — so it is what we
    build: type words separated by spaces, subtypes after an em dash.

    Until 0.36.0 the pieces were comma-joined instead ("Legendary, Creature —
    Pirate, Shark"). That form answered the card-type filter, so it looked
    harmless, but any filter naming two type words in a row missed every
    Archidekt-sourced card: `type_line NOT LIKE '%Basic Land%'` never excluded
    a single basic land, because the row said "Basic, Land — Plains".
    """
    head = " ".join(t for t in (oracle.get("superTypes") or []) + (oracle.get("types") or []) if t)
    subtypes = " ".join(t for t in (oracle.get("subTypes") or []) if t)
    if head and subtypes:
        return f"{head} — {subtypes}"
    return head or subtypes


def parse_archidekt_card(
    card_entry: dict[str, Any], boards: dict[str, str] | None = None
) -> dict[str, Any]:
    """Parse a card entry from an Archidekt deck into Scryfall-compatible format.

    `boards` is the deck's category map from `deck_boards`. It is optional
    because the collection sync parses entries that belong to no deck at all —
    those get 'main' and nothing reads it.
    """
    card_info = card_entry.get("card", {})
    oracle = card_info.get("oracleCard", {})
    edition = card_info.get("edition", {})
    prices = card_info.get("prices", {})

    uid = card_info.get("uid", "")

    image_uri = f"https://cards.scryfall.io/normal/front/{uid[0]}/{uid[1]}/{uid}.jpg" if uid else ""
    art_crop = f"https://cards.scryfall.io/art_crop/front/{uid[0]}/{uid[1]}/{uid}.jpg" if uid else ""

    categories = card_entry.get("categories") or []
    is_commander = "Commander" in categories
    is_companion = card_entry.get("companion") is not None

    return {
        "card": {
            "scryfall_id": uid,
            "oracle_id": oracle.get("uid", ""),
            "name": oracle.get("name", ""),
            "mana_cost": oracle.get("manaCost", ""),
            "cmc": oracle.get("cmc", 0),
            "type_line": _type_line(oracle),
            "oracle_text": oracle.get("text", ""),
            "colors": oracle.get("colors", []),
            "color_identity": oracle.get("colorIdentity", []),
            "set_code": edition.get("editioncode", ""),
            "set_name": edition.get("editionname", ""),
            "collector_number": card_info.get("collectorNumber", ""),
            "rarity": card_info.get("rarity", ""),
            "image_uri": image_uri,
            "image_art_crop": art_crop,
            "power": oracle.get("power", ""),
            "toughness": oracle.get("toughness", ""),
            "loyalty": oracle.get("loyalty", ""),
            "keywords": oracle.get("keywords", []),
            "edhrec_rank": oracle.get("edhrecRank"),
            "price_usd": str(prices.get("tcg", "") or ""),
            "price_eur": str(prices.get("cm", "") or ""),
            "price_usd_foil": str(prices.get("tcgfoil", "") or ""),
            "price_eur_foil": str(prices.get("cmfoil", "") or ""),
            "legalities": "{}",
        },
        "quantity": card_entry.get("quantity", 1),
        "category": ", ".join(categories) if categories else "",
        "board": board_of(categories, boards or {}),
        "is_commander": is_commander,
        "is_companion": is_companion,
        "modifier": card_entry.get("modifier", "Normal"),
    }


# The format table used to live here, written from memory when Commander was
# the only format that mattered. It was shifted by one from number 7 upward and
# nobody noticed for two years, because Commander is 3 in both the wrong table
# and the right one. It now lives in `services/formats.py`, where every entry
# is a measurement rather than a recollection, and where an unmeasured number
# is left blank instead of filled in from the pattern.


# Singleton
archidekt = ArchidektClient()
