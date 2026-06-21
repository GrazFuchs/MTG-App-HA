"""MTGStocks price/movers sync and queries.

Three sync stages (run daily, see scheduler):
  1. sync_mtgstocks_prints   – resolve owned/wishlist cards -> MTGStocks print id
                               (persisted once per card), capturing all-time high/low.
  2. sync_mtgstocks_prices   – refresh latest prices + all-time high/low for mapped
                               prints and append a daily snapshot row.
  3. sync_mtgstocks_interests – pull market movers, keep only those that match a
                               card we own or wishlist.

All prices from MTGStocks are TCGplayer USD (the EUR series stays Cardmarket's job).
Everything degrades gracefully — the client returns None on any upstream failure.
"""
import logging
from datetime import date
from typing import Any

from ..database import get_db
from ..clients.mtgstocks import (
    mtgstocks,
    parse_print_detail,
    parse_interest,
    find_printing,
)

logger = logging.getLogger(__name__)

# Cap new-mapping resolutions per run so a first-time backfill of a large
# collection spreads over several days instead of hammering the source.
MAX_NEW_PRINTS_PER_SYNC = 250
# Buy/sell signal thresholds (fraction away from the all-time extreme).
NEAR_ATL_PCT = 0.15  # current price within +15% of all-time low  -> buy
NEAR_ATH_PCT = 0.15  # current price within -15% of all-time high -> sell


async def _owned_wishlist_card_rows(db) -> list:
    """Cards that are owned or actively wishlisted (with identity fields)."""
    cursor = await db.execute(
        """SELECT c.id, c.name, c.set_code, c.collector_number, c.scryfall_id
        FROM cards c
        WHERE c.id IN (SELECT card_id FROM collection)
           OR c.id IN (
               SELECT card_id FROM wishlist
               WHERE removed_at IS NULL AND status = 'wanted' AND card_id IS NOT NULL
           )"""
    )
    return await cursor.fetchall()


async def _resolve_card(name: str, set_code: str, collector_number: str) -> dict[str, Any] | None:
    """Resolve a card to the MTGStocks print matching its set/printing.

    Strategy: autocomplete -> canonical print id -> fetch detail (has every
    printing in ``sets``) -> pick the printing matching our set+collector number,
    refetching that print's detail for its own all-time high/low.
    """
    results = await mtgstocks.search(name)
    if not results:
        return None

    target = name.lower()
    canonical = next((r for r in results if (r.get("name") or "").lower() == target), None)
    if canonical is None and " // " in name:
        # Double-faced card: MTGStocks indexes the front face.
        front = name.split(" // ")[0].lower()
        canonical = next((r for r in results if (r.get("name") or "").lower() == front), None)
    if canonical is None or canonical.get("id") is None:
        return None

    canonical_id = canonical["id"]
    detail = await mtgstocks.get_print(canonical_id)
    if not detail:
        return None
    parsed = parse_print_detail(detail)

    matched = find_printing(detail, set_code, collector_number)
    if matched and matched.get("id") and matched["id"] != canonical_id:
        md = await mtgstocks.get_print(matched["id"])
        if md:
            parsed = parse_print_detail(md)
    return parsed


async def _upsert_print_mapping(db, card_id: int, parsed: dict[str, Any]) -> None:
    """Insert/refresh a mtgstocks_prints row from a parsed print detail."""
    await db.execute(
        """INSERT INTO mtgstocks_prints
        (mtgstocks_print_id, card_id, card_name, set_name,
         all_time_high, all_time_high_date, all_time_low, all_time_low_date,
         market, avg, low, market_foil, low_foil, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(mtgstocks_print_id) DO UPDATE SET
            card_id=COALESCE(excluded.card_id, mtgstocks_prints.card_id),
            card_name=excluded.card_name, set_name=excluded.set_name,
            all_time_high=excluded.all_time_high, all_time_high_date=excluded.all_time_high_date,
            all_time_low=excluded.all_time_low, all_time_low_date=excluded.all_time_low_date,
            market=excluded.market, avg=excluded.avg, low=excluded.low,
            market_foil=excluded.market_foil, low_foil=excluded.low_foil,
            updated_at=CURRENT_TIMESTAMP""",
        (
            parsed["mtgstocks_print_id"], card_id, parsed["name"], parsed["set_name"],
            parsed["all_time_high"], parsed["all_time_high_date"],
            parsed["all_time_low"], parsed["all_time_low_date"],
            parsed["market"], parsed["avg"], parsed["low"],
            parsed["market_foil"], parsed["low_foil"],
        ),
    )


async def sync_mtgstocks_prints() -> dict[str, Any]:
    """Resolve MTGStocks print ids for owned/wishlist cards lacking a mapping."""
    db = await get_db()
    cards = await _owned_wishlist_card_rows(db)
    if not cards:
        return {"status": "skipped", "reason": "no owned/wishlist cards", "resolved": 0}

    mapped_cursor = await db.execute(
        "SELECT card_id FROM mtgstocks_prints WHERE card_id IS NOT NULL"
    )
    mapped_ids = {r[0] for r in await mapped_cursor.fetchall()}

    todo = [c for c in cards if c["id"] not in mapped_ids]
    logger.info("MTGStocks print mapping: %d owned/wishlist cards, %d unmapped",
                len(cards), len(todo))

    resolved = 0
    failed = 0
    for card in todo[:MAX_NEW_PRINTS_PER_SYNC]:
        try:
            parsed = await _resolve_card(
                card["name"], card["set_code"] or "", card["collector_number"] or ""
            )
        except Exception as e:
            logger.warning("MTGStocks resolve failed for %s: %s", card["name"], e)
            parsed = None
        if not parsed or not parsed.get("mtgstocks_print_id"):
            failed += 1
            continue
        await _upsert_print_mapping(db, card["id"], parsed)
        resolved += 1

    await db.commit()
    remaining = max(0, len(todo) - MAX_NEW_PRINTS_PER_SYNC)
    logger.info("MTGStocks print mapping: resolved=%d failed=%d remaining=%d",
                resolved, failed, remaining)
    return {"status": "completed", "resolved": resolved, "failed": failed, "remaining": remaining}


async def sync_mtgstocks_prices() -> dict[str, Any]:
    """Refresh latest prices + all-time extremes for mapped prints and snapshot today."""
    db = await get_db()
    today = date.today().isoformat()

    cursor = await db.execute(
        "SELECT mtgstocks_print_id, card_id FROM mtgstocks_prints"
    )
    rows = await cursor.fetchall()
    if not rows:
        return {"status": "skipped", "reason": "no mapped prints", "snapshots": 0}

    snapshots = 0
    for r in rows:
        pid = r["mtgstocks_print_id"]
        detail = await mtgstocks.get_print(pid)
        if not detail:
            continue
        parsed = parse_print_detail(detail)
        await _upsert_print_mapping(db, r["card_id"], parsed)
        await db.execute(
            """INSERT INTO mtgstocks_price_history
            (mtgstocks_print_id, date, market, avg, low, market_foil, low_foil)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mtgstocks_print_id, date) DO UPDATE SET
                market=excluded.market, avg=excluded.avg, low=excluded.low,
                market_foil=excluded.market_foil, low_foil=excluded.low_foil""",
            (pid, today, parsed["market"], parsed["avg"], parsed["low"],
             parsed["market_foil"], parsed["low_foil"]),
        )
        snapshots += 1

    await db.commit()
    logger.info("MTGStocks price snapshot: %d prints stored for %s", snapshots, today)
    return {"status": "completed", "snapshots": snapshots}


async def sync_mtgstocks_interests() -> dict[str, Any]:
    """Pull the four interests boards, keep only movers matching owned/wishlist cards."""
    db = await get_db()

    # Build lookup tables of cards we care about.
    cards = await _owned_wishlist_card_rows(db)
    if not cards:
        return {"status": "skipped", "reason": "no owned/wishlist cards", "stored": 0}
    by_name_set: dict[tuple[str, str], int] = {}
    by_name: dict[str, int] = {}
    for c in cards:
        key = (c["name"].lower(), (c["set_code"] or "").upper())
        by_name_set.setdefault(key, c["id"])
        by_name.setdefault(c["name"].lower(), c["id"])

    map_cursor = await db.execute(
        "SELECT mtgstocks_print_id, card_id FROM mtgstocks_prints WHERE card_id IS NOT NULL"
    )
    print_to_card = {r[0]: r[1] for r in await map_cursor.fetchall()}

    def _match(item: dict[str, Any]) -> int | None:
        cid = print_to_card.get(item["mtgstocks_print_id"])
        if cid is not None:
            return cid
        cid = by_name_set.get((item["card_name"].lower(), item["set_code"]))
        if cid is not None:
            return cid
        return by_name.get(item["card_name"].lower())

    stored = 0
    snapshot_date = None
    for kind in ("average", "market"):
        for foil in (False, True):
            data = await mtgstocks.get_interests(kind, foil)
            if not data:
                continue
            snapshot_date = data.get("date") or snapshot_date or date.today().isoformat()
            for raw in data.get("interests", []):
                item = parse_interest(raw, kind)
                if not item:
                    continue
                card_id = _match(item)
                if card_id is None:
                    continue
                await db.execute(
                    """INSERT INTO mtgstocks_interests
                    (date, mtgstocks_print_id, card_id, card_name, set_name, set_code,
                     kind, is_foil, interest_type, percentage, present_price, past_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, mtgstocks_print_id, kind, is_foil) DO UPDATE SET
                        card_id=excluded.card_id, percentage=excluded.percentage,
                        present_price=excluded.present_price, past_price=excluded.past_price,
                        interest_type=excluded.interest_type""",
                    (snapshot_date, item["mtgstocks_print_id"], card_id, item["card_name"],
                     item["set_name"], item["set_code"], kind, item["is_foil"],
                     item["interest_type"], item["percentage"],
                     item["present_price"], item["past_price"]),
                )
                stored += 1

    await db.commit()
    logger.info("MTGStocks interests: %d matched movers stored for %s", stored, snapshot_date)
    return {"status": "completed", "stored": stored, "date": snapshot_date}


# ---------------------------------------------------------------------------
# Queries (read paths used by the router)
# ---------------------------------------------------------------------------

async def get_long_term_history(card_id: int, days: int = 365) -> dict[str, Any]:
    """Fetch the full MTGStocks price series for a card, filtered to a window.

    Served live from MTGStocks (cached 24h in the client) rather than stored,
    since the series spans years (thousands of points per print).
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT mtgstocks_print_id, all_time_high, all_time_high_date,
                  all_time_low, all_time_low_date
        FROM mtgstocks_prints WHERE card_id = ? LIMIT 1""",
        (card_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return {"series": [], "all_time_high": None, "all_time_low": None, "currency": "USD"}

    pid = row["mtgstocks_print_id"]
    data = await mtgstocks.get_price_history(pid)
    series: list[dict[str, Any]] = []
    if data:
        from datetime import datetime, timezone, timedelta
        cutoff_ms = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000
        merged: dict[int, dict[str, Any]] = {}
        for key in ("market", "avg", "low", "market_foil"):
            for point in data.get(key, []) or []:
                try:
                    ts, price = point[0], point[1]
                except (IndexError, TypeError):
                    continue
                if ts < cutoff_ms:
                    continue
                bucket = merged.setdefault(ts, {})
                bucket[key] = price
        for ts in sorted(merged):
            d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
            series.append({"date": d, **merged[ts]})

    return {
        "series": series,
        "all_time_high": row["all_time_high"],
        "all_time_high_date": row["all_time_high_date"],
        "all_time_low": row["all_time_low"],
        "all_time_low_date": row["all_time_low_date"],
        "currency": "USD",
    }


async def get_collection_movers(limit: int = 40) -> list[dict[str, Any]]:
    """Latest market movers among cards the user owns (deduped per card)."""
    db = await get_db()
    cursor = await db.execute("SELECT MAX(date) FROM mtgstocks_interests")
    row = await cursor.fetchone()
    latest = row[0] if row else None
    if not latest:
        return []

    cursor = await db.execute(
        """SELECT i.card_id, i.card_name, i.set_name, i.set_code, i.kind, i.is_foil,
                  i.interest_type, i.percentage, i.present_price, i.past_price,
                  c.set_code AS owned_set_code,
                  COALESCE(SUM(col.quantity + col.foil_quantity), 0) AS owned
        FROM mtgstocks_interests i
        JOIN cards c ON c.id = i.card_id
        JOIN collection col ON col.card_id = i.card_id
        WHERE i.date = ? AND i.card_id IS NOT NULL
        GROUP BY i.id
        ORDER BY ABS(i.percentage) DESC""",
        (latest,),
    )
    rows = await cursor.fetchall()

    # Dedupe per (card_id, is_foil), keeping the largest absolute move.
    best: dict[tuple[int, int], dict[str, Any]] = {}
    for r in rows:
        key = (r["card_id"], r["is_foil"])
        pct = r["percentage"] or 0
        if key in best and abs(best[key]["percentage"] or 0) >= abs(pct):
            continue
        best[key] = {
            "card_id": r["card_id"],
            "card_name": r["card_name"],
            "set_name": r["set_name"],
            "set_code": r["set_code"] or r["owned_set_code"] or "",
            "kind": r["kind"],
            "is_foil": bool(r["is_foil"]),
            "interest_type": r["interest_type"],
            "percentage": round(pct, 1),
            "present_price": r["present_price"],
            "past_price": r["past_price"],
            "direction": "up" if pct >= 0 else "down",
            "owned": int(r["owned"]),
        }
    movers = sorted(best.values(), key=lambda m: abs(m["percentage"]), reverse=True)
    return movers[:limit]


async def get_buy_sell_signals() -> dict[str, list[dict[str, Any]]]:
    """Buy signals (wishlist near all-time low) and sell signals (owned near all-time high).

    Prices are TCGplayer USD. "Unused" sell copies mirror the Cardmarket alert logic.
    """
    db = await get_db()

    # BUY: wishlist cards trading near their all-time low.
    buy_cursor = await db.execute(
        """SELECT mp.card_id, mp.card_name, mp.set_name, mp.market, mp.avg,
                  mp.all_time_low, mp.all_time_low_date, w.target_price_eur
        FROM mtgstocks_prints mp
        JOIN wishlist w ON w.card_id = mp.card_id
        WHERE w.removed_at IS NULL AND w.status = 'wanted'
          AND mp.all_time_low IS NOT NULL AND mp.all_time_low > 0
          AND COALESCE(mp.market, mp.avg) IS NOT NULL
          AND COALESCE(mp.market, mp.avg) <= mp.all_time_low * (1 + ?)
        ORDER BY (COALESCE(mp.market, mp.avg) - mp.all_time_low) / mp.all_time_low ASC""",
        (NEAR_ATL_PCT,),
    )
    buy = []
    for r in await buy_cursor.fetchall():
        cur = r["market"] if r["market"] is not None else r["avg"]
        pct_above = (cur - r["all_time_low"]) / r["all_time_low"] * 100 if r["all_time_low"] else 0
        buy.append({
            "card_id": r["card_id"], "card_name": r["card_name"], "set_name": r["set_name"],
            "current_usd": round(cur, 2), "all_time_low": round(r["all_time_low"], 2),
            "all_time_low_date": r["all_time_low_date"],
            "pct_above_low": round(pct_above, 1),
            "suggestion": (
                f"{r['card_name']} is near its all-time low (${cur:.2f} vs ${r['all_time_low']:.2f}, "
                f"+{pct_above:.0f}%) — good time to buy"
            ),
        })

    # SELL: owned cards trading near their all-time high, with unused copies.
    sell_cursor = await db.execute(
        """SELECT mp.card_id, mp.card_name, mp.set_name, mp.market, mp.avg,
                  mp.all_time_high, mp.all_time_high_date,
                  COALESCE(SUM(col.quantity + col.foil_quantity), 0) AS owned,
                  COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc WHERE dc.card_id = mp.card_id), 0) AS in_decks
        FROM mtgstocks_prints mp
        JOIN collection col ON col.card_id = mp.card_id
        JOIN cards c ON c.id = mp.card_id
        WHERE mp.all_time_high IS NOT NULL AND mp.all_time_high > 0
          AND COALESCE(mp.market, mp.avg) IS NOT NULL
          AND COALESCE(mp.market, mp.avg) >= mp.all_time_high * (1 - ?)
          AND c.type_line NOT LIKE '%Basic Land%'
        GROUP BY mp.card_id
        ORDER BY COALESCE(mp.market, mp.avg) / mp.all_time_high DESC""",
        (NEAR_ATH_PCT,),
    )
    sell = []
    for r in await sell_cursor.fetchall():
        unused = int(r["owned"]) - int(r["in_decks"])
        if unused <= 0:
            continue
        cur = r["market"] if r["market"] is not None else r["avg"]
        pct_of_high = cur / r["all_time_high"] * 100 if r["all_time_high"] else 0
        sell.append({
            "card_id": r["card_id"], "card_name": r["card_name"], "set_name": r["set_name"],
            "current_usd": round(cur, 2), "all_time_high": round(r["all_time_high"], 2),
            "all_time_high_date": r["all_time_high_date"],
            "pct_of_high": round(pct_of_high, 1),
            "owned": int(r["owned"]), "in_decks": int(r["in_decks"]), "unused_copies": unused,
            "suggestion": (
                f"{r['card_name']} is near its all-time high (${cur:.2f} vs ${r['all_time_high']:.2f}, "
                f"{pct_of_high:.0f}% of ATH) — consider selling {unused} unused "
                f"cop{'y' if unused == 1 else 'ies'}"
            ),
        })

    return {"buy": buy, "sell": sell}
