"""Cardmarket import service (CSV and web scraping)."""
import csv
import io
import logging
import re
from typing import Any

from ..database import get_db
from ..clients.cardmarket import cardmarket_scraper

logger = logging.getLogger(__name__)

# New Cardmarket CSV stock export columns
NEW_FORMAT_HEADERS = {
    "Name", "Expansion", "Language", "Condition", "Price_EUR", "Amount",
}

# Legacy Cardmarket CSV columns
LEGACY_FORMAT_HEADERS = {
    "English Name", "Exp.", "Price", "Language", "Condition", "Amount",
}


def _clean_article_id(raw: str) -> str:
    """Clean the =\"...\" wrapper from ArticleID values."""
    # e.g. '="2038528487"' -> '2038528487'
    match = re.search(r'"?=?"?(\d+)"?', raw)
    return match.group(1) if match else raw.strip().strip('"')


async def import_cardmarket_csv(file_content: str | bytes) -> dict[str, Any]:
    """Parse and import a Cardmarket stock export CSV."""
    db = await get_db()

    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8-sig")

    # Detect format
    reader = csv.DictReader(io.StringIO(file_content), delimiter=";")
    headers = set(reader.fieldnames or [])

    is_new_format = NEW_FORMAT_HEADERS.issubset(headers)
    is_legacy_format = LEGACY_FORMAT_HEADERS.issubset(headers)

    if not is_new_format and not is_legacy_format:
        # Try comma delimiter
        alt_reader = csv.DictReader(io.StringIO(file_content), delimiter=",")
        alt_headers = set(alt_reader.fieldnames or [])
        if NEW_FORMAT_HEADERS.issubset(alt_headers):
            reader = alt_reader
            is_new_format = True
        elif LEGACY_FORMAT_HEADERS.issubset(alt_headers):
            reader = alt_reader
            is_legacy_format = True
        else:
            return {
                "total_rows": 0,
                "imported": 0,
                "errors": 1,
                "error_details": [
                    f"Unrecognized CSV format. Found columns: {headers}. "
                    f"Expected Cardmarket stock export columns."
                ],
            }

    # Clear previous imported entries (preserve manual ones)
    await db.execute("DELETE FROM cardmarket_listings WHERE source = 'import' OR source IS NULL")

    total = 0
    imported = 0
    error_details: list[str] = []

    for row in reader:
        total += 1
        try:
            if is_new_format:
                card_name = row.get("Name", "").strip()
                set_name = row.get("Expansion", "").strip()
                expansion_code = row.get("ExpansionCode", "").strip()
                rarity = row.get("Rarity", "").strip()
                language = row.get("Language", "").strip()
                condition = row.get("Condition", "").strip()
                condition_full = row.get("ConditionFull", "").strip()
                reverse_holo = row.get("ReverseHolo", "").strip().upper() in ("Y", "YES", "TRUE", "1")
                comments = row.get("Comments", "").strip()
                price_str = row.get("Price_EUR", "0").strip().replace(",", ".")
                amount = int(row.get("Amount", "1").strip() or "1")
                article_id = _clean_article_id(row.get("ArticleID", ""))
                product_url = row.get("ProductUrl", "").strip()
                is_foil = False  # Not in this CSV format directly
                set_code = ""
            else:
                # Legacy format
                card_name = row.get("English Name", "").strip()
                if not card_name:
                    card_name = row.get("Local Name", "").strip()
                set_code = row.get("Exp.", "").strip().lower()
                set_name = row.get("Exp. Name", "").strip()
                price_str = row.get("Price", "0").strip().replace(",", ".")
                language = row.get("Language", "").strip()
                condition = row.get("Condition", "").strip()
                is_foil = row.get("Foil?", "").strip().upper() in ("X", "YES", "TRUE", "1")
                amount = int(row.get("Amount", "1").strip() or "1")
                article_id = ""
                expansion_code = ""
                rarity = ""
                condition_full = ""
                reverse_holo = False
                comments = ""
                product_url = ""

            if not card_name:
                error_details.append(f"Row {total}: No card name")
                continue

            price = float(price_str) if price_str else 0

            # Try to link to existing card in DB
            card_id = None
            try:
                cursor = await db.execute(
                    "SELECT id FROM cards WHERE name=? LIMIT 1",
                    (card_name,),
                )
                card_row = await cursor.fetchone()
                if card_row:
                    card_id = card_row[0]
            except Exception:
                pass

            await db.execute(
                """INSERT INTO cardmarket_listings
                (card_name, set_name, set_code, quantity, price, condition,
                 language, is_foil, card_id, article_id, expansion_code,
                 rarity, condition_full, reverse_holo, comments, product_url, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'import')""",
                (card_name, set_name, set_code, amount, price, condition,
                 language, is_foil, card_id, article_id, expansion_code,
                 rarity, condition_full, reverse_holo, comments, product_url),
            )
            imported += 1

        except Exception as e:
            error_details.append(f"Row {total}: {e}")

    await db.commit()
    logger.info("Cardmarket CSV import: %d/%d imported, %d errors", imported, total, len(error_details))

    # Merge manual entries that now match imported ones (move to 'import' group)
    await db.execute(
        """UPDATE cardmarket_listings SET source = 'import'
        WHERE source = 'manual'
        AND card_name IN (SELECT card_name FROM cardmarket_listings WHERE source = 'import')"""
    )
    await db.commit()

    return {
        "total_rows": total,
        "imported": imported,
        "errors": len(error_details),
        "error_details": error_details[:50],
    }


async def sync_cardmarket_stock() -> dict[str, Any]:
    """Scrape the user's Cardmarket profile and import offer listings."""
    if not cardmarket_scraper.is_configured:
        return {"total_rows": 0, "imported": 0, "errors": 1,
                "error_details": ["Cardmarket username not configured in add-on settings."]}

    db = await get_db()

    try:
        articles = await cardmarket_scraper.scrape_offers()
    except Exception as e:
        logger.error("Cardmarket scraping failed: %s", e)
        return {"total_rows": 0, "imported": 0, "errors": 1,
                "error_details": [f"Scraping failed: {e}"]}

    if not articles:
        return {"total_rows": 0, "imported": 0, "errors": 0,
                "error_details": ["No listings found (page may be blocked by Cloudflare). Try CSV import."]}

    # Clear previous imported entries (preserve manual ones)
    await db.execute("DELETE FROM cardmarket_listings WHERE source = 'import' OR source IS NULL")

    imported = 0
    error_details: list[str] = []

    for art in articles:
        try:
            card_name = art.get("card_name", "").strip()
            if not card_name:
                continue

            set_name = art.get("set_name", "")
            set_code = art.get("set_code", "")
            price = art.get("price", 0)
            condition = art.get("condition", "")
            language = art.get("language", "en")
            is_foil = art.get("is_foil", False)
            quantity = art.get("quantity", 1)

            # Try to link to existing card in DB
            card_id = None
            try:
                cursor = await db.execute(
                    "SELECT id FROM cards WHERE name=? LIMIT 1",
                    (card_name,),
                )
                card_row = await cursor.fetchone()
                if card_row:
                    card_id = card_row[0]
            except Exception:
                pass

            await db.execute(
                """INSERT INTO cardmarket_listings
                (card_name, set_name, set_code, quantity, price, condition,
                 language, is_foil, card_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (card_name, set_name, set_code, quantity, price, condition,
                 language, is_foil, card_id),
            )
            imported += 1

        except Exception as e:
            error_details.append(f"Article '{art.get('card_name', '?')}': {e}")

    await db.commit()
    logger.info("Cardmarket scrape: %d/%d imported, %d errors", imported, len(articles), len(error_details))

    return {
        "total_rows": len(articles),
        "imported": imported,
        "errors": len(error_details),
        "error_details": error_details[:50],
    }
    logger.info("Cardmarket API sync: %d/%d imported, %d errors", imported, len(articles), len(error_details))

    return {
        "total_rows": len(articles),
        "imported": imported,
        "errors": len(error_details),
        "error_details": error_details[:50],
    }
