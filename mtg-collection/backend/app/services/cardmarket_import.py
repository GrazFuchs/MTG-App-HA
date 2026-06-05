"""Cardmarket import service (CSV import only)."""
import csv
import io
import logging
import re
from typing import Any

from ..database import get_db

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
        logger.info("Cardmarket CSV import: received %d bytes", len(file_content))
        file_content = file_content.decode("utf-8-sig")
    else:
        logger.info("Cardmarket CSV import: received %d chars (string)", len(file_content))

    if not file_content or not file_content.strip():
        logger.error("Cardmarket CSV import: file content is empty")
        return {
            "total_rows": 0,
            "imported": 0,
            "errors": 1,
            "error_details": ["File is empty. Please select a valid Cardmarket CSV export."],
        }

    # Detect format — strip whitespace from header names for resilience
    reader = csv.DictReader(io.StringIO(file_content), delimiter=";")
    raw_fieldnames = reader.fieldnames or []
    # Normalize: strip whitespace from fieldnames (Cardmarket sometimes adds trailing spaces)
    clean_fieldnames = [h.strip() for h in raw_fieldnames]
    reader.fieldnames = clean_fieldnames
    headers = {h for h in clean_fieldnames if h}
    logger.info("Cardmarket CSV import: detected %d columns: %s", len(headers), sorted(headers))

    is_new_format = NEW_FORMAT_HEADERS.issubset(headers)
    is_legacy_format = LEGACY_FORMAT_HEADERS.issubset(headers)

    if not is_new_format and not is_legacy_format:
        # Try comma delimiter
        alt_reader = csv.DictReader(io.StringIO(file_content), delimiter=",")
        alt_fieldnames = [h.strip() for h in (alt_reader.fieldnames or [])]
        alt_reader.fieldnames = alt_fieldnames
        alt_headers = {h for h in alt_fieldnames if h}
        if NEW_FORMAT_HEADERS.issubset(alt_headers):
            reader = alt_reader
            is_new_format = True
        elif LEGACY_FORMAT_HEADERS.issubset(alt_headers):
            reader = alt_reader
            is_legacy_format = True
        else:
            msg = (
                f"Unrecognized CSV format. Found columns: {sorted(headers)}. "
                f"Expected columns (new): {sorted(NEW_FORMAT_HEADERS)} or "
                f"(legacy): {sorted(LEGACY_FORMAT_HEADERS)}"
            )
            logger.error("Cardmarket CSV import failed: %s", msg)
            return {
                "total_rows": 0,
                "imported": 0,
                "errors": 1,
                "error_details": [msg],
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
