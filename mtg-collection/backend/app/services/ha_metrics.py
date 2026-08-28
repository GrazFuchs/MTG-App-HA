"""Inbox and sell metrics behind the Home Assistant sensors.

Each function returns a :class:`Metrics` with the sensor states keyed by sensor
key, plus the attribute payloads for the sensors that carry a top-N list.

HA caps a state at 255 characters, so lists always live in the attributes and
are truncated to :data:`TOP_N` entries there.
"""
from __future__ import annotations

import logging
from typing import Any, NamedTuple

import aiosqlite

from .bracket import effective_bracket

from .queries import (
    DUPLICATES_CTE,
    DUPLICATES_FINAL_CTE,
    basic_land_exclusion_sql,
)

logger = logging.getLogger(__name__)

# Entries per attribute list. Measured rather than guessed: across all 128 MTG
# entities the attributes came to 40.8 KiB in total, with the heaviest single
# payload at 2.2 KiB of the ~16 KiB Home Assistant allows — so ten was a very
# cautious number, and the dashboard tables said "showing 10 of 137" for no
# reason anybody could point at. At 25 the worst payload is still around a
# third of the limit.
TOP_N = 25

# Computing a triage suggestion costs a handful of queries per event, so the
# needs_sell/needs_keep split is derived from at most this many pending events
# (newest first).  The pending count itself is always exact.
MAX_SUGGESTION_SCAN = 300

# Upper bound on how many sell candidates the advisor is asked for.
SELL_SCAN_LIMIT = 200


class Metrics(NamedTuple):
    states: dict[str, Any]
    attributes: dict[str, dict[str, Any]]


def _price_expr(alias: str = "c", foil_col: str = "ae.is_foil") -> str:
    """Numeric EUR price of a card row, honouring the foil flag."""
    return (
        "CAST(COALESCE(NULLIF(CASE WHEN "
        f"{foil_col} THEN {alias}.price_eur_foil ELSE {alias}.price_eur END"
        ", ''), '0') AS REAL)"
    )


async def inbox_metrics(db: aiosqlite.Connection) -> Metrics:
    """Pending inbox counts, value, age and the triage-suggestion split."""
    from .triage_advisor import get_suggestion

    land_filter = basic_land_exclusion_sql("c")
    price = _price_expr()

    cursor = await db.execute(
        f"""SELECT COUNT(*) AS pending,
                   COALESCE(SUM({price} * ae.qty_delta), 0) AS value_eur,
                   CAST(julianday('now') - julianday(MIN(ae.created_at)) AS INTEGER)
                       AS oldest_age_days
            FROM acquisition_events ae
            JOIN cards c ON c.id = ae.card_id
            WHERE ae.triage_state = 'pending' AND {land_filter}"""
    )
    row = await cursor.fetchone()
    pending = int(row["pending"] or 0)
    pending_value = round(float(row["value_eur"] or 0), 2)
    oldest_age = int(row["oldest_age_days"] or 0)

    cursor = await db.execute(
        """SELECT triage_state, COUNT(*) AS cnt FROM acquisition_events
           WHERE triage_state != 'pending'
             AND triage_decision_at >= datetime('now', '-30 days')
           GROUP BY triage_state"""
    )
    by_state = {r["triage_state"]: r["cnt"] for r in await cursor.fetchall()}

    # Suggestions for the newest pending events, for the needs_sell/needs_keep
    # split and the top-N attribute list.
    cursor = await db.execute(
        f"""SELECT ae.id, ae.card_id, ae.collection_id, ae.is_foil, ae.qty_delta,
                   ae.created_at, c.name, c.set_code,
                   {price} AS price_eur,
                   CAST(julianday('now') - julianday(ae.created_at) AS INTEGER) AS age_days
            FROM acquisition_events ae
            JOIN cards c ON c.id = ae.card_id
            WHERE ae.triage_state = 'pending' AND {land_filter}
            ORDER BY ae.created_at DESC, ae.id DESC
            LIMIT ?""",
        (MAX_SUGGESTION_SCAN,),
    )
    rows = await cursor.fetchall()

    needs_sell = 0
    needs_keep = 0
    items: list[dict[str, Any]] = []
    for r in rows:
        event_row = {
            "id": r["id"],
            "card_id": r["card_id"],
            "collection_id": r["collection_id"],
            "is_foil": bool(r["is_foil"]),
            "qty_delta": r["qty_delta"],
        }
        suggestion, _printings, _in_decks = await get_suggestion(db, event_row)
        if suggestion.action in ("sold_new", "swap"):
            needs_sell += 1
        elif suggestion.action == "keep":
            needs_keep += 1

        if len(items) < TOP_N:
            items.append({
                "event_id": r["id"],
                "card_name": r["name"],
                "set_code": r["set_code"] or "",
                "quantity": r["qty_delta"],
                "is_foil": bool(r["is_foil"]),
                "suggestion": suggestion.action,
                "reason": suggestion.reason,
                "price_eur": round(float(r["price_eur"] or 0), 2),
                "age_days": int(r["age_days"] or 0),
            })

    truncated = pending > len(rows)
    if truncated:
        logger.info(
            "Inbox has %d pending events, suggestions computed for the newest %d",
            pending,
            len(rows),
        )

    return Metrics(
        states={
            "inbox_pending": pending,
            "inbox_needs_sell": needs_sell,
            "inbox_needs_keep": needs_keep,
            "inbox_pending_value_eur": pending_value,
            "inbox_oldest_age_days": oldest_age,
            "inbox_decided_30d": sum(by_state.values()),
            "inbox_has_pending": "ON" if pending > 0 else "OFF",
        },
        attributes={
            "inbox_pending": {
                "items": items,
                "suggestions_scanned": len(rows),
                "suggestions_truncated": truncated,
            },
            "inbox_decided_30d": {"by_state": by_state},
        },
    )


async def _sell_candidates() -> tuple[int, float, list[dict[str, Any]]]:
    """All sell candidates from the advisor: count, total potential, top N."""
    from .sell_advisor import suggest_sells

    suggestions = await suggest_sells(
        target_amount_eur=None, max_suggestions=SELL_SCAN_LIMIT
    )
    potential = round(sum(s["expected_total_eur"] for s in suggestions), 2)
    top = [
        {
            "card_name": s["card_name"],
            "set_name": s["set_name"],
            "copies_to_sell": s["copies_to_sell"],
            "trend_price_eur": s["trend_price_eur"],
            "expected_total_eur": s["expected_total_eur"],
            "spike_pct": s["spike_pct"],
            "reason": s["reason"],
        }
        for s in suggestions[:TOP_N]
    ]
    return len(suggestions), potential, top


async def _duplicates_surplus(db: aiosqlite.Connection) -> tuple[int, float, float, list]:
    """Surplus copies, their value, the unlisted share, and the top unlisted rows."""
    cte = DUPLICATES_CTE.replace("{where}", basic_land_exclusion_sql("c"))

    cursor = await db.execute(
        f"""{cte}, {DUPLICATES_FINAL_CTE}
            SELECT COALESCE(SUM(extras_after_listings), 0) AS surplus_cards,
                   COALESCE(SUM(extra_value), 0) AS surplus_value,
                   COALESCE(SUM(CASE WHEN listed_quantity = 0 THEN extra_value ELSE 0 END), 0)
                       AS unlisted_value
            FROM final WHERE extras_after_listings > 0"""
    )
    row = await cursor.fetchone()

    cursor = await db.execute(
        f"""{cte}, {DUPLICATES_FINAL_CTE}
            SELECT name, set_code, is_foil, extras_after_listings, extra_value
            FROM final
            WHERE extras_after_listings > 0 AND listed_quantity = 0
            ORDER BY extra_value DESC, LOWER(name) ASC
            LIMIT ?""",
        (TOP_N,),
    )
    top = [
        {
            "card_name": r["name"],
            "set_code": r["set_code"] or "",
            "is_foil": bool(r["is_foil"]),
            "surplus_copies": r["extras_after_listings"],
            "value_eur": round(float(r["extra_value"] or 0), 2),
        }
        for r in await cursor.fetchall()
    ]

    return (
        int(row["surplus_cards"] or 0),
        round(float(row["surplus_value"] or 0), 2),
        round(float(row["unlisted_value"] or 0), 2),
        top,
    )


async def sell_metrics(db: aiosqlite.Connection) -> Metrics:
    """Sell candidates, duplicate surplus and the unlisted backlog."""
    candidates, potential, top_sells = await _sell_candidates()
    surplus_cards, surplus_value, unlisted_value, top_unlisted = await _duplicates_surplus(db)

    return Metrics(
        states={
            "sell_candidates": candidates,
            "sell_potential_eur": potential,
            "duplicates_surplus_cards": surplus_cards,
            "duplicates_surplus_value_eur": surplus_value,
            "unlisted_value_eur": unlisted_value,
        },
        attributes={
            "sell_candidates": {"items": top_sells},
            "unlisted_value_eur": {"items": top_unlisted},
        },
    )


def addon_metrics() -> Metrics:
    """The add-on's own ingress link, so dashboards can deep-link into the UI.

    Stays `None` — and therefore unpublished — outside a Supervisor
    environment, where no absolute link exists.
    """
    from .ingress import deep_links, ingress_base

    base = ingress_base()
    return Metrics(
        states={"ingress_url": base or None},
        attributes={"ingress_url": deep_links()},
    )


async def deck_performance_metrics(db: aiosqlite.Connection) -> Metrics:
    """Overall play stats: games and win rate over the last 30 days, last game."""
    cursor = await db.execute(
        """SELECT COUNT(*) AS games,
                  SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                  SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                  SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws
           FROM deck_games
           WHERE played_at >= date('now', '-30 days')"""
    )
    row = await cursor.fetchone()
    games = int(row["games"] or 0)
    wins = int(row["wins"] or 0)
    win_rate = round(wins / games * 100, 1) if games else 0.0

    cursor = await db.execute(
        """SELECT g.played_at, g.result, d.name AS deck_name
           FROM deck_games g LEFT JOIN decks d ON d.id = g.deck_id
           ORDER BY g.played_at DESC, g.id DESC LIMIT 1"""
    )
    last = await cursor.fetchone()

    return Metrics(
        states={
            "games_30d": games,
            "winrate_30d": win_rate,
            # device_class timestamp needs a full ISO datetime; played_at is a
            # date.  None means "never played" — the sensor stays unknown
            # rather than getting an unparseable empty state.
            "last_game_at": f"{last['played_at']}T00:00:00+00:00" if last else None,
            "last_game_result": last["result"] if last else "none",
        },
        attributes={
            "winrate_30d": {"wins": wins, "losses": int(row["losses"] or 0),
                            "draws": int(row["draws"] or 0), "games": games},
            "last_game_result": {"deck_name": (last["deck_name"] if last else "") or ""},
        },
    )


# A deck counts as "active" — and gets its own sensor — when it was played
# within this window.  Decks that fall out of it are removed from HA again.
ACTIVE_DECK_WINDOW_DAYS = 90


async def deck_stats(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Per-deck play stats for every deck, with an `is_active` flag.

    Inactive decks are included so their sensors can be cleared from HA.
    """
    cursor = await db.execute(
        """SELECT d.id, d.name, d.bracket, d.user_bracket, d.computed_bracket,
                  d.power_score, d.power_level,
                  COUNT(g.id) AS games,
                  SUM(CASE WHEN g.result = 'win' THEN 1 ELSE 0 END) AS wins,
                  SUM(CASE WHEN g.result = 'loss' THEN 1 ELSE 0 END) AS losses,
                  SUM(CASE WHEN g.result = 'draw' THEN 1 ELSE 0 END) AS draws,
                  MAX(g.played_at) AS last_played,
                  COALESCE(MAX(g.played_at) >= date('now', ?), 0) AS is_active
           FROM decks d LEFT JOIN deck_games g ON g.deck_id = d.id
           GROUP BY d.id
           ORDER BY d.id""",
        (f"-{ACTIVE_DECK_WINDOW_DAYS} days",),
    )

    stats = []
    for r in await cursor.fetchall():
        games = int(r["games"] or 0)
        wins = int(r["wins"] or 0)
        last_played = r["last_played"]
        stats.append({
            "deck_id": r["id"],
            "deck_name": r["name"] or f"Deck {r['id']}",
            "bracket": effective_bracket(
                r["user_bracket"], r["computed_bracket"], r["bracket"]
            ),
            "bracket_source": (
                "user" if r["user_bracket"]
                else "computed" if r["computed_bracket"]
                else "archidekt" if r["bracket"] else "unset"
            ),
            "power_score": r["power_score"],
            "power_level": r["power_level"],
            "games": games,
            "wins": wins,
            "losses": int(r["losses"] or 0),
            "draws": int(r["draws"] or 0),
            "win_rate": round(wins / games * 100, 1) if games else 0.0,
            "last_played": last_played or "",
            "is_active": bool(games) and bool(r["is_active"]),
        })
    return stats


async def signal_metrics() -> Metrics:
    """MTGStocks buy/sell signals (only meaningful when the integration is on)."""
    from .mtgstocks_prices import get_buy_sell_signals

    signals = await get_buy_sell_signals()
    buy = signals.get("buy", [])
    sell = signals.get("sell", [])

    return Metrics(
        states={"signals_buy": len(buy), "signals_sell": len(sell)},
        attributes={
            "signals_buy": {"items": buy[:TOP_N]},
            "signals_sell": {"items": sell[:TOP_N]},
        },
    )
