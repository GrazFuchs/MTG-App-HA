"""Fill the card facts only Scryfall has.

Almost every card row in this database was assembled from an Archidekt payload,
because that is where decks and the collection come from. Archidekt is a good
source for what is *owned* and *played*, and a partial one for what a card *is*:
it reports no format legalities (the parser writes the literal `"{}"`), nothing
about the Reserved List, and nothing about the WotC Game Changers list. Those
three are fields on the Scryfall card object.

So this module tops the rows up from Scryfall — `POST /cards/collection`, 75
printings per request, keyed by `scryfall_id`, which is printing-exact. It runs
after every sync and can be triggered by hand from
`POST /api/cards/backfill-scryfall`.

Two rules shape the write:

* **Never trade a known value for an empty one.** A card is touched by both
  sources over its life, and whichever wrote last used to win. Here Scryfall
  fills holes (`oracle_text`, `cmc`, `mana_cost`) and owns what only it knows
  (`legalities`, `keywords`, `game_changer`, `reserved`); a field Scryfall does
  not answer for leaves the stored value alone.
* **A card is asked once, then left alone for a week.** `scryfall_enriched_at`
  is the stamp; without it a nightly run would re-crawl all ten thousand cards.
  The week is not idle patience either: WotC edits the Game Changers list (last
  on 2026-02-09), EDHREC ranks drift, and an Archidekt sync of the same card
  overwrites `keywords` with its own thinner reading, so the refresh is what
  makes those self-correcting rather than frozen at first contact.
"""
import asyncio
import json
import logging
from typing import Any

import httpx

from ..database import get_db

logger = logging.getLogger(__name__)

# Scryfall caps POST /cards/collection at 75 identifiers per request.
_CHUNK = 75

# Scryfall documents 10 requests/second in general but **2/second** for
# `/collection`, `/search` and `/named`. The shared client paces every request
# at 100 ms, which is the general limit, so the stricter one is honoured here.
_CHUNK_PACING = 0.5

# `cardmarket_id = 0` means "Scryfall has no Cardmarket product for this
# printing" (tokens, some promos) as opposed to NULL, "never asked" — the same
# sentinel `cardmarket_prices.backfill_cardmarket_ids()` uses.
_NO_CARDMARKET_PRODUCT = 0

# How long an answer is considered current. Also the bound on the nightly cost:
# a tenth of the collection comes up for refresh each night, not all of it.
REFRESH_AFTER_DAYS = 7

# Cap for the pass that runs inside a sync, so a first run on a large
# collection cannot stretch the sync unpredictably. The backlog then converges
# over a few nights; `POST /api/cards/backfill-scryfall` does it in one go.
POST_SYNC_MAX_CARDS = 3000

_PENDING_WHERE = f"""
    COALESCE(scryfall_id, '') != ''
    AND (
        scryfall_enriched_at IS NULL
        OR scryfall_enriched_at < datetime('now', '-{REFRESH_AFTER_DAYS} days')
    )
"""

_UPDATE_SQL = """
    UPDATE cards SET
        game_changer = ?,
        reserved = ?,
        legalities = COALESCE(?, legalities),
        keywords = COALESCE(?, keywords),
        edhrec_rank = COALESCE(?, edhrec_rank),
        cardmarket_id = ?,
        layout = COALESCE(?, layout),
        type_line = COALESCE(?, type_line),
        oracle_text = CASE WHEN COALESCE(oracle_text, '') = ''
                           THEN COALESCE(?, oracle_text) ELSE oracle_text END,
        cmc = CASE WHEN COALESCE(cmc, 0) = 0
                   THEN COALESCE(?, cmc) ELSE cmc END,
        mana_cost = CASE WHEN COALESCE(mana_cost, '') = ''
                         THEN COALESCE(?, mana_cost) ELSE mana_cost END,
        scryfall_enriched_at = CURRENT_TIMESTAMP
    WHERE id = ?
"""


async def pending_count() -> int:
    """How many printings are waiting for (or due) an enrichment pass."""
    db = await get_db()
    cursor = await db.execute(f"SELECT COUNT(*) FROM cards WHERE {_PENDING_WHERE}")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


def _update_params(card: dict[str, Any], card_id: int) -> tuple:
    """Map one Scryfall card object onto the parameters of `_UPDATE_SQL`.

    `None` is the "leave the stored value alone" marker throughout, which is why
    every optional field is normalised to None rather than to an empty string:
    the SQL wraps them in COALESCE.
    """
    legalities = card.get("legalities")
    keywords = card.get("keywords")
    type_line = card.get("type_line") or None
    # Absent on double-faced cards, where the text lives in `card_faces`. Left
    # to the stored Archidekt value rather than flattened here — a joined text
    # would read as one card's rules and Sprint 04 classifies on this field.
    oracle_text = card.get("oracle_text") or None
    cmc = card.get("cmc")
    return (
        int(bool(card.get("game_changer"))),
        int(bool(card.get("reserved"))),
        json.dumps(legalities) if legalities else None,
        json.dumps(keywords) if keywords is not None else None,
        card.get("edhrec_rank"),
        card.get("cardmarket_id") or _NO_CARDMARKET_PRODUCT,
        card.get("layout") or None,
        type_line,
        oracle_text,
        cmc if cmc else None,
        card.get("mana_cost") or None,
        card_id,
    )


async def backfill_scryfall_fields(
    max_cards: int | None = None, force: bool = False
) -> dict[str, Any]:
    """Enrich pending printings from Scryfall and stamp them.

    `force` ignores the stamp and re-asks, oldest answer first — for when the
    Game Changers list has changed and the whole collection should be re-read
    rather than only the tenth that is due.
    """
    from ..clients.scryfall import scryfall

    db = await get_db()
    where = "COALESCE(scryfall_id, '') != ''" if force else _PENDING_WHERE
    cursor = await db.execute(
        f"""SELECT id, scryfall_id FROM cards
        WHERE {where}
        ORDER BY COALESCE(scryfall_enriched_at, ''), id"""
        + (" LIMIT ?" if max_cards else ""),
        (max_cards,) if max_cards else (),
    )
    pending = await cursor.fetchall()
    if not pending:
        return {
            "status": "completed",
            "checked": 0,
            "enriched": 0,
            "unresolved": 0,
            "game_changers": 0,
        }

    # One card row per Scryfall id: the column is UNIQUE, so this cannot lose a
    # row, and it gives the lookup from a response back to the row it answers.
    by_scryfall_id = {row[1]: row[0] for row in pending}
    identifiers = [{"id": sid} for sid in by_scryfall_id]
    logger.info("Scryfall enrichment: %d printings to ask about", len(identifiers))

    status = "completed"
    enriched = 0
    unresolved = 0
    game_changers = 0

    for i in range(0, len(identifiers), _CHUNK):
        chunk = identifiers[i:i + _CHUNK]
        if i:
            await asyncio.sleep(_CHUNK_PACING)
        try:
            cards, _not_found = await scryfall.get_cards_collection(chunk)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                # Stop rather than hammer on. The stamps written so far hold, so
                # the next run picks up where this one left off.
                logger.warning(
                    "Scryfall answered 429; stopping enrichment after %d printings",
                    enriched + unresolved,
                )
                status = "rate_limited"
            else:
                logger.exception("Scryfall lookup failed, stopping enrichment early")
                status = "failed"
            break
        except Exception:
            logger.exception("Scryfall lookup failed, stopping enrichment early")
            status = "failed"
            break

        resolved: set[str] = set()
        for card in cards:
            scryfall_id = card.get("id")
            card_id = by_scryfall_id.get(scryfall_id)
            if card_id is None:
                continue
            resolved.add(scryfall_id)
            await db.execute(_UPDATE_SQL, _update_params(card, card_id))
            enriched += 1
            if card.get("game_changer"):
                game_changers += 1

        # A printing Scryfall does not know is stamped as asked but keeps NULL
        # flags. Writing 0 would be an invented answer, and `game_changer = 1`
        # is about to decide a bracket.
        for identifier in chunk:
            scryfall_id = identifier["id"]
            if scryfall_id not in resolved:
                await db.execute(
                    "UPDATE cards SET scryfall_enriched_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (by_scryfall_id[scryfall_id],),
                )
                unresolved += 1

        await db.commit()

    logger.info(
        "Scryfall enrichment %s: %d enriched, %d unresolved, %d game changers",
        status,
        enriched,
        unresolved,
        game_changers,
    )
    return {
        "status": status,
        "checked": len(identifiers),
        "enriched": enriched,
        "unresolved": unresolved,
        "game_changers": game_changers,
    }
