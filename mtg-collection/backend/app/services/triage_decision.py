"""Booking a triage decision — the one implementation, for REST and for MCP.

There used to be two. The REST route wrote a `decision_snapshot`, stored the
notes and told the HA publisher that the inbox had changed; the MCP tool did
none of the three. Both "worked": the card left the queue either way. What was
missing only showed up later — a card decided through Claude appeared in the
inbox archive with no record of what it had looked like or what was suggested,
and the Home Assistant sensors kept reporting the old pending count until
something else happened to trigger a publish.

That is the shape of the bug worth preventing, not the instance: two call sites
doing "the same thing" drift apart silently, because neither is wrong on its
own. So there is one function now, and both callers pass through it.

Validation errors are raised as `TriageError` rather than `HTTPException` — the
MCP tool has no HTTP status to return, and the router translates.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..models.schemas import TriageDecisionRequest
from .ha_publisher import schedule_inbox_publish
from .triage_advisor import get_suggestion

logger = logging.getLogger(__name__)


class TriageError(Exception):
    """A decision that cannot be booked. `status` is the HTTP code REST should use."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


async def load_pending_event(db: Any, event_id: int) -> Any:
    """Fetch an event and refuse it if it is not waiting for a decision."""
    cursor = await db.execute("SELECT * FROM acquisition_events WHERE id = ?", (event_id,))
    event = await cursor.fetchone()
    if not event:
        raise TriageError("Event not found", status=404)
    if event["triage_state"] != "pending":
        raise TriageError("Already decided", status=400)
    return event


def _validate(req: TriageDecisionRequest, event: Any) -> None:
    if req.action in ("keep", "sold_new", "swap") and req.source is None:
        raise TriageError("source is required for keep/sold_new/swap")
    if req.action in ("sold_new", "swap") and req.listing_price_eur is None:
        raise TriageError("listing_price_eur is required for sold_new/swap")
    if req.sell_qty is not None and req.action == "sold_new":
        if req.sell_qty > event["qty_delta"]:
            raise TriageError(
                f"sell_qty ({req.sell_qty}) exceeds qty_delta ({event['qty_delta']})")


async def apply_decision(db: Any, event: Any, req: TriageDecisionRequest) -> dict[str, Any]:
    """Book one decision. Caller supplies an event already checked as pending.

    Commits, and schedules the Home Assistant publish. Returns the same shape
    both callers report.
    """
    _validate(req, event)

    # Snapshot the suggestion and the card exactly as they stood at decision
    # time, so the archive can later show how the item was booked *and* what it
    # was presented as when confirmed. Recomputing later gives today's answer to
    # yesterday's question.
    snapshot_card = await (await db.execute(
        "SELECT * FROM cards WHERE id = ?", (event["card_id"],))).fetchone()
    event_row = {
        "id": event["id"],
        "card_id": event["card_id"],
        "collection_id": event["collection_id"],
        "is_foil": bool(event["is_foil"]),
        "qty_delta": event["qty_delta"],
    }
    suggestion, printings, in_decks = await get_suggestion(db, event_row)

    linked_listing_id = None
    triage_state = "swapped" if req.action == "swap" else req.action

    if req.action in ("sold_new", "swap"):
        sell_col_id = None
        if req.action == "sold_new":
            cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (event["card_id"],))
        else:
            sell_col_id = req.sell_collection_id or suggestion.sell_collection_id
            if sell_col_id is None:
                raise TriageError("sell_collection_id required for swap (no suggestion available)")
            cursor = await db.execute(
                "SELECT c.* FROM collection col JOIN cards c ON c.id = col.card_id WHERE col.id = ?",
                (sell_col_id,),
            )

        card_to_list = await cursor.fetchone()
        if not card_to_list:
            raise TriageError("Card for listing not found", status=400)

        is_foil_listing = int(event["is_foil"]) if req.action == "sold_new" else 0
        if req.action == "swap" and sell_col_id is not None:
            # The old entry may be the foil one even when the new arrival is not.
            foil_row = await (await db.execute(
                "SELECT quantity, foil_quantity FROM collection WHERE id = ?",
                (sell_col_id,))).fetchone()
            if foil_row and foil_row["foil_quantity"] > 0 and foil_row["quantity"] == 0:
                is_foil_listing = 1

        quantity = (req.sell_qty if req.action == "sold_new" and req.sell_qty
                    else (req.listing_quantity or 1))
        listing_cursor = await db.execute(
            """INSERT INTO cardmarket_listings
            (card_name, set_name, set_code, quantity, price, condition, language,
             is_foil, rarity, comments, source, card_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'triage', ?)""",
            (
                card_to_list["name"],
                card_to_list["set_name"] or "",
                card_to_list["set_code"] or "",
                quantity,
                req.listing_price_eur,
                req.listing_condition or "NM",
                req.listing_language or "English",
                is_foil_listing,
                card_to_list["rarity"] or "",
                card_to_list["id"],
            ),
        )
        linked_listing_id = listing_cursor.lastrowid

    snap_price = None
    if snapshot_card is not None:
        snap_price = snapshot_card["price_eur_foil"] if event["is_foil"] else snapshot_card["price_eur"]
    snapshot = {
        "decided_action": req.action,
        "triage_state": triage_state,
        "source": req.source,
        "listing_price_eur": req.listing_price_eur,
        "sell_qty": req.sell_qty,
        "linked_listing_id": linked_listing_id,
        "card": {
            "name": snapshot_card["name"] if snapshot_card else None,
            "set_code": snapshot_card["set_code"] if snapshot_card else None,
            "set_name": snapshot_card["set_name"] if snapshot_card else None,
            "is_foil": bool(event["is_foil"]),
            "qty_delta": event["qty_delta"],
            "price_eur": snap_price,
        },
        "suggestion": suggestion.model_dump(),
        "existing_printings": [p.model_dump() for p in printings],
        "in_decks": in_decks,
    }

    await db.execute(
        """UPDATE acquisition_events
        SET triage_state = ?, triage_decision_at = CURRENT_TIMESTAMP,
            source = ?, linked_listing_id = ?, notes = ?, decision_snapshot = ?
        WHERE id = ?""",
        (triage_state, req.source, linked_listing_id, req.notes or "",
         json.dumps(snapshot, default=str), event["id"]),
    )
    await db.commit()

    schedule_inbox_publish()
    return {"status": "ok", "event_id": event["id"], "triage_state": triage_state}
