"""MTGStocks client (unofficial API).

MTGStocks has no official/public API. The endpoints below are the ones the
mtgstocks.com web frontend itself calls. They sit behind Cloudflare/API-Gateway
and reject plain requests (HTTP 403), so a browser-like ``User-Agent`` + ``Origin``
header set is required. Everything here degrades gracefully: any error or non-200
returns ``None`` and logs a warning (same philosophy as the EDHREC client) so a
flaky/blocked upstream never breaks a sync.

Endpoints (reverse-engineered, verified live 2026-06):
  GET /search/autocomplete/{query}
        -> [{"id", "type": "print", "name", "slug"}]   (one canonical print per name)
  GET /prints/{id}
        -> {id, slug, name, collector_number, scryfallId,
            card_set: {abbreviation, name, ...},
            all_time_high: {avg, date(ms)}, all_time_low: {avg, date(ms)},
            tcgplayer: {latestPrice: {low, avg, high, market, foil, marketFoil, ...}},
            cardmarket: {latestPrice: {low, avg, foil}},
            sets: [{id, abbreviation, collector_number, set_name, latest_price,
                    latest_price_mkm, ...}]}   (every printing of the card)
  GET /prints/{id}/prices
        -> {"low": [[ts_ms, price], ...], "avg": [...], "market": [...], ...}
  GET /interests/{average|market}/{regular|foil}
        -> {"date": "YYYY-MM-DD",
            "interests": [{foil, percentage, interest_type, present_price, past_price,
                           print: {id, name, set_code, set_name, number, ...}}]}
"""
import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MTGSTOCKS_BASE = "https://api.mtgstocks.com"
# A browser-like header set is mandatory; plain clients get a Cloudflare 403.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.mtgstocks.com",
    "Referer": "https://www.mtgstocks.com/",
}
RATE_LIMIT_DELAY = 1.0  # ~1 request/second — be polite to an unofficial source
CACHE_TTL = 86400  # 24 hours


class MTGStocksClient:
    def __init__(self):
        self._last_request = 0.0
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=MTGSTOCKS_BASE,
                headers=HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def _rate_limit(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < CACHE_TTL:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any):
        self._cache[key] = (time.time(), data)

    async def _get(self, path: str, *, cache: bool = True) -> Any | None:
        if cache:
            cached = self._get_cached(path)
            if cached is not None:
                return cached
        try:
            await self._rate_limit()
            client = await self._get_client()
            resp = await client.get(path)
            if resp.status_code == 200:
                data = resp.json()
                if cache:
                    self._set_cached(path, data)
                return data
            logger.warning("MTGStocks returned %d for %s", resp.status_code, path)
        except Exception as e:
            logger.warning("MTGStocks request failed for %s: %s", path, e)
        return None

    async def search(self, name: str) -> list[dict[str, Any]] | None:
        """Autocomplete search; returns one canonical print per matching card name."""
        if not name:
            return None
        data = await self._get(f"/search/autocomplete/{name}")
        return data if isinstance(data, list) else None

    async def get_print(self, print_id: int) -> dict[str, Any] | None:
        """Full print detail incl. scryfallId, all-time high/low, latest prices, sets[]."""
        data = await self._get(f"/prints/{print_id}")
        return data if isinstance(data, dict) else None

    async def get_price_history(self, print_id: int) -> dict[str, Any] | None:
        """Full multi-year price series per category ([[ts_ms, price], ...])."""
        data = await self._get(f"/prints/{print_id}/prices")
        return data if isinstance(data, dict) else None

    async def get_interests(self, kind: str, foil: bool) -> dict[str, Any] | None:
        """Market movers. kind in {"average", "market"}; foil selects the foil board.

        Not cached — this is daily-changing data fetched once per sync.
        """
        if kind not in ("average", "market"):
            raise ValueError(f"kind must be 'average' or 'market', got {kind!r}")
        board = "foil" if foil else "regular"
        data = await self._get(f"/interests/{kind}/{board}", cache=False)
        return data if isinstance(data, dict) else None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _ms_to_date(ms: Any) -> str | None:
    """Convert a MTGStocks epoch-millis timestamp to an ISO date string."""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError):
        return None


def _f(value: Any) -> float | None:
    """Coerce a price-ish value to float, or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_print_detail(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a /prints/{id} payload into the fields we persist."""
    ath = data.get("all_time_high") or {}
    atl = data.get("all_time_low") or {}
    tcg = (data.get("tcgplayer") or {}).get("latestPrice") or {}
    cm = (data.get("cardmarket") or {}).get("latestPrice") or {}
    card_set = data.get("card_set") or {}
    return {
        "mtgstocks_print_id": data.get("id"),
        "scryfall_id": data.get("scryfallId") or "",
        "name": data.get("name") or "",
        "set_name": card_set.get("name") or "",
        "set_abbreviation": (card_set.get("abbreviation") or "").upper(),
        "collector_number": str(data.get("collector_number") or ""),
        "all_time_high": _f(ath.get("avg")),
        "all_time_high_date": _ms_to_date(ath.get("date")),
        "all_time_low": _f(atl.get("avg")),
        "all_time_low_date": _ms_to_date(atl.get("date")),
        # Latest spot prices (TCGplayer USD first, Cardmarket EUR as the EUR series)
        "market": _f(tcg.get("market")) if _f(tcg.get("market")) is not None else _f(tcg.get("avg")),
        "avg": _f(tcg.get("avg")),
        "low": _f(tcg.get("low")),
        "market_foil": _f(tcg.get("marketFoil")) if _f(tcg.get("marketFoil")) is not None else _f(tcg.get("foil")),
        "low_foil": _f(tcg.get("lowFoil")),
        "mkm_avg": _f(cm.get("avg")),
        "mkm_low": _f(cm.get("low")),
        "mkm_foil": _f(cm.get("foil")),
        "sets": data.get("sets") or [],
    }


def find_printing(detail: dict[str, Any], set_code: str, collector_number: str) -> dict[str, Any] | None:
    """Pick the printing matching set_code (+ collector number) from a print's sets[].

    Returns the raw ``sets`` entry (which carries its own MTGStocks print ``id``),
    or ``None`` if no plausible match is found.
    """
    sets = detail.get("sets") or []
    if not sets:
        return None
    want_set = (set_code or "").upper()
    want_num = str(collector_number or "").strip()

    if want_set:
        # Best: same set AND same collector number.
        for s in sets:
            if (s.get("abbreviation") or "").upper() == want_set and \
               str(s.get("collector_number") or "").strip() == want_num:
                return s
        # Next: same set, any collector number.
        for s in sets:
            if (s.get("abbreviation") or "").upper() == want_set:
                return s
    return None


def parse_interest(item: dict[str, Any], kind: str) -> dict[str, Any] | None:
    """Normalize one interests entry. Returns None if it has no usable print."""
    pr = item.get("print") or {}
    pid = pr.get("id")
    if pid is None:
        return None
    return {
        "mtgstocks_print_id": pid,
        "card_name": pr.get("name") or "",
        "set_code": (pr.get("set_code") or "").upper(),
        "set_name": pr.get("set_name") or "",
        "collector_number": str(pr.get("number") or ""),
        "kind": kind,
        "is_foil": 1 if item.get("foil") else 0,
        "interest_type": item.get("interest_type") or "",
        "percentage": _f(item.get("percentage")),
        "present_price": _f(item.get("present_price")),
        "past_price": _f(item.get("past_price")),
    }


# Singleton
mtgstocks = MTGStocksClient()
