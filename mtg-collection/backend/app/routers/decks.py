"""Deck API routes."""
import json
from fastapi import APIRouter, HTTPException
from ..database import get_db
from ..models.schemas import DeckSummary, DeckDetail, DeckCardEntry, CardResponse, DeckUserFieldsUpdate
from ..services.queries import query_all_decks

router = APIRouter()


@router.get("/", response_model=list[DeckSummary])
async def list_decks():
    db = await get_db()
    decks = await query_all_decks(db)
    return [DeckSummary(**d) for d in decks]


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
