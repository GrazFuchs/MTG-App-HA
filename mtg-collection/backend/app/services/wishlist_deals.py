"""Notice when a wishlist card falls below its target price, and say so.

`is_deal` existed before this and never announced anything, because it is a
*state*: true for as long as the price stays under the target. Nothing compared
today against yesterday, so there was no moment to report — the card was simply
quietly cheap, on a list of 74, until somebody happened to look.

What is stored per entry is therefore the price at the last check. A deal is the
**crossing**: the price was above the target and now is not. That works whether
the price comes from Cardmarket or from Scryfall, which a join against the
Cardmarket price history would not — a third of the list has no Cardmarket
product at all.

Two deliberate quiet rules:

* **A target of 0 is "no target set", not "free".** Such an entry can never
  cross anything and is skipped here rather than silently counted as never a
  deal — the UI surfaces it instead, because four of the most expensive cards on
  this list are in exactly that state.
* **The same card is not announced twice in a week.** Edge detection already
  stops a daily repeat, but a price that oscillates around the target would
  cross every other day. A week of quiet is the cheapest correct answer.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..database import get_db
from .notifications import send_persistent_notification

logger = logging.getLogger(__name__)

#: How long an announced entry stays quiet, however its price wobbles.
DEAL_RENOTIFY_DAYS = 7

_ACTIVE_STATUSES = ("wanted", "ordered")

_PRICE_SELECT = """
    SELECT w.id, w.card_id, w.target_price_eur, w.is_foil, w.set_code,
           w.last_price_eur, w.deal_notified_at, w.status,
           c.name AS card_name, c.price_eur, c.price_eur_foil,
           (SELECT ph.trend FROM cardmarket_products cp
            JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
            WHERE cp.card_id = c.id
            ORDER BY ph.date DESC LIMIT 1) AS cm_trend
    FROM wishlist w
    JOIN cards c ON c.id = w.card_id
    WHERE w.removed_at IS NULL AND w.status IN ({statuses})
""".format(statuses=", ".join(f"'{s}'" for s in _ACTIVE_STATUSES))


def _current_price(row: Any) -> float | None:
    """The same reading the wishlist page shows: Cardmarket trend, else Scryfall."""
    for value in (row["cm_trend"], row["price_eur_foil"] if row["is_foil"] else row["price_eur"]):
        if value in (None, ""):
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _recently_announced(stamp: Any, now: datetime) -> bool:
    if not stamp:
        return False
    try:
        last = datetime.fromisoformat(str(stamp).replace(" ", "T"))
    except ValueError:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) < timedelta(days=DEAL_RENOTIFY_DAYS)


async def check_wishlist_deals(notify: bool = True) -> dict[str, Any]:
    """Compare every active entry against its target and report the crossings.

    Always records the current price, whether or not anything happened — that
    record *is* the comparison for the next run.
    """
    db = await get_db()
    cursor = await db.execute(_PRICE_SELECT)
    rows = await cursor.fetchall()

    now = datetime.now(timezone.utc)
    deals: list[dict[str, Any]] = []
    checked = 0
    without_target = 0
    without_price = 0

    for row in rows:
        price = _current_price(row)
        if price is None:
            without_price += 1
            continue
        checked += 1

        target = float(row["target_price_eur"] or 0)
        previous = row["last_price_eur"]

        # Record first: even a run that announces nothing has to leave the
        # comparison point for the next one.
        await db.execute(
            "UPDATE wishlist SET last_price_eur = ?, last_price_at = CURRENT_TIMESTAMP WHERE id = ?",
            (price, row["id"]),
        )

        if target <= 0:
            without_target += 1
            continue
        if price > target:
            continue
        if previous is None or float(previous) <= target:
            # Either the first sighting, or it was already below — a state, not
            # a crossing. Announcing here is what would make this fire daily.
            continue
        if _recently_announced(row["deal_notified_at"], now):
            logger.info(
                "Wishlist deal for %s suppressed: announced within %d days",
                row["card_name"], DEAL_RENOTIFY_DAYS,
            )
            continue

        deals.append({
            "wishlist_id": row["id"],
            "card_name": row["card_name"],
            "set_code": row["set_code"],
            "is_foil": bool(row["is_foil"]),
            "price_eur": round(price, 2),
            "target_price_eur": round(target, 2),
            "previous_price_eur": round(float(previous), 2),
        })

    await db.commit()

    if notify:
        for deal in deals:
            await _announce(deal)
            await db.execute(
                "UPDATE wishlist SET deal_notified_at = CURRENT_TIMESTAMP WHERE id = ?",
                (deal["wishlist_id"],),
            )
        await db.commit()

    logger.info(
        "Wishlist deal check: %d priced entries, %d crossed their target, "
        "%d without a target, %d without a price",
        checked, len(deals), without_target, without_price,
    )
    return {
        "checked": checked,
        "deals": deals,
        "without_target": without_target,
        "without_price": without_price,
    }


async def _announce(deal: dict[str, Any]) -> None:
    printing = f" ({deal['set_code'].upper()})" if deal["set_code"] else ""
    foil = " foil" if deal["is_foil"] else ""
    await send_persistent_notification(
        title=f"🎯 {deal['card_name']} is below your target",
        message=(
            f"**{deal['card_name']}**{printing}{foil} is at "
            f"**{deal['price_eur']:.2f} €** — your target is "
            f"{deal['target_price_eur']:.2f} € "
            f"(it was {deal['previous_price_eur']:.2f} € at the last check)."
        ),
        deep_link="/wishlist",
        # Stable per entry: a second crossing replaces the card rather than
        # stacking a second one beside it.
        notification_id=f"mtg_wishlist_deal_{deal['wishlist_id']}",
    )
