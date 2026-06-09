"""Deck API routes."""
import json
from datetime import date
from fastapi import APIRouter, HTTPException, Query, Response
from ..database import get_db
from ..models.schemas import (
    DeckSummary, DeckDetail, DeckCardEntry, CardResponse, DeckUserFieldsUpdate,
    DeckCombo, DeckCompareResponse, DeckCompletenessResponse, MissingCard,
    CardSummary, PairwiseOverlap,
    DeckGame, DeckGameCreate, DeckGameUpdate, DeckPerformanceStats,
)
from ..services.queries import query_all_decks
from ..services.deck_performance import compute_performance_stats

router = APIRouter()


@router.get("/", response_model=list[DeckSummary])
async def list_decks(response: Response):
    response.headers["Cache-Control"] = "public, max-age=30"
    db = await get_db()
    decks = await query_all_decks(db)
    return [DeckSummary(**d) for d in decks]


@router.get("/compare", response_model=DeckCompareResponse)
async def compare_decks(ids: str = Query(..., description="Comma-separated deck IDs (max 4)")):
    """Compare 2-4 decks: common cards, unique cards, color identity overlap."""
    db = await get_db()
    try:
        deck_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deck ID format — provide numeric IDs")
    if len(deck_ids) < 2 or len(deck_ids) > 4:
        raise HTTPException(status_code=400, detail="Provide 2-4 deck IDs")

    # Load deck summaries
    decks = []
    deck_card_sets: dict[int, dict[str, dict]] = {}  # deck_id -> {card_name: card_info}
    deck_colors: dict[int, set[str]] = {}

    for did in deck_ids:
        cursor = await db.execute(
            """SELECT d.*, (SELECT COALESCE(SUM(quantity), 0) FROM deck_cards WHERE deck_id=d.id) as card_count
            FROM decks d WHERE d.id=?""", (did,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Deck {did} not found")
        decks.append(DeckSummary(
            id=row["id"], archidekt_id=row["archidekt_id"], name=row["name"],
            format=row["format"], commander_name=row["commander_name"] or "",
            featured_image=row["featured_image"] or "", card_count=row["card_count"],
            folder_name=row["folder_name"] or "", bracket=row["bracket"] or 0,
            last_synced=row["last_synced"],
        ))

        # Get cards in this deck
        cursor = await db.execute(
            """SELECT c.name, c.set_code, c.image_uri, c.price_eur, c.color_identity
            FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id=?""", (did,)
        )
        cards_in_deck: dict[str, dict] = {}
        colors: set[str] = set()
        for r in await cursor.fetchall():
            cards_in_deck[r["name"]] = {
                "name": r["name"], "set_code": r["set_code"] or "",
                "image_uri": r["image_uri"] or "", "price_eur": r["price_eur"] or "",
            }
            for c in json.loads(r["color_identity"] or "[]"):
                colors.add(c)
        deck_card_sets[did] = cards_in_deck
        deck_colors[did] = colors

    # Common cards (in ALL decks)
    all_names = [set(deck_card_sets[did].keys()) for did in deck_ids]
    common_names = set.intersection(*all_names) if all_names else set()
    # Use first deck's card info for common cards
    common_cards = [CardSummary(**deck_card_sets[deck_ids[0]][n]) for n in sorted(common_names)]

    # Pairwise overlap
    pairwise = []
    for i in range(len(deck_ids)):
        for j in range(i + 1, len(deck_ids)):
            a, b = deck_ids[i], deck_ids[j]
            overlap = set(deck_card_sets[a].keys()) & set(deck_card_sets[b].keys())
            pairwise.append(PairwiseOverlap(
                deck_a=a, deck_b=b,
                overlap_count=len(overlap),
                overlap_cards=sorted(overlap),
            ))

    # Unique to each deck
    unique_to: dict[int, list[CardSummary]] = {}
    for did in deck_ids:
        others = set()
        for other_id in deck_ids:
            if other_id != did:
                others.update(deck_card_sets[other_id].keys())
        unique_names = set(deck_card_sets[did].keys()) - others
        unique_to[did] = [CardSummary(**deck_card_sets[did][n]) for n in sorted(unique_names)]

    # Color identity intersection/union
    all_color_sets = [deck_colors[did] for did in deck_ids]
    color_union = sorted(set.union(*all_color_sets)) if all_color_sets else []
    color_intersection = sorted(set.intersection(*all_color_sets)) if all_color_sets else []

    return DeckCompareResponse(
        decks=decks,
        common_cards=common_cards,
        pairwise_overlap=pairwise,
        unique_to=unique_to,
        color_identity_intersection=color_intersection,
        color_identity_union=color_union,
    )


@router.get("/{deck_id}", response_model=DeckDetail)
async def get_deck(deck_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM decks WHERE id=?", (deck_id,))
    deck = await cursor.fetchone()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    cursor = await db.execute(
        """SELECT c.*, dc.quantity, dc.category, dc.is_commander,
        dc.is_companion, dc.modifier
        FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id=? ORDER BY dc.category, c.name""",
        (deck_id,),
    )
    card_rows = await cursor.fetchall()

    cards = []
    for r in card_rows:
        card = CardResponse(
            id=r["id"], scryfall_id=r["scryfall_id"], oracle_id=r["oracle_id"],
            name=r["name"], mana_cost=r["mana_cost"], cmc=r["cmc"],
            type_line=r["type_line"], oracle_text=r["oracle_text"],
            colors=json.loads(r["colors"] or "[]"),
            color_identity=json.loads(r["color_identity"] or "[]"),
            set_code=r["set_code"], set_name=r["set_name"],
            collector_number=r["collector_number"], rarity=r["rarity"],
            image_uri=r["image_uri"], image_art_crop=r["image_art_crop"],
            power=r["power"], toughness=r["toughness"], loyalty=r["loyalty"],
            keywords=json.loads(r["keywords"] or "[]"),
            edhrec_rank=r["edhrec_rank"],
            price_usd=r["price_usd"], price_eur=r["price_eur"],
            price_usd_foil=r["price_usd_foil"], price_eur_foil=r["price_eur_foil"],
            updated_at=r["updated_at"],
        )
        cards.append(DeckCardEntry(
            card=card, quantity=r["quantity"], category=r["category"] or "",
            is_commander=bool(r["is_commander"]),
            is_companion=bool(r["is_companion"]),
            modifier=r["modifier"] or "Normal",
        ))

    return DeckDetail(
        id=deck["id"], archidekt_id=deck["archidekt_id"], name=deck["name"],
        format=deck["format"], description=deck["description"],
        featured_image=deck["featured_image"] or "",
        commander_name=deck["commander_name"] or "",
        owner_username=deck["owner_username"] or "",
        bracket=deck["bracket"] or 0,
        user_bracket=deck["user_bracket"],
        gameplan=deck["gameplan"] or "",
        ai_assessment=deck["ai_assessment"] or "",
        ai_assessment_updated_at=deck["ai_assessment_updated_at"],
        view_count=deck["view_count"], created_at=deck["created_at"],
        updated_at=deck["updated_at"], last_synced=deck["last_synced"],
        cards=cards,
    )


@router.put("/{deck_id}/user-fields", response_model=DeckDetail)
async def update_deck_user_fields(deck_id: int, body: DeckUserFieldsUpdate):
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    fields = []
    params: list = []
    if body.user_bracket is not None:
        fields.append("user_bracket = ?")
        params.append(body.user_bracket)
    elif body.model_fields_set and "user_bracket" in body.model_fields_set:
        # Explicitly set to null
        fields.append("user_bracket = NULL")
    if body.gameplan is not None:
        fields.append("gameplan = ?")
        params.append(body.gameplan)

    if fields:
        params.append(deck_id)
        await db.execute(f"UPDATE decks SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()

    return await get_deck(deck_id)


@router.get("/{deck_id}/combos", response_model=list[DeckCombo])
async def get_deck_combos(deck_id: int, include_partial: bool = True):
    """Get cached combos for a deck."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    where = "WHERE deck_id = ?" if include_partial else "WHERE deck_id = ? AND is_partial = 0"
    cursor = await db.execute(
        f"SELECT * FROM deck_combos {where} ORDER BY is_partial, name",
        (deck_id,),
    )
    rows = await cursor.fetchall()
    return [
        DeckCombo(
            id=r["id"],
            combo_id=r["combo_id"],
            name=r["name"] or "",
            color_identity=r["color_identity"] or "",
            cards=json.loads(r["cards_json"] or "[]"),
            result=json.loads(r["result_json"] or "[]"),
            prerequisites=r["prerequisites"] or "",
            steps=r["steps"] or "",
            is_partial=bool(r["is_partial"]),
            missing_cards=json.loads(r["missing_cards_json"] or "[]"),
        )
        for r in rows
    ]


@router.post("/{deck_id}/combos/sync")
async def sync_deck_combos(deck_id: int):
    """Manually trigger a combo re-sync from Spellbook."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    from ..services.combo_sync import sync_combos_for_deck
    count = await sync_combos_for_deck(deck_id)
    return {"count": count}


@router.get("/{deck_id}/completeness", response_model=DeckCompletenessResponse)
async def get_deck_completeness(deck_id: int):
    """Get deck completeness: how many cards are owned vs needed."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    # Get unique cards in deck with quantities
    cursor = await db.execute(
        """SELECT c.name, dc.quantity, c.price_eur,
           COALESCE((SELECT SUM(col.quantity + col.foil_quantity)
                     FROM collection col WHERE col.card_id = c.id), 0) as owned
        FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ?
        ORDER BY c.name""",
        (deck_id,),
    )
    rows = await cursor.fetchall()

    total_unique = len(rows)
    owned_unique = 0
    missing_cards: list[MissingCard] = []
    total_cost = 0.0

    for r in rows:
        owned = r["owned"]
        needed = r["quantity"]
        if owned >= needed:
            owned_unique += 1
        else:
            price = float(r["price_eur"]) if r["price_eur"] else 0.0
            missing_qty = needed - owned
            cost = price * missing_qty
            total_cost += cost
            missing_cards.append(MissingCard(
                name=r["name"],
                quantity_needed=missing_qty,
                current_market_price_eur=price,
            ))

    completeness_pct = (owned_unique / total_unique * 100) if total_unique > 0 else 100.0
    most_expensive = sorted(missing_cards, key=lambda m: m.current_market_price_eur, reverse=True)[:5]

    return DeckCompletenessResponse(
        deck_id=deck_id,
        total_unique_cards=total_unique,
        owned_unique=owned_unique,
        completeness_pct=round(completeness_pct, 1),
        missing_cards=missing_cards,
        total_acquisition_cost_eur=round(total_cost, 2),
        most_expensive_missing=most_expensive,
    )


# --- Deck Performance Tracker ---

def _game_row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "deck_id": r["deck_id"],
        "played_at": r["played_at"],
        "result": r["result"],
        "opponents": r["opponents"] or "",
        "pod_size": r["pod_size"],
        "on_play": bool(r["on_play"]),
        "mulligans": r["mulligans"],
        "missed_land_drops": r["missed_land_drops"],
        "turns": r["turns"],
        "what_worked": r["what_worked"] or "",
        "what_didnt": r["what_didnt"] or "",
        "notes": r["notes"] or "",
        "created_at": r["created_at"],
    }


async def _ensure_deck(db, deck_id: int) -> None:
    cursor = await db.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")


async def _fetch_games(db, deck_id: int) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM deck_games WHERE deck_id = ? ORDER BY played_at DESC, id DESC",
        (deck_id,),
    )
    return [_game_row_to_dict(r) for r in await cursor.fetchall()]


@router.get("/{deck_id}/games", response_model=list[DeckGame])
async def list_deck_games(deck_id: int):
    db = await get_db()
    await _ensure_deck(db, deck_id)
    return [DeckGame(**g) for g in await _fetch_games(db, deck_id)]


@router.post("/{deck_id}/games", response_model=DeckGame)
async def add_deck_game(deck_id: int, body: DeckGameCreate):
    db = await get_db()
    await _ensure_deck(db, deck_id)
    played_at = body.played_at.strip() or date.today().isoformat()
    cursor = await db.execute(
        """INSERT INTO deck_games
        (deck_id, played_at, result, opponents, pod_size, on_play,
         mulligans, missed_land_drops, turns, what_worked, what_didnt, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (deck_id, played_at, body.result, body.opponents, body.pod_size,
         int(body.on_play), body.mulligans, body.missed_land_drops, body.turns,
         body.what_worked, body.what_didnt, body.notes),
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM deck_games WHERE id = ?", (cursor.lastrowid,))
    return DeckGame(**_game_row_to_dict(await cursor.fetchone()))


@router.patch("/{deck_id}/games/{game_id}", response_model=DeckGame)
async def update_deck_game(deck_id: int, game_id: int, body: DeckGameUpdate):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM deck_games WHERE id = ? AND deck_id = ?", (game_id, deck_id)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Game not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No fields to update")
    fields = []
    params: list = []
    for key, val in data.items():
        if key == "on_play" and val is not None:
            val = int(val)
        fields.append(f"{key} = ?")
        params.append(val)
    params.append(game_id)
    await db.execute(f"UPDATE deck_games SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    cursor = await db.execute("SELECT * FROM deck_games WHERE id = ?", (game_id,))
    return DeckGame(**_game_row_to_dict(await cursor.fetchone()))


@router.delete("/{deck_id}/games/{game_id}")
async def delete_deck_game(deck_id: int, game_id: int):
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM deck_games WHERE id = ? AND deck_id = ?", (game_id, deck_id)
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Game not found")
    return {"ok": True}


@router.get("/{deck_id}/performance", response_model=DeckPerformanceStats)
async def deck_performance(deck_id: int):
    db = await get_db()
    await _ensure_deck(db, deck_id)
    games = await _fetch_games(db, deck_id)
    return DeckPerformanceStats(**compute_performance_stats(games))
