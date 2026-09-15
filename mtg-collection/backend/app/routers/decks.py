"""Deck API routes."""
import json
from datetime import date
from fastapi import APIRouter, HTTPException, Query, Response
from ..database import get_db
from ..models.schemas import (
    DeckSummary, DeckDetail, DeckCardEntry, CardResponse, DeckUserFieldsUpdate,
    DeckCombo, DeckCompareResponse, DeckCompletenessResponse, MissingCard,
    CardSummary, PairwiseOverlap, FormatRules,
    DeckGame, DeckGameCreate, DeckGameUpdate, DeckPerformanceStats,
)
from ..services import formats
from ..services.queries import (
    binds_effective,
    legality_push_effective,
    parse_color_identity,
    query_all_decks,
)
from ..services.deck_performance import compute_performance_stats
from ..services.bracket import effective_bracket

router = APIRouter()


def _col(row, name):
    """Read a column that a very old database may not carry yet."""
    return row[name] if name in row.keys() else None


def _json_col(row, name):
    raw = _col(row, name)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _row_board(row) -> str:
    """The card's pile, defaulting to 'main' on a database that predates it."""
    return (_col(row, "board") or "main")


@router.get("/", response_model=list[DeckSummary])
async def list_decks(response: Response):
    response.headers["Cache-Control"] = "public, max-age=30"
    db = await get_db()
    decks = await query_all_decks(db)
    return [DeckSummary(**d) for d in decks]


@router.post("/combos/sync-all")
async def sync_all_deck_combos(
    max_decks: int = Query(0, description="0 = every deck that is due"),
    force: bool = Query(False, description="Ignore the per-deck stamp and ask about all"),
):
    """Ask Spellbook about every deck whose combo cache is missing or stale.

    Declared before the `/{deck_id}` routes so that "combos" is never read as a
    deck id. The sync runs this itself after every run; this is the way to
    catch the whole shelf up in one go.
    """
    from ..services.combo_sync import sync_combos_for_stale_decks
    return await sync_combos_for_stale_decks(max_decks=max_decks or None, force=force)


@router.post("/bracket/recompute-all")
async def recompute_all_brackets():
    """Recompute every deck's bracket from the cached inputs.

    No network: game changers, combos and the card classification are already
    in the database. Declared before the `/{deck_id}` routes.
    """
    from ..services.bracket import compute_brackets_for_all_decks
    return await compute_brackets_for_all_decks()


@router.post("/power/recompute-all")
async def recompute_all_power_levels():
    """Recompute every deck's power score. Local arithmetic, no network."""
    from ..services.power_level import compute_power_for_all_decks
    return await compute_power_for_all_decks()


@router.post("/legality/recheck-all")
async def recheck_all_legality():
    """Re-check every deck against its format's rules. Local SQL, no network.

    Declared before the `/{deck_id}` routes, like the other sweep endpoints, so
    "legality" can never be read as a deck id.
    """
    from ..services import legality

    result = await legality.check_all_decks()
    # The per-deck results are large and a caller asking for a sweep wants the
    # summary; `GET /{id}/legality` has the detail.
    return {k: v for k, v in result.items() if k != "results"}


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
            for c in parse_color_identity(r["color_identity"]):
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

    from ..services.queries import token_exclusion_sql
    cursor = await db.execute(
        f"""SELECT c.*, dc.quantity, dc.category, dc.board, dc.is_commander,
        dc.is_companion, dc.modifier
        FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id=? AND {token_exclusion_sql("c")}
        ORDER BY dc.category, c.name""",
        (deck_id,),
    )
    card_rows = await cursor.fetchall()

    cards = []
    for r in card_rows:
        card = CardResponse(
            id=r["id"], scryfall_id=r["scryfall_id"], oracle_id=r["oracle_id"],
            name=r["name"], mana_cost=r["mana_cost"], cmc=r["cmc"],
            type_line=r["type_line"], oracle_text=r["oracle_text"],
            colors=parse_color_identity(r["colors"]),
            color_identity=parse_color_identity(r["color_identity"]),
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
            board=_row_board(r),
            is_commander=bool(r["is_commander"]),
            is_companion=bool(r["is_companion"]),
            modifier=r["modifier"] or "Normal",
        ))

    _power = formats.power_applies(deck["format"])
    main_cards = [c for c in cards if c.board == "main"]
    mismatch = formats.check_shape(
        deck["format"],
        total_cards=sum(c.quantity for c in main_cards),
        distinct_cards=len(main_cards),
        has_commander_card=any(c.is_commander for c in cards),
    )

    return DeckDetail(
        id=deck["id"], archidekt_id=deck["archidekt_id"], name=deck["name"],
        format=deck["format"],
        archidekt_format_id=_col(deck, "archidekt_format_id"),
        format_rules=FormatRules(**formats.rules_payload(deck["format"])),
        format_mismatch=mismatch,
        description=deck["description"],
        featured_image=deck["featured_image"] or "",
        commander_name=deck["commander_name"] or "",
        owner_username=deck["owner_username"] or "",
        bracket=deck["bracket"] or 0,
        user_bracket=deck["user_bracket"],
        computed_bracket=_col(deck, "computed_bracket"),
        # The format gate lives inside `effective_bracket` so that this caller
        # and the deck list cannot disagree — they did, for one deploy.
        effective_bracket=effective_bracket(
            deck["user_bracket"], _col(deck, "computed_bracket"), deck["bracket"],
            deck["format"],
        ),
        computed_bracket_detail=(
            _json_col(deck, "computed_bracket_detail")
            if formats.bracket_applies(deck["format"]) else None
        ),
        # Same gate as the bracket: a stored score outlives a format change
        # until the next recompute, and must not be shown in the meantime.
        power_score=_col(deck, "power_score") if _power else None,
        power_level=_col(deck, "power_level") if _power else None,
        power_detail=_json_col(deck, "power_detail") if _power else None,
        spellbook_bracket_tag=(
            _col(deck, "spellbook_bracket_tag") or ""
            if formats.bracket_applies(deck["format"]) else ""
        ),
        gameplan=deck["gameplan"] or "",
        # Derived and decided, side by side. `binds_effective` is the one
        # rule; nobody outside it needs to know which folder means what.
        binds_copies=binds_effective(deck),
        binds_copies_override=(
            None if _col(deck, "binds_copies_override") is None
            else bool(_col(deck, "binds_copies_override"))
        ),
        # The second folder-derived decision, built and read exactly like the
        # first. It silences the notification, never the check below it.
        legality_push=legality_push_effective(deck),
        legality_push_override=(
            None if _col(deck, "legality_push_override") is None
            else bool(_col(deck, "legality_push_override"))
        ),
        folder_name=deck["folder_name"] or "",
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
    # Only ever the override column. The derived `binds_copies` belongs to the
    # sync, and a hand-made decision that the next sync silently undoes is
    # worse than no decision at all.
    if "binds_copies_override" in body.model_fields_set:
        if body.binds_copies_override is None:
            fields.append("binds_copies_override = NULL")
        else:
            fields.append("binds_copies_override = ?")
            params.append(1 if body.binds_copies_override else 0)
    if "legality_push_override" in body.model_fields_set:
        if body.legality_push_override is None:
            fields.append("legality_push_override = NULL")
        else:
            fields.append("legality_push_override = ?")
            params.append(1 if body.legality_push_override else 0)

    if fields:
        params.append(deck_id)
        await db.execute(f"UPDATE decks SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()

    return await get_deck(deck_id)


@router.get("/{deck_id}/combos", response_model=list[DeckCombo])
async def get_deck_combos(deck_id: int, include_partial: bool = True):
    """Get cached combos for a deck.

    Partial combos carry `missing_not_legal` and `completable`: Spellbook does
    not know the deck's format, so a combo one banned card short looks exactly
    like a real upgrade until someone checks by hand.
    """
    db = await get_db()
    cursor = await db.execute("SELECT id, format FROM decks WHERE id=?", (deck_id,))
    deck_row = await cursor.fetchone()
    if not deck_row:
        raise HTTPException(status_code=404, detail="Deck not found")

    where = "WHERE deck_id = ?" if include_partial else "WHERE deck_id = ? AND is_partial = 0"
    cursor = await db.execute(
        f"SELECT * FROM deck_combos {where} ORDER BY is_partial, name",
        (deck_id,),
    )
    rows = await cursor.fetchall()
    combos = [
        {
            "id": r["id"],
            "combo_id": r["combo_id"],
            "name": r["name"] or "",
            "color_identity": r["color_identity"] or "",
            "cards": json.loads(r["cards_json"] or "[]"),
            "result": json.loads(r["result_json"] or "[]"),
            "prerequisites": r["prerequisites"] or "",
            "steps": r["steps"] or "",
            "is_partial": bool(r["is_partial"]),
            "missing_cards": json.loads(r["missing_cards_json"] or "[]"),
        }
        for r in rows
    ]

    from ..services.legality import annotate_combos
    return [DeckCombo(**c) for c in await annotate_combos(deck_row["format"], combos)]


@router.post("/{deck_id}/combos/sync")
async def sync_deck_combos(deck_id: int):
    """Manually trigger a combo re-sync from Spellbook."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    from ..services.combo_sync import sync_combos_for_deck
    try:
        count = await sync_combos_for_deck(deck_id)
    except Exception as exc:
        # A Spellbook outage used to come back as `{"count": 0}`, which reads as
        # "this deck has no combos". 502 says which of the two it is.
        raise HTTPException(
            status_code=502, detail=f"Spellbook lookup failed: {exc}"
        ) from exc
    return {"count": count}


@router.post("/{deck_id}/bracket/recompute")
async def recompute_deck_bracket(deck_id: int):
    """Recompute one deck's bracket and return the verdict with its evidence."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    from ..services.bracket import compute_bracket
    return await compute_bracket(deck_id)


@router.post("/{deck_id}/power/recompute")
async def recompute_deck_power(deck_id: int):
    """Recompute one deck's power score and return it with its working."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    from ..services.power_level import compute_power_level
    return await compute_power_level(deck_id)


@router.get("/{deck_id}/power/reference-url")
async def deck_power_reference_url(deck_id: int):
    """The edhpowerlevel.com link for this deck, to check the port against.

    The original runs client-side in a browser, so this is the only way to
    compare: open the link, read its numbers, put them beside ours.
    """
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    from ..services.power_level import reference_url
    return {"url": await reference_url(deck_id)}


@router.get("/{deck_id}/legality")
async def deck_legality(deck_id: int, recheck: bool = Query(False)):
    """Is this deck legal in its own format — size, copies, banned cards.

    Served from the stored answer by default. `recheck=true` recomputes it,
    which is local SQL and cheap; the stored one exists because the answer can
    change without the deck changing, not because computing it is expensive.
    """
    from ..services import legality

    db = await get_db()
    cursor = await db.execute(
        "SELECT legality_json FROM decks WHERE id = ?", (deck_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Deck not found")

    if not recheck:
        cached = legality.stored(_col(row, "legality_json"))
        if cached:
            return cached
    return await legality.check_and_store(deck_id)


@router.get("/{deck_id}/completeness", response_model=DeckCompletenessResponse)
async def get_deck_completeness(deck_id: int):
    """Get deck completeness: how many cards are owned vs needed."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM decks WHERE id=?", (deck_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Deck not found")

    # Cards in this deck, what we own of each, and how many copies *other*
    # binding decks are already using. Basic lands are excluded: they are
    # effectively unlimited and never an acquisition — counting them skewed the
    # percentage and put "Forest ×3" into most_expensive_missing.
    #
    # `bound_elsewhere` is the number this endpoint was missing. Owning four
    # copies means nothing if all four are in another deck, and with playsets
    # that is the normal case rather than an edge one. Counted over
    # `deck_demand`, so a disassembled deck does not "hold" anything.
    from ..services.queries import basic_land_exclusion_sql, token_exclusion_sql
    cursor = await db.execute(
        f"""SELECT c.name, dc.quantity, c.price_eur,
           COALESCE((SELECT SUM(col.quantity + col.foil_quantity)
                     FROM collection col WHERE col.card_id = c.id), 0) as owned,
           COALESCE((SELECT SUM(dd.quantity) FROM deck_demand dd
                     WHERE dd.card_name = c.name AND dd.deck_id != ?), 0) as bound_elsewhere
        FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ? AND COALESCE(dc.board, 'main') IN ('main', 'side')
          AND {basic_land_exclusion_sql('c')} AND {token_exclusion_sql('c')}
        ORDER BY c.name""",
        (deck_id, deck_id),
    )
    rows = await cursor.fetchall()

    total_unique = len(rows)
    owned_unique = 0
    missing_cards: list[MissingCard] = []
    total_cost = 0.0
    blocked_unique = 0

    for r in rows:
        owned = r["owned"]
        needed = r["quantity"]
        bound = r["bound_elsewhere"]

        # Two different questions, and conflating them is how a shopping list
        # sends you out for cards that are in the next deck box over:
        #
        #   "do I own enough"      -> missing_cards, the purchase list
        #   "is enough of it free" -> blocked, a card to move rather than buy
        #
        # Owning four copies means nothing for building *this* deck if all four
        # are in another one — and with playsets that is the normal case.
        if owned >= needed:
            owned_unique += 1
            if owned - bound < needed:
                blocked_unique += 1
        else:
            price = float(r["price_eur"]) if r["price_eur"] else 0.0
            missing_qty = needed - owned
            cost = price * missing_qty
            total_cost += cost
            missing_cards.append(MissingCard(
                name=r["name"],
                quantity_needed=missing_qty,
                current_market_price_eur=price,
                bound_elsewhere=bound,
                owned=owned,
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
        blocked_by_other_decks=blocked_unique,
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


def _refresh_deck_sensors() -> None:
    """Push updated play stats to HA after a game changed (no-op without MQTT)."""
    import asyncio

    from ..services.ha_publisher import publish_deck_sensors

    asyncio.create_task(publish_deck_sensors())


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
    """Log a game from the web UI.

    Writes through `game_log.insert_game` rather than its own INSERT, which is
    what it used to do. That is where the pod-size default and the match
    grouping live, and a second INSERT here would mean the web form quietly
    behaved differently from Home Assistant — the drift that cost 0.45.0 two
    booking paths and 0.47.0 three bracket readers.
    """
    from ..services.game_log import insert_game

    db = await get_db()
    await _ensure_deck(db, deck_id)
    game_id = await insert_game(db, deck_id, body)
    cursor = await db.execute("SELECT * FROM deck_games WHERE id = ?", (game_id,))
    game = DeckGame(**_game_row_to_dict(await cursor.fetchone()))
    _refresh_deck_sensors()
    return game


@router.patch("/{deck_id}/games/{game_id}", response_model=DeckGame)
async def update_deck_game(deck_id: int, game_id: int, body: DeckGameUpdate):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM deck_games WHERE id = ? AND deck_id = ?", (game_id, deck_id)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Game not found")
    from ..services.game_log import renumber_match

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No fields to update")

    # Regrouping by hand is the answer to the 90-minute window being a
    # judgement rather than a rule: two Bo1 games against the same person on
    # the same evening get pulled together, and this is the one click that
    # separates them again. An empty string detaches the game.
    cursor = await db.execute("SELECT match_id FROM deck_games WHERE id = ?", (game_id,))
    old_match = (await cursor.fetchone())["match_id"]
    if "match_id" in data and not data["match_id"]:
        data["match_id"] = None

    fields = []
    params: list = []
    for key, val in data.items():
        if key == "on_play" and val is not None:
            val = int(val)
        fields.append(f"{key} = ?")
        params.append(val)
    params.append(game_id)
    await db.execute(f"UPDATE deck_games SET {', '.join(fields)} WHERE id = ?", params)

    if "match_id" in data:
        # Both sides: the match it left may now hold a single game, and the one
        # it joined has to count again. `game_in_match` is derived, never
        # remembered — a stale number would be a second answer.
        await db.execute(
            "UPDATE deck_games SET game_in_match = NULL WHERE id = ? AND match_id IS NULL",
            (game_id,),
        )
        await renumber_match(db, old_match)
        await renumber_match(db, data["match_id"])
    await db.commit()

    cursor = await db.execute("SELECT * FROM deck_games WHERE id = ?", (game_id,))
    game = DeckGame(**_game_row_to_dict(await cursor.fetchone()))
    _refresh_deck_sensors()
    return game


@router.delete("/{deck_id}/games/{game_id}")
async def delete_deck_game(deck_id: int, game_id: int):
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM deck_games WHERE id = ? AND deck_id = ?", (game_id, deck_id)
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Game not found")
    _refresh_deck_sensors()
    return {"ok": True}


@router.get("/{deck_id}/performance", response_model=DeckPerformanceStats)
async def deck_performance(deck_id: int):
    db = await get_db()
    await _ensure_deck(db, deck_id)
    games = await _fetch_games(db, deck_id)
    return DeckPerformanceStats(**compute_performance_stats(games))
