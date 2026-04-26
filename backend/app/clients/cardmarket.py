"""Cardmarket web scraper for user offer listings."""
import asyncio
import logging
import re
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from .flaresolverr import flaresolverr

logger = logging.getLogger(__name__)

CARDMARKET_BASE = "https://www.cardmarket.com"

# Browser-like headers to avoid Cloudflare basic protection
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class CardmarketScraper:
    """Scrapes a Cardmarket user's public offer listings."""

    def __init__(self, username: str = ""):
        self.username = username

    @property
    def is_configured(self) -> bool:
        return bool(self.username)

    async def scrape_offers(self) -> list[dict[str, Any]]:
        """Fetch and parse all pages of the user's singles offers."""
        if not self.username:
            return []

        all_listings: list[dict[str, Any]] = []
        page = 1

        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=30.0, follow_redirects=True
        ) as client:
            while True:
                url = f"{CARDMARKET_BASE}/en/Magic/Users/{self.username}/Offers/Singles"
                params = {}
                if page > 1:
                    params["page"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 403:
                        logger.warning(
                            "Cardmarket returned 403 (Cloudflare?) on page %d.",
                            page,
                        )
                        # Try FlareSolverr fallback
                        if flaresolverr.is_configured:
                            logger.info("Attempting FlareSolverr bypass for Cardmarket...")
                            return await self._scrape_via_flaresolverr()
                        logger.warning("FlareSolverr not configured. Try CSV import as fallback.")
                        break
                    if resp.status_code != 200:
                        logger.warning(
                            "Cardmarket page %d returned status %d", page, resp.status_code
                        )
                        break
                except httpx.HTTPError as e:
                    logger.error("Failed to fetch Cardmarket page %d: %s", page, e)
                    break

                listings = _parse_offers_page(resp.text)
                if not listings:
                    break

                all_listings.extend(listings)
                logger.info("Scraped %d listings from page %d", len(listings), page)

                # Check for next page
                if f"page={page + 1}" not in resp.text and not re.search(
                    rf'[?&]page={page + 1}["\s&]', resp.text
                ):
                    break

                page += 1
                await asyncio.sleep(1.5)  # Rate limiting

        logger.info("Total Cardmarket listings scraped: %d", len(all_listings))
        return all_listings

    async def _scrape_via_flaresolverr(self) -> list[dict[str, Any]]:
        """Scrape Cardmarket offers using FlareSolverr to bypass Cloudflare."""
        all_listings: list[dict[str, Any]] = []
        session_id = None

        try:
            session_id = await flaresolverr.create_session()

            # Fetch first page via FlareSolverr to get cookies
            base_url = f"{CARDMARKET_BASE}/en/Magic/Users/{self.username}/Offers/Singles"
            result = await flaresolverr.get_page(base_url, session=session_id)

            if result["status"] != 200:
                logger.error(
                    "FlareSolverr returned status %d for Cardmarket", result["status"]
                )
                return []

            # Parse first page
            listings = _parse_offers_page(result["html"])
            if listings:
                all_listings.extend(listings)
                logger.info(
                    "FlareSolverr: scraped %d listings from page 1", len(listings)
                )

            # Extract cookies and user-agent for subsequent pages via httpx
            cookies_dict = {}
            for c in result.get("cookies", []):
                if c.get("name") and c.get("value"):
                    cookies_dict[c["name"]] = c["value"]
            user_agent = result.get("user_agent", _HEADERS["User-Agent"])

            # Use cookies for remaining pages with httpx (faster than FlareSolverr per page)
            headers = {**_HEADERS, "User-Agent": user_agent}
            page = 2
            async with httpx.AsyncClient(
                headers=headers, cookies=cookies_dict,
                timeout=30.0, follow_redirects=True,
            ) as client:
                while True:
                    # Check if there's a next page link in previous HTML
                    prev_html = result["html"] if page == 2 else resp_text
                    if f"page={page}" not in prev_html and not re.search(
                        rf'[?&]page={page}["\s&]', prev_html
                    ):
                        break

                    await asyncio.sleep(1.5)

                    try:
                        resp = await client.get(base_url, params={"page": str(page)})
                        if resp.status_code == 403:
                            # Cookies expired, fall back to FlareSolverr for this page
                            logger.info(
                                "Cookie-based request got 403 on page %d, "
                                "using FlareSolverr directly", page
                            )
                            result2 = await flaresolverr.get_page(
                                f"{base_url}?page={page}", session=session_id
                            )
                            resp_text = result2["html"]
                        elif resp.status_code != 200:
                            logger.warning(
                                "Cardmarket page %d returned status %d",
                                page, resp.status_code,
                            )
                            break
                        else:
                            resp_text = resp.text
                    except httpx.HTTPError as e:
                        logger.error("Failed to fetch page %d: %s", page, e)
                        break

                    listings = _parse_offers_page(resp_text)
                    if not listings:
                        break

                    all_listings.extend(listings)
                    logger.info(
                        "FlareSolverr+cookies: scraped %d listings from page %d",
                        len(listings), page,
                    )
                    page += 1

        except Exception as e:
            logger.error("FlareSolverr scraping failed: %s", e)
        finally:
            if session_id:
                await flaresolverr.destroy_session(session_id)

        logger.info(
            "Total Cardmarket listings via FlareSolverr: %d", len(all_listings)
        )
        return all_listings


def _parse_offers_page(html: str) -> list[dict[str, Any]]:
    """Parse a single offers page and extract listing data using selectolax."""
    listings: list[dict[str, Any]] = []
    tree = HTMLParser(html)

    # Cardmarket article rows: <div class="row no-gutters article-row">
    rows = tree.css("div.article-row") or tree.css("tr.article-row")
    if not rows:
        # Fallback: find any row containing a product link
        rows = [
            node.parent
            for node in tree.css('a[href*="/en/Magic/Products/Singles/"]')
            if node.parent is not None
        ]

    for row in rows:
        # Product link
        link = row.css_first('a[href*="/en/Magic/Products/Singles/"]')
        if not link:
            continue
        card_name = link.text(strip=True)
        if not card_name or len(card_name) > 200:
            continue

        # Expansion
        exp_link = row.css_first('a[href*="/en/Magic/Expansions/"]')
        expansion = exp_link.text(strip=True) if exp_link else ""

        # Condition  (abbr or span with condition class, or data attribute)
        condition = ""
        cond_node = row.css_first("[data-original-title]") or row.css_first(
            "a.article-condition, span.article-condition, abbr"
        )
        if cond_node:
            cond_text = (
                cond_node.attributes.get("data-original-title", "")
                or cond_node.text(strip=True)
            )
            m = re.search(r"\b(MT|NM|EX|GD|LP|PL|PO)\b", cond_text, re.I)
            if m:
                condition = m.group(1).upper()

        # Price
        price = 0.0
        price_node = row.css_first("span.price-container span, span.font-weight-bold")
        if price_node:
            price_m = re.search(
                r"(\d+(?:\.\d{3})*,\d{2})", price_node.text(strip=True)
            )
            if price_m:
                price = float(price_m.group(1).replace(".", "").replace(",", "."))

        # Quantity
        quantity = 1
        qty_node = row.css_first("[data-quantity]") or row.css_first(
            "span.amount-container, span.item-count"
        )
        if qty_node:
            qty_val = qty_node.attributes.get("data-quantity", "") or qty_node.text(strip=True)
            qty_m = re.search(r"(\d+)", qty_val)
            if qty_m:
                quantity = int(qty_m.group(1))

        # Foil
        is_foil = bool(row.css_first("[data-is-foil], .icon-foil, .foil"))

        # Rarity
        rarity = ""
        rarity_node = row.css_first("img[alt]")
        if rarity_node:
            alt = rarity_node.attributes.get("alt", "")
            if alt in ("Common", "Uncommon", "Rare", "Mythic", "Special", "Time Shifted"):
                rarity = alt

        listings.append({
            "card_name": card_name,
            "set_name": expansion,
            "set_code": "",
            "condition": condition,
            "price": price,
            "quantity": quantity,
            "is_foil": is_foil,
            "language": "en",
            "rarity": rarity,
        })

    return listings


# Singleton
cardmarket_scraper = CardmarketScraper()
