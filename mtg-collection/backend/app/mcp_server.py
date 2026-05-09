"""MCP Server implementation with Streamable HTTP transport."""
import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "MTG Collection Manager",
    instructions=(
        "You are an MTG Collection Manager assistant. You can search cards, "
        "list decks, browse a user's collection, check Cardmarket listings, "
        "get EDHREC commander recommendations and combos, and trigger syncs."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


# --- Tools ---

@mcp.tool()
async def search_card(query: str) -> str:
    """Search for Magic: The Gathering cards using Scryfall.

    Args:
        query: Search query (supports Scryfall syntax, e.g. 't:creature c:green cmc:3')
    """
    from .clients.scryfall import scryfall
    try:
        data = await scryfall.search_cards(query)
        cards = data.get("data", [])[:10]
        results = []
        for c in cards:
            prices = c.get("prices", {})
            results.append({
                "name": c.get("name"),
                "mana_cost": c.get("mana_cost"),
                "type_line": c.get("type_line"),
                "oracle_text": c.get("oracle_text", "")[:200],
                "set": c.get("set_name"),
                "rarity": c.get("rarity"),
                "price_usd": prices.get("usd"),
                "price_eur": prices.get("eur"),
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_card(name: str) -> str:
    """Get detailed information about a specific card by exact name.

    Args:
        name: Exact card name (e.g. 'Lightning Bolt')
    """
    from .clients.scryfall import scryfall
    try:
        data = await scryfall.get_card_by_name(name, exact=True)
        prices = data.get("prices", {})
        legalities = data.get("legalities", {})
        return json.dumps({
            "name": data.get("name"),
            "mana_cost": data.get("mana_cost"),
            "cmc": data.get("cmc"),
            "type_line": data.get("type_line"),
            "oracle_text": data.get("oracle_text"),
            "colors": data.get("colors"),
            "color_identity": data.get("color_identity"),
            "set": data.get("set_name"),
            "rarity": data.get("rarity"),
            "power": data.get("power"),
            "toughness": data.get("toughness"),
            "keywords": data.get("keywords"),
            "edhrec_rank": data.get("edhrec_rank"),
            "prices": {k: v for k, v in prices.items() if v},
            "legalities": legalities,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def list_decks() -> str:
    """List all synced decks from Archidekt."""
    from .database import get_db
    from .services.queries import query_all_decks
    try:
        db = await get_db()
        decks = await query_all_decks(db)
        return json.dumps(decks, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_deck(deck_id: int) -> str:
    """Get detailed deck information with all cards.

    Args:
        deck_id: Local deck ID (from list_decks)
    """
    from .database import get_db
    from .services.queries import query_deck_detail
    try:
        db = await get_db()
        detail = await query_deck_detail(db, deck_id)
        if not detail:
            return json.dumps({"error": f"Deck {deck_id} not found"})
        return json.dumps(detail, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def search_collection(
    query: str = "",
    sort_by: str = "name",
    sort_dir: str = "asc",
    limit: int = 50,
) -> str:
    """Search your card collection by name.

    Args:
        query: Card name or partial name to search for (empty returns all)
        sort_by: Sort field: name, price_eur, price_usd, set, added_at, archidekt_tags, quantity
        sort_dir: Sort direction: asc or desc
        limit: Max results to return (1-200, default 50)
    """
    from .database import get_db
    try:
        db = await get_db()
        limit = max(1, min(200, limit))
        where = "c.name LIKE ?" if query else "1=1"
        params: list[Any] = [f"%{query}%"] if query else []

        sort_col = {
            "name": "LOWER(c.name)",
            "price_eur": (
                "CAST(CASE "
                "WHEN col.foil_quantity > 0 AND col.quantity = 0 "
                "THEN COALESCE(NULLIF(c.price_eur_foil, ''), NULLIF(c.price_eur, ''), '0') "
                "ELSE COALESCE(NULLIF(c.price_eur, ''), NULLIF(c.price_eur_foil, ''), '0') "
                "END AS REAL)"
            ),
            "price_usd": (
                "CAST(CASE "
                "WHEN col.foil_quantity > 0 AND col.quantity = 0 "
                "THEN COALESCE(NULLIF(c.price_usd_foil, ''), NULLIF(c.price_usd, ''), '0') "
                "ELSE COALESCE(NULLIF(c.price_usd, ''), NULLIF(c.price_usd_foil, ''), '0') "
                "END AS REAL)"
            ),
            "set": "LOWER(c.set_name)",
            "added_at": "col.added_at",
            "archidekt_tags": "LOWER(col.archidekt_tags)",
            "quantity": "(col.quantity + col.foil_quantity)",
        }.get(sort_by, "LOWER(c.name)")
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

        cursor = await db.execute(
            f"""SELECT c.name, c.set_name, c.rarity, c.price_eur, c.price_usd,
            c.price_eur_foil, c.price_usd_foil,
            col.quantity, col.foil_quantity, col.condition,
            col.language, col.archidekt_tags, col.added_at
            FROM collection col JOIN cards c ON c.id = col.card_id
            WHERE {where}
            ORDER BY {sort_col} {direction}, LOWER(c.name) ASC
            LIMIT ?""",
            params + [limit],
        )
        results = [{
            "name": r[0], "set": r[1], "rarity": r[2],
            "price_eur": r[3], "price_usd": r[4],
            "price_eur_foil": r[5], "price_usd_foil": r[6],
            "quantity": r[7], "foil_quantity": r[8], "condition": r[9],
            "language": r[10], "archidekt_tags": r[11] or "",
            "added_at": r[12],
        } for r in await cursor.fetchall()]
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_collection_stats() -> str:
    """Get statistics about your collection (total cards, value, etc.)."""
    from .database import get_db
    from .services.queries import query_collection_stats
    try:
        db = await get_db()
        stats = await query_collection_stats(db)
        return json.dumps({
            "total_cards": stats["total_cards"],
            "unique_cards": stats["unique_cards"],
            "total_value_eur": stats["total_value_eur"],
            "total_value_usd": stats["total_value_usd"],
            "total_decks": stats["total_decks"],
            "cardmarket_listings": stats["total_cardmarket_listings"],
            "cardmarket_value": stats["cardmarket_total_value"],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_cardmarket_listings() -> str:
    """Get all cards currently listed on Cardmarket."""
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT card_name, set_name, quantity, price, condition, language, is_foil
            FROM cardmarket_listings ORDER BY card_name LIMIT 200"""
        )
        results = [{
            "name": r[0], "set": r[1], "quantity": r[2],
            "price": r[3], "condition": r[4], "language": r[5],
            "foil": bool(r[6]),
        } for r in await cursor.fetchall()]
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_card_price(name: str) -> str:
    """Get current price information for a card.

    Args:
        name: Exact card name
    """
    from .clients.scryfall import scryfall
    try:
        data = await scryfall.get_card_by_name(name, exact=True)
        prices = data.get("prices", {})
        return json.dumps({
            "name": data.get("name"),
            "set": data.get("set_name"),
            "prices": {k: v for k, v in prices.items() if v},
            "purchase_uris": data.get("purchase_uris", {}),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_edhrec_recommendations(commander: str) -> str:
    """Get EDHREC card recommendations for a commander.

    Args:
        commander: Commander name (e.g. 'Meren of Clan Nel Toth')
    """
    from .clients.edhrec import edhrec, parse_edhrec_recommendations, slugify_commander
    try:
        slug = slugify_commander(commander)
        data = await edhrec.get_commander_recommendations(slug)
        if not data:
            return json.dumps({"error": f"No EDHREC data found for '{commander}'"})

        recs = parse_edhrec_recommendations(data)[:30]
        return json.dumps([{
            "name": r["name"], "inclusion": r["inclusion"],
            "num_decks": r["num_decks"], "synergy": r.get("synergy", 0),
            "category": r.get("category", ""),
        } for r in recs], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_edhrec_combos(commander: str) -> str:
    """Get known combos for a commander from EDHREC.

    Args:
        commander: Commander name (e.g. 'Meren of Clan Nel Toth')
    """
    from .clients.edhrec import edhrec, parse_edhrec_combos, slugify_commander
    try:
        slug = slugify_commander(commander)
        data = await edhrec.get_combos(slug)
        if not data:
            return json.dumps({"error": f"No combo data found for '{commander}'"})

        combos = parse_edhrec_combos(data)[:20]
        return json.dumps(combos, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def trigger_sync() -> str:
    """Trigger a manual sync from Archidekt."""
    from .services.sync_service import run_full_sync
    try:
        result = await run_full_sync()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_price_alerts() -> str:
    """Get price spike alerts for owned cards with unused copies.

    Returns cards where the Cardmarket trend price spiked >30% above the 30-day average,
    and the user has copies not used in any deck. Includes sell suggestions.
    """
    from .services.cardmarket_prices import get_price_alerts as _get_alerts
    try:
        alerts = await _get_alerts()
        return json.dumps(alerts, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_price_history(card_name: str, days: int = 30) -> str:
    """Get Cardmarket price history for a card.

    Args:
        card_name: Card name to look up
        days: Number of days of history (default 30)
    """
    from .database import get_db
    from .services.cardmarket_prices import get_price_history as _get_history
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT cm_product_id, card_name, expansion_name FROM cardmarket_products WHERE card_name LIKE ? LIMIT 5",
            (f"%{card_name}%",),
        )
        products = await cursor.fetchall()
        if not products:
            return json.dumps({"error": f"No Cardmarket product found for '{card_name}'"})

        results = []
        for p in products:
            history = await _get_history(p[0], days)
            results.append({
                "card_name": p[1],
                "expansion": p[2],
                "cm_product_id": p[0],
                "history": history,
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_deck_usage(card_name: str) -> str:
    """Check which decks a card is used in and how many copies.

    Args:
        card_name: Card name to look up
    """
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT d.name, d.format, dc.quantity, dc.category, dc.is_commander
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            JOIN decks d ON d.id = dc.deck_id
            WHERE LOWER(c.name) = LOWER(?)
            ORDER BY d.name""",
            (card_name,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return json.dumps({"card_name": card_name, "used_in_decks": 0, "decks": []})

        decks = [{
            "deck_name": r[0], "format": r[1], "quantity": r[2],
            "category": r[3], "is_commander": bool(r[4]),
        } for r in rows]
        total = sum(d["quantity"] for d in decks)
        return json.dumps({
            "card_name": card_name,
            "used_in_decks": len(decks),
            "total_copies_in_decks": total,
            "decks": decks,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def sync_prices() -> str:
    """Trigger a manual Cardmarket price data sync for owned cards."""
    from .services.cardmarket_prices import sync_cardmarket_prices
    try:
        result = await sync_cardmarket_prices()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_duplicates(search: str = "", page: int = 1, page_size: int = 50) -> str:
    """Get cards where you own more copies than are used in decks.

    Args:
        search: Optional card name filter
        page: Page number (default 1)
        page_size: Items per page (default 50)
    """
    from .database import get_db
    db = await get_db()
    offset = (page - 1) * page_size
    where = "WHERE extras > 0"
    params: list[Any] = []
    if search:
        where += " AND card_name LIKE ?"
        params.append(f"%{search}%")

    count_cursor = await db.execute(
        f"""WITH dups AS (
            SELECT c.name as card_name, c.set_name, c.set_code, c.rarity,
                   c.price_eur, co.quantity + co.foil_quantity as total_copies,
                   COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc WHERE dc.card_id = c.id), 0) as in_decks,
                   (co.quantity + co.foil_quantity) - COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc WHERE dc.card_id = c.id), 0) as extras
            FROM collection co JOIN cards c ON co.card_id = c.id
            WHERE (co.quantity + co.foil_quantity) > 1
        ) SELECT COUNT(*) FROM dups {where}""", params)
    total = (await count_cursor.fetchone())[0]

    cursor = await db.execute(
        f"""WITH dups AS (
            SELECT c.name as card_name, c.set_name, c.set_code, c.rarity,
                   c.price_eur, co.quantity + co.foil_quantity as total_copies,
                   COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc WHERE dc.card_id = c.id), 0) as in_decks,
                   (co.quantity + co.foil_quantity) - COALESCE((SELECT SUM(dc.quantity) FROM deck_cards dc WHERE dc.card_id = c.id), 0) as extras
            FROM collection co JOIN cards c ON co.card_id = c.id
            WHERE (co.quantity + co.foil_quantity) > 1
        ) SELECT * FROM dups {where} ORDER BY extras DESC, card_name LIMIT ? OFFSET ?""",
        params + [page_size, offset])
    rows = await cursor.fetchall()
    items = [dict(r) for r in rows]
    return json.dumps({"items": items, "total": total, "page": page}, indent=2)


@mcp.tool()
async def add_cardmarket_listing(card_name: str, quantity: int = 1, price: float = 0.0,
                                  condition: str = "NM", language: str = "English",
                                  set_name: str = "", set_code: str = "",
                                  rarity: str = "", comments: str = "") -> str:
    """Create a manual Cardmarket listing for selling a card.

    Args:
        card_name: Name of the card to list
        quantity: Number of copies to sell
        price: Price in EUR
        condition: Card condition (MT, NM, EX, GD, LP, PL, PO)
        language: Card language
        set_name: Set/expansion name
        set_code: Set code
        rarity: Card rarity
        comments: Additional comments
    """
    from .database import get_db
    db = await get_db()
    await db.execute(
        """INSERT INTO cardmarket_listings
        (card_name, set_name, set_code, quantity, price, condition, language, is_foil, rarity, comments, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'manual')""",
        (card_name, set_name, set_code, quantity, price, condition, language, rarity, comments),
    )
    await db.commit()
    return json.dumps({"status": "created", "card_name": card_name, "quantity": quantity, "price": price})


@mcp.tool()
async def clear_cardmarket_listings() -> str:
    """Delete all Cardmarket listings (both CSV-imported and manually created)."""
    from .database import get_db
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM cardmarket_listings")
    count = (await cursor.fetchone())[0]
    await db.execute("DELETE FROM cardmarket_listings")
    await db.commit()
    return json.dumps({"status": "cleared", "deleted": count})


@mcp.tool()
async def suggest_what_to_sell(target_amount_eur: float = 50.0, max_suggestions: int = 10) -> str:
    """Suggest cards to sell based on unused copies and price trends.

    Prioritizes cards with price spikes and copies not used in any deck.
    Accumulates suggestions until target amount is reached.

    Args:
        target_amount_eur: Target sell amount in EUR (default 50.0)
        max_suggestions: Maximum number of card suggestions (default 10)
    """
    from .services.sell_advisor import suggest_sells
    try:
        suggestions = await suggest_sells(target_amount_eur, max_suggestions)
        if not suggestions:
            return json.dumps({"message": "Keine Verkaufsempfehlungen — entweder keine ungenutzten Kopien oder keine Preisdaten vorhanden.", "suggestions": []})
        total = sum(s["expected_total_eur"] for s in suggestions)
        return json.dumps({
            "target_eur": target_amount_eur,
            "estimated_total_eur": round(total, 2),
            "target_reached": total >= target_amount_eur,
            "suggestions": suggestions,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_wishlist(
    status: str = "wanted",
    priority_min: int = 1,
    deck_id: int | None = None,
    deals_only: bool = False,
) -> str:
    """Get the wishlist with filters and current prices.

    Args:
        status: Filter by status: 'wanted', 'acquired', 'dropped', or 'all'
        priority_min: Minimum priority (1-5). Default 1 = show all.
        deck_id: Only show items for a specific deck.
        deals_only: If True, only return items where current_price <= target_price_eur.

    Returns:
        JSON list of wishlist items with current price, is_deal flag, and all fields.
    """
    from .database import get_db
    try:
        db = await get_db()
        conditions = ["w.removed_at IS NULL"]
        params: list = []
        if status != "all":
            conditions.append("w.status = ?")
            params.append(status)
        if priority_min > 1:
            conditions.append("w.priority >= ?")
            params.append(priority_min)
        if deck_id is not None:
            conditions.append("w.deck_id = ?")
            params.append(deck_id)
        where = " AND ".join(conditions)
        cursor = await db.execute(
            f"""SELECT w.id, w.card_id, w.target_price_eur, w.notes, w.added_at,
                      w.set_code, w.is_foil, w.quantity, w.priority, w.status,
                      w.deck_id, w.tags, w.acquired_at,
                      c.name AS card_name, c.scryfall_id, c.set_name,
                      c.price_eur, c.price_eur_foil,
                      d.name AS deck_name,
                      (SELECT ph.trend FROM cardmarket_products cp
                       JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                       WHERE LOWER(cp.card_name) = LOWER(c.name)
                       ORDER BY ph.date DESC LIMIT 1) AS cm_trend
               FROM wishlist w
               LEFT JOIN cards c ON c.id = w.card_id
               LEFT JOIN decks d ON d.id = w.deck_id
               WHERE {where}
               ORDER BY w.priority DESC, w.added_at DESC""",
            params,
        )
        rows = await cursor.fetchall()
        items = []
        for r in rows:
            # Prefer cardmarket trend, fall back to scryfall price
            def _fp(v):
                try: return float(v) if v and v != "" else None
                except (ValueError, TypeError): return None
            current = _fp(r["cm_trend"])
            if current is None:
                current = _fp(r["price_eur_foil"]) if r["is_foil"] else _fp(r["price_eur"])
            target = r["target_price_eur"] or 0
            is_deal = current is not None and target > 0 and current <= target
            if deals_only and not is_deal:
                continue
            tags = [t.strip() for t in (r["tags"] or "").split(",") if t.strip()]
            items.append({
                "id": r["id"],
                "card_name": r["card_name"] or "",
                "set_code": r["set_code"],
                "is_foil": bool(r["is_foil"]),
                "quantity": r["quantity"] or 1,
                "priority": r["priority"] or 3,
                "status": r["status"] or "wanted",
                "deck_id": r["deck_id"],
                "deck_name": r["deck_name"],
                "tags": tags,
                "target_price_eur": target,
                "current_price_eur": current,
                "is_deal": is_deal,
                "notes": r["notes"] or "",
                "added_at": r["added_at"] or "",
                "acquired_at": r["acquired_at"],
            })
        return json.dumps(items, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def add_to_wishlist(
    card_name: str,
    set_code: str = "",
    is_foil: bool = False,
    quantity: int = 1,
    target_price_eur: float = 0.0,
    priority: int = 3,
    deck_id: int | None = None,
    tags: str = "",
    notes: str = "",
) -> str:
    """Add a card to the wishlist.

    Args:
        card_name: Exact card name (resolved via DB or Scryfall).
        set_code: Optional 3-letter set code (e.g. 'mh3'). Empty = no set preference.
        is_foil: Whether the desired version is foil.
        quantity: Number of copies wanted (1-99).
        target_price_eur: Maximum price per copy to trigger deal alert (0 = no alert).
        priority: 1 (low) to 5 (high). Default 3.
        deck_id: Optional ID of a deck this card is wanted for.
        tags: Comma-separated tags (e.g. 'modern,foil-priority').
        notes: Free-form notes.

    Returns:
        JSON string with the created item or error.
    """
    from .database import get_db
    from .services.card_resolver import resolve_card
    try:
        if not 1 <= priority <= 5:
            return json.dumps({"error": "priority must be 1-5"})
        if not 1 <= quantity <= 99:
            return json.dumps({"error": "quantity must be 1-99"})
        db = await get_db()
        card = await resolve_card(db, card_name=card_name, set_code=set_code or None)
        if not card:
            return json.dumps({"error": f"Card '{card_name}' not found"})
        try:
            cursor = await db.execute(
                """INSERT INTO wishlist
                   (card_id, set_code, is_foil, quantity, target_price_eur, priority, deck_id, tags, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    card["id"], set_code or None, int(is_foil), quantity,
                    target_price_eur, priority, deck_id, tags.strip(), notes.strip(),
                ),
            )
            await db.commit()
            return json.dumps({
                "id": cursor.lastrowid,
                "card_name": card["name"],
                "set_code": set_code or None,
                "is_foil": is_foil,
                "quantity": quantity,
                "target_price_eur": target_price_eur,
                "priority": priority,
            }, indent=2)
        except Exception as e:
            if "UNIQUE" in str(e):
                return json.dumps({"error": "Already on wishlist with this set/foil combination"})
            raise
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def update_wishlist_item(
    item_id: int,
    target_price_eur: float | None = None,
    priority: int | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> str:
    """Update a wishlist item's fields. Only provided (non-None) fields are changed.

    Args:
        item_id: ID of the wishlist item to update.
        target_price_eur: New price alert threshold (0 = no alert).
        priority: New priority 1 (low) to 5 (high).
        status: New status: 'wanted', 'acquired', or 'dropped'.
        notes: New notes text.

    Returns:
        JSON with updated item or error.
    """
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT id FROM wishlist WHERE id = ? AND removed_at IS NULL", (item_id,)
        )
        if not await cursor.fetchone():
            return json.dumps({"error": f"Wishlist item {item_id} not found"})

        fields = []
        params: list = []
        if target_price_eur is not None:
            fields.append("target_price_eur = ?")
            params.append(target_price_eur)
        if priority is not None:
            if not 1 <= priority <= 5:
                return json.dumps({"error": "priority must be 1-5"})
            fields.append("priority = ?")
            params.append(priority)
        if status is not None:
            if status not in ("wanted", "acquired", "dropped"):
                return json.dumps({"error": "status must be 'wanted', 'acquired', or 'dropped'"})
            fields.append("status = ?")
            params.append(status)
            if status == "acquired":
                fields.append("acquired_at = CURRENT_TIMESTAMP")
        if notes is not None:
            fields.append("notes = ?")
            params.append(notes.strip())

        if not fields:
            return json.dumps({"error": "No fields to update"})

        params.append(item_id)
        await db.execute(
            f"UPDATE wishlist SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        await db.commit()
        return json.dumps({"ok": True, "item_id": item_id, "updated": {k: v for k, v in zip(["target_price_eur", "priority", "status", "notes"], [target_price_eur, priority, status, notes]) if v is not None}})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def wishlist_summary() -> str:
    """Get aggregate stats for the wishlist.

    Useful for questions like: 'How much would my wishlist cost?' or
    'How many priority-5 cards do I want?'

    Returns:
        JSON with total items, quantities, target/current EUR values,
        deal count, by_priority breakdown, and by_deck breakdown.
    """
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT w.quantity, w.target_price_eur, w.priority, w.deck_id, w.is_foil,
                      c.name AS card_name, c.price_eur, c.price_eur_foil,
                      d.name AS deck_name,
                      (SELECT ph.trend FROM cardmarket_products cp
                       JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                       WHERE LOWER(cp.card_name) = LOWER(c.name)
                       ORDER BY ph.date DESC LIMIT 1) AS cm_trend
               FROM wishlist w
               LEFT JOIN cards c ON c.id = w.card_id
               LEFT JOIN decks d ON d.id = w.deck_id
               WHERE w.removed_at IS NULL AND w.status = 'wanted'"""
        )
        rows = await cursor.fetchall()
        total_items = 0
        total_qty = 0
        total_target = 0.0
        total_current = 0.0
        deals = 0
        unknown_price = 0
        by_priority: dict[int, int] = {}
        deck_counts: dict[int, dict] = {}

        def _fp(v):
            try: return float(v) if v and v != "" else None
            except (ValueError, TypeError): return None

        for r in rows:
            total_items += 1
            qty = r["quantity"] or 1
            total_qty += qty
            target = r["target_price_eur"] or 0
            total_target += target * qty
            current = _fp(r["cm_trend"])
            if current is None:
                current = _fp(r["price_eur_foil"]) if r["is_foil"] else _fp(r["price_eur"])
            if current is not None:
                total_current += current * qty
                if target > 0 and current <= target:
                    deals += 1
            else:
                unknown_price += 1
            prio = r["priority"] or 3
            by_priority[prio] = by_priority.get(prio, 0) + 1
            if r["deck_id"] is not None:
                did = r["deck_id"]
                if did not in deck_counts:
                    deck_counts[did] = {"deck_id": did, "deck_name": r["deck_name"] or "", "count": 0}
                deck_counts[did]["count"] += 1

        return json.dumps({
            "total_items": total_items,
            "total_quantity": total_qty,
            "total_target_eur": round(total_target, 2),
            "total_current_eur": round(total_current, 2),
            "items_with_deals": deals,
            "items_unknown_price": unknown_price,
            "by_priority": by_priority,
            "by_deck": list(deck_counts.values()),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def find_card_printings(card_name: str) -> str:
    """List all printings of a card across sets, with prices.

    Useful before adding to wishlist when comparing set prices or art.
    Returns results sorted by release date (newest first).

    Args:
        card_name: Exact card name (e.g. 'Lightning Bolt').

    Returns:
        JSON list with set_code, set_name, rarity, released_at, price_eur, price_eur_foil.
    """
    from .clients.scryfall import scryfall
    try:
        printings = await scryfall.get_card_printings(card_name)
        if not printings:
            return json.dumps({"error": f"No printings found for '{card_name}'"})
        # Return a concise view for Claude (full data can be large)
        concise = [{
            "scryfall_id": p["scryfall_id"],
            "set_code": p["set_code"],
            "set_name": p["set_name"],
            "collector_number": p["collector_number"],
            "rarity": p["rarity"],
            "released_at": p["released_at"],
            "price_eur": p["price_eur"],
            "price_eur_foil": p["price_eur_foil"],
            "foil_available": p["is_foil_available"],
            "nonfoil_available": p["is_nonfoil_available"],
        } for p in printings]
        return json.dumps({"card": card_name, "printing_count": len(concise), "printings": concise}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def wishlist_to_cardmarket_decklist() -> str:
    """Generate Cardmarket-compatible decklist from the current 'wanted' wishlist.

    Returns plaintext that can be pasted directly into Cardmarket's
    'Add cards' wantlist dialog.
    Format: '<quantity> <card_name>' per line, sorted by priority desc then name.

    Returns:
        Plain text string (newline-separated), not JSON.
    """
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            """SELECT w.quantity, c.name
               FROM wishlist w
               LEFT JOIN cards c ON c.id = w.card_id
               WHERE w.removed_at IS NULL AND w.status = 'wanted'
               ORDER BY w.priority DESC, c.name ASC"""
        )
        rows = await cursor.fetchall()
        lines = [f"{r['quantity'] or 1} {r['name']}" for r in rows if r["name"]]
        if not lines:
            return "# Wishlist is empty"
        return "\n".join(lines)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def analyze_deck_completeness(deck_id: int) -> str:
    """Analyze how complete a deck is based on your collection.

    Shows which cards you own, which are missing, and estimated cost to complete.

    Args:
        deck_id: Local deck ID (from list_decks)
    """
    from .database import get_db
    from .services.queries import query_deck_detail
    try:
        db = await get_db()
        detail = await query_deck_detail(db, deck_id)
        if not detail:
            return json.dumps({"error": f"Deck {deck_id} not found"})

        owned_cards: list[dict] = []
        missing_cards: list[dict] = []
        total_missing_cost = 0.0

        for card in detail["cards"]:
            # Check if we own this card in collection
            cursor = await db.execute(
                """SELECT COALESCE(SUM(col.quantity + col.foil_quantity), 0)
                FROM collection col JOIN cards c ON c.id = col.card_id
                WHERE LOWER(c.name) = LOWER(?)""",
                (card["name"],),
            )
            row = await cursor.fetchone()
            owned_qty = row[0] if row else 0

            needed = card["quantity"]
            if owned_qty >= needed:
                owned_cards.append({"name": card["name"], "quantity": needed, "owned": owned_qty})
            else:
                short = needed - owned_qty
                price = 0.0
                try:
                    price = float(card.get("price_eur") or 0) * short
                except (ValueError, TypeError):
                    pass
                total_missing_cost += price
                missing_cards.append({
                    "name": card["name"],
                    "needed": needed,
                    "owned": owned_qty,
                    "short": short,
                    "est_cost_eur": round(price, 2),
                })

        total_cards = len(detail["cards"])
        complete_pct = round(len(owned_cards) / total_cards * 100, 1) if total_cards else 0

        return json.dumps({
            "deck": detail["name"],
            "format": detail["format"],
            "total_unique_cards": total_cards,
            "owned_count": len(owned_cards),
            "missing_count": len(missing_cards),
            "completeness_pct": complete_pct,
            "estimated_cost_to_complete_eur": round(total_missing_cost, 2),
            "missing_cards": sorted(missing_cards, key=lambda x: x["est_cost_eur"], reverse=True),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def mark_wishlist_ordered(item_id: int, expected_price_eur: float | None = None) -> str:
    """Mark a wishlist item as ordered (bought but not yet received).

    Use this when the user confirms they bought a card but it hasn't arrived yet
    (Whatnot stream, Cardmarket order, etc).

    Args:
        item_id: ID of the wishlist item.
        expected_price_eur: Expected price paid per copy (optional).
    """
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, status, card_id FROM wishlist WHERE id = ? AND removed_at IS NULL",
            (item_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return json.dumps({"error": f"Wishlist item {item_id} not found"})
        if row["status"] == "acquired":
            return json.dumps({"error": "Item is already acquired"})

        await db.execute(
            """UPDATE wishlist SET is_ordered = 1, ordered_at = CURRENT_TIMESTAMP,
               expected_price_eur = COALESCE(?, expected_price_eur)
               WHERE id = ?""",
            (expected_price_eur, item_id),
        )
        await db.commit()
        return json.dumps({"ok": True, "item_id": item_id, "is_ordered": True,
                           "expected_price_eur": expected_price_eur})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def mark_wishlist_acquired(
    item_id: int,
    paid_price_eur: float | None = None,
    source: str | None = None,
) -> str:
    """Mark a wishlist item as acquired (received and added to physical collection).

    source: one of cardmarket, whatnot, booster, trade, gift, shop, other.
    If item was ordered with expected_price_eur and paid_price_eur is None,
    expected_price_eur is used as the paid price.

    Args:
        item_id: ID of the wishlist item.
        paid_price_eur: Actual price paid per copy.
        source: Acquisition source (cardmarket|whatnot|booster|trade|gift|shop|other).
    """
    from .database import get_db
    try:
        valid_sources = {"cardmarket", "whatnot", "booster", "trade", "gift", "shop", "other", None}
        if source not in valid_sources:
            return json.dumps({"error": f"Invalid source '{source}'. Must be one of: {', '.join(s for s in valid_sources if s)}"})

        db = await get_db()
        cursor = await db.execute(
            "SELECT id, status, is_ordered, expected_price_eur FROM wishlist WHERE id = ? AND removed_at IS NULL",
            (item_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return json.dumps({"error": f"Wishlist item {item_id} not found"})
        if row["status"] == "acquired":
            return json.dumps({"error": "Item is already acquired"})

        # Fall back to expected_price_eur if ordered and no paid_price given
        actual_paid = paid_price_eur
        if actual_paid is None and row["is_ordered"] and row["expected_price_eur"] is not None:
            actual_paid = row["expected_price_eur"]

        await db.execute(
            """UPDATE wishlist
               SET status = 'acquired', acquired_at = CURRENT_TIMESTAMP,
                   is_ordered = 0,
                   paid_price_eur = COALESCE(?, paid_price_eur),
                   source = COALESCE(?, source)
               WHERE id = ?""",
            (actual_paid, source, item_id),
        )
        await db.commit()
        return json.dumps({"ok": True, "item_id": item_id, "status": "acquired",
                           "paid_price_eur": actual_paid, "source": source})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def mark_wishlist_not_received(item_id: int) -> str:
    """Mark a wishlist item as not received (was ordered but never arrived).

    Use this for lost packages, failed Whatnot deliveries, refunds where the seller
    never shipped.

    Args:
        item_id: ID of the wishlist item.
    """
    from .database import get_db
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT id FROM wishlist WHERE id = ? AND removed_at IS NULL",
            (item_id,),
        )
        if not await cursor.fetchone():
            return json.dumps({"error": f"Wishlist item {item_id} not found"})

        await db.execute(
            """UPDATE wishlist
               SET status = 'not_received', not_received_at = CURRENT_TIMESTAMP, is_ordered = 0
               WHERE id = ?""",
            (item_id,),
        )
        await db.commit()
        return json.dumps({"ok": True, "item_id": item_id, "status": "not_received"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_acquisition_stats(days: int = 30) -> str:
    """Get acquisition statistics for the last N days.

    Returns: total acquired, total spent, current market value, source breakdown,
    monthly distribution. Useful for 'what did I buy this month and what's it worth'.

    Args:
        days: Number of days to look back (default 30, max 3650).
    """
    from .database import get_db
    try:
        days = max(1, min(3650, days))
        db = await get_db()

        cursor = await db.execute(
            """
            SELECT
                COUNT(*) AS total_acquired,
                COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS total_spent,
                COALESCE(SUM(
                    COALESCE(
                        (SELECT ph.trend FROM cardmarket_products cp
                         JOIN cardmarket_price_history ph ON ph.cm_product_id = cp.cm_product_id
                         WHERE LOWER(cp.card_name) = LOWER(c.name)
                         ORDER BY ph.date DESC LIMIT 1),
                        CAST(NULLIF(c.price_eur, '') AS REAL),
                        0
                    ) * w.quantity
                ), 0) AS total_current_value
            FROM wishlist w
            LEFT JOIN cards c ON c.id = w.card_id
            WHERE w.removed_at IS NULL
              AND w.status = 'acquired'
              AND w.acquired_at >= datetime('now', ? || ' days')
            """,
            (f"-{days}",),
        )
        totals = await cursor.fetchone()

        cursor = await db.execute(
            """
            SELECT
                COALESCE(w.source, 'unknown') AS source,
                COUNT(*) AS count,
                COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS total_spent
            FROM wishlist w
            WHERE w.removed_at IS NULL
              AND w.status = 'acquired'
              AND w.acquired_at >= datetime('now', ? || ' days')
            GROUP BY COALESCE(w.source, 'unknown')
            ORDER BY total_spent DESC
            """,
            (f"-{days}",),
        )
        by_source = [{"source": r[0], "count": r[1], "total_spent_eur": round(r[2], 2)}
                     for r in await cursor.fetchall()]

        cursor = await db.execute(
            """
            SELECT
                strftime('%Y-%m', w.acquired_at) AS month,
                COUNT(*) AS count,
                COALESCE(SUM(COALESCE(w.paid_price_eur, 0) * w.quantity), 0) AS spent
            FROM wishlist w
            WHERE w.removed_at IS NULL
              AND w.status = 'acquired'
              AND w.acquired_at >= datetime('now', ? || ' days')
              AND w.acquired_at IS NOT NULL
            GROUP BY strftime('%Y-%m', w.acquired_at)
            ORDER BY month DESC
            LIMIT 12
            """,
            (f"-{days}",),
        )
        by_month = [{"month": r[0], "count": r[1], "spent": round(r[2], 2)}
                    for r in await cursor.fetchall()]

        return json.dumps({
            "days": days,
            "total_acquired": totals["total_acquired"],
            "total_spent_eur": round(totals["total_spent"], 2),
            "total_current_value_eur": round(totals["total_current_value"], 2),
            "profit_loss_eur": round(totals["total_current_value"] - totals["total_spent"], 2),
            "by_source": by_source,
            "by_month": by_month,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def analyze_my_listings(threshold_pct: float = 15.0) -> str:
    """Analyze Cardmarket listings vs current market trend.

    Returns listings categorized as:
    - underpriced: my price < trend - threshold_pct (suggest raising)
    - overpriced: my price > trend + threshold_pct (won't sell, suggest lowering)
    - fair: within threshold of trend

    Args:
        threshold_pct: Tolerance band in percent (default 15%). Listings within
                       this band of the trend price are considered fair.
    """
    from .services.listing_health import analyze_listings
    try:
        result = await analyze_listings(threshold_pct)
        summary = {
            "threshold_pct": threshold_pct,
            "underpriced_count": len(result["underpriced"]),
            "overpriced_count": len(result["overpriced"]),
            "fair_count": len(result["fair"]),
            "no_match_count": len(result["no_match"]),
            "underpriced": result["underpriced"],
            "overpriced": result["overpriced"],
            "fair": result["fair"],
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Resources ---

@mcp.resource("mtg://collection/stats")
async def resource_collection_stats() -> str:
    """Current collection statistics."""
    from .database import get_db
    from .services.queries import query_collection_stats
    db = await get_db()
    stats = await query_collection_stats(db)
    return json.dumps(stats, indent=2)


@mcp.resource("mtg://decks")
async def resource_deck_list() -> str:
    """List of all synced decks."""
    from .database import get_db
    from .services.queries import query_all_decks
    db = await get_db()
    decks = await query_all_decks(db)
    return json.dumps(decks, indent=2, default=str)


@mcp.resource("mtg://deck/{deck_id}")
async def resource_deck(deck_id: str) -> str:
    """Detail data for a single deck."""
    from .database import get_db
    from .services.queries import query_deck_detail
    try:
        deck_id_int = int(deck_id)
    except ValueError:
        return json.dumps({"error": f"Invalid deck_id: {deck_id}"})
    db = await get_db()
    detail = await query_deck_detail(db, deck_id_int)
    if not detail:
        return json.dumps({"error": f"Deck {deck_id} not found"})
    return json.dumps(detail, default=str, indent=2)


@mcp.tool()
async def set_deck_ai_assessment(deck_id: int, assessment: str) -> str:
    """Write or update the AI assessment for a deck.

    Use this when the user asks for a deck review or analysis.
    The text supports Markdown formatting. Max 5000 chars.

    Args:
        deck_id: The ID of the deck
        assessment: The full assessment text (Markdown). Replaces previous assessment.

    Returns:
        JSON: {"deck_id": ..., "ai_assessment_updated_at": ..., "char_count": ...}
    """
    from .database import get_db
    try:
        if len(assessment) > 5000:
            return json.dumps({"error": "Assessment exceeds 5000 character limit"})
        db = await get_db()
        cursor = await db.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
        if not await cursor.fetchone():
            return json.dumps({"error": f"Deck {deck_id} not found"})
        await db.execute(
            "UPDATE decks SET ai_assessment = ?, ai_assessment_updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (assessment, deck_id),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT ai_assessment_updated_at FROM decks WHERE id = ?", (deck_id,)
        )
        row = await cursor.fetchone()
        return json.dumps({
            "deck_id": deck_id,
            "ai_assessment_updated_at": row[0] if row else None,
            "char_count": len(assessment),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Prompts ---

@mcp.prompt()
def analyze_deck(deck_name: str) -> str:
    """Prompt template for analyzing a deck."""
    return (
        f"Please analyze the MTG deck '{deck_name}'. "
        "First use the list_decks tool to find it, then get_deck to see its cards. "
        "Analyze the mana curve, color distribution, card types, synergies, "
        "and suggest potential improvements. "
        "Also check EDHREC recommendations for the commander."
    )


@mcp.prompt()
def suggest_upgrades(deck_name: str, budget: str = "20 EUR") -> str:
    """Prompt template for suggesting deck upgrades within a budget."""
    return (
        f"I want to upgrade my MTG deck '{deck_name}' with a budget of {budget}. "
        "First use list_decks and get_deck to see the current deck list. "
        "Then use get_edhrec_recommendations for the commander. "
        "Suggest cards to add and remove, staying within budget. "
        "Use get_card_price to verify current prices."
    )


def mount_mcp_server(app: FastAPI):
    """Mount the MCP server onto the FastAPI app."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    from .config import get_settings

    mcp_app = mcp.streamable_http_app()

    # Log sub-app routes for debugging
    if hasattr(mcp_app, 'routes'):
        for route in mcp_app.routes:
            logger.info("MCP sub-app route: methods=%s path=%s",
                        getattr(route, 'methods', 'N/A'),
                        getattr(route, 'path', str(route)))

    # ASGI proxy: forward requests to the MCP sub-app at /mcp
    # This avoids Starlette Mount redirect issues with HA ingress
    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
    async def mcp_proxy(request: Request):
        # Auth check: if mcp_auth_token is configured, require Bearer token
        settings = get_settings()
        if settings.mcp_auth_token:
            auth_header = request.headers.get("authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != settings.mcp_auth_token:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        # Build a new ASGI scope for the sub-app
        scope = dict(request.scope)
        scope["path"] = "/"
        scope["root_path"] = ""

        # Fix Host header — HA ingress passes the HA server's host, but the
        # MCP sub-app validates it against its own server address
        fixed_headers = []
        for name, value in scope.get("headers", []):
            if name == b"host":
                fixed_headers.append((b"host", b"localhost:8099"))
            else:
                fixed_headers.append((name, value))
        scope["headers"] = fixed_headers
        scope["server"] = ("localhost", 8099)

        response_started = False
        status_code = 200
        response_headers = []
        body_parts = []

        async def send(message):
            nonlocal response_started, status_code, response_headers
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

        await mcp_app(scope, request.receive, send)

        headers_dict = {k.decode(): v.decode() for k, v in response_headers}
        return Response(
            content=b"".join(body_parts),
            status_code=status_code,
            headers=headers_dict,
        )

    logger.info("MCP server proxied at /mcp")
