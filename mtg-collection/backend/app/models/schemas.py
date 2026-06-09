"""Pydantic models for API request/response and external data."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator

SOURCE_VALUES = Literal["cardmarket", "whatnot", "booster", "trade", "gift", "shop", "secret_lair", "other"]


# --- Card Models ---

class CardBase(BaseModel):
    scryfall_id: str
    oracle_id: str | None = None
    name: str
    mana_cost: str = ""
    cmc: float = 0
    type_line: str = ""
    oracle_text: str = ""
    colors: list[str] = []
    color_identity: list[str] = []
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    rarity: str = ""
    image_uri: str = ""
    image_art_crop: str = ""
    power: str = ""
    toughness: str = ""
    loyalty: str = ""
    keywords: list[str] = []
    edhrec_rank: int | None = None
    price_usd: str = ""
    price_eur: str = ""
    price_usd_foil: str = ""
    price_eur_foil: str = ""

    @field_validator('mana_cost', 'type_line', 'oracle_text',
                     'set_code', 'set_name', 'collector_number', 'rarity',
                     'image_uri', 'image_art_crop', 'power', 'toughness', 'loyalty',
                     'price_usd', 'price_eur', 'price_usd_foil', 'price_eur_foil',
                     mode='before')
    @classmethod
    def coerce_none_to_empty(cls, v):
        return v if v is not None else ""


class CardResponse(CardBase):
    id: int
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


# --- Deck Models ---

class DeckSummary(BaseModel):
    id: int
    archidekt_id: int | None = None
    name: str
    format: str = ""
    commander_name: str = ""
    featured_image: str = ""
    card_count: int = 0
    folder_name: str = ""
    bracket: int = 0
    last_synced: datetime | None = None


class DeckCardEntry(BaseModel):
    card: CardResponse
    quantity: int = 1
    category: str = ""
    is_commander: bool = False
    is_companion: bool = False
    modifier: str = "Normal"


class DeckDetail(BaseModel):
    id: int
    archidekt_id: int | None = None
    name: str
    format: str = ""
    description: str = ""
    featured_image: str = ""
    commander_name: str = ""
    owner_username: str = ""
    bracket: int = 0
    user_bracket: int | None = None
    gameplan: str = ""
    ai_assessment: str = ""
    ai_assessment_updated_at: datetime | None = None
    view_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_synced: datetime | None = None
    cards: list[DeckCardEntry] = []


class DeckUserFieldsUpdate(BaseModel):
    user_bracket: int | None = Field(None, ge=1, le=5)
    gameplan: str | None = Field(None, max_length=500)


# --- Collection Models ---

class CollectionEntry(BaseModel):
    id: int
    card: CardResponse
    quantity: int = 1
    foil_quantity: int = 0
    condition: str = "NM"
    language: str = "en"
    archidekt_tags: str = ""
    notes: str = ""
    added_at: datetime | None = None
    in_decks: int = 0
    cardmarket_listing_count: int = 0
    cardmarket_listed_qty: int = 0


class CollectionAddRequest(BaseModel):
    scryfall_id: str
    quantity: int = 1
    foil_quantity: int = 0
    condition: str = "NM"
    language: str = "en"
    notes: str = ""


# --- Cardmarket Models ---

class CardmarketListing(BaseModel):
    id: int
    card_name: str
    set_name: str = ""
    set_code: str = ""
    quantity: int = 1
    price: float = 0
    condition: str = ""
    language: str = ""
    is_foil: bool = False
    card_id: int | None = None
    imported_at: datetime | None = None
    article_id: str = ""
    expansion_code: str = ""
    rarity: str = ""
    condition_full: str = ""
    reverse_holo: bool = False
    comments: str = ""
    product_url: str = ""
    source: str = "import"
    card: CardResponse | None = None  # Sprint 13: JOIN on cards for hover preview


class CardmarketImportResult(BaseModel):
    total_rows: int
    imported: int
    errors: int
    error_details: list[str] = []


# --- Sync Models ---

class SyncLogEntry(BaseModel):
    id: int
    source: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    items_synced: int = 0
    error: str = ""


class SyncStatus(BaseModel):
    last_sync: SyncLogEntry | None = None
    sync_enabled: bool = True
    next_sync_hour: int = 3
    archidekt_username: str = ""
    archidekt_authenticated: bool = False
    cardmarket_configured: bool = False
    synced_decks: int = 0


# --- Stats Models ---

class CollectionStats(BaseModel):
    total_cards: int = 0
    unique_cards: int = 0
    total_value_eur: float = 0
    total_value_usd: float = 0
    total_decks: int = 0
    total_cardmarket_listings: int = 0
    cardmarket_total_value: float = 0


# --- EDHREC Models ---

class EDHRECRecommendation(BaseModel):
    name: str
    sanitized: str = ""
    url: str = ""
    inclusion: int = 0
    num_decks: int = 0
    synergy: float = 0
    image_uri: str = ""


class EDHRECCombo(BaseModel):
    cards: list[str] = []
    color_identity: list[str] = []
    result: str = ""
    link: str = ""


# --- Wishlist Models ---

class WishlistItemCreate(BaseModel):
    card_name: str | None = None
    scryfall_id: str | None = None
    set_code: str | None = None
    is_foil: bool = False
    quantity: int = Field(1, ge=1, le=99)
    target_price_eur: float = Field(0, ge=0)
    priority: int = Field(3, ge=1, le=5)
    status: Literal["wanted", "acquired", "dropped", "not_received"] = "wanted"
    deck_id: int | None = None
    tags: str = ""
    notes: str = ""


class WishlistItemUpdate(BaseModel):
    """All fields optional for PATCH semantics."""
    target_price_eur: float | None = Field(None, ge=0)
    priority: int | None = Field(None, ge=1, le=5)
    status: Literal["wanted", "acquired", "dropped", "not_received"] | None = None
    deck_id: int | None = None
    tags: str | None = None
    notes: str | None = None
    quantity: int | None = Field(None, ge=1, le=99)
    set_code: str | None = None
    is_foil: bool | None = None


class WishlistOrderRequest(BaseModel):
    expected_price_eur: float | None = Field(None, ge=0)
    set_code: str | None = None
    is_foil: bool | None = None


class WishlistAcquireRequest(BaseModel):
    paid_price_eur: float | None = Field(None, ge=0)
    source: SOURCE_VALUES | None = None
    set_code: str | None = None
    is_foil: bool | None = None


class WishlistItemResponse(BaseModel):
    id: int
    card_id: int
    card_name: str
    scryfall_id: str
    set_code: str | None = None
    set_name: str | None = None
    is_foil: bool
    quantity: int
    target_price_eur: float
    priority: int
    status: str
    deck_id: int | None = None
    deck_name: str | None = None
    tags: list[str] = []
    notes: str
    added_at: str
    acquired_at: str | None = None
    current_price_eur: float | None = None
    is_deal: bool = False
    image_uri: str | None = None
    color_identity: list[str] = []
    # Sprint 9: Acquisition tracking fields
    is_ordered: bool = False
    ordered_at: str | None = None
    expected_price_eur: float | None = None
    paid_price_eur: float | None = None
    source: str | None = None
    not_received_at: str | None = None
    price_delta_eur: float | None = None
    price_delta_pct: float | None = None


class SourceBucket(BaseModel):
    source: str
    count: int
    total_spent_eur: float
    total_current_value_eur: float


class MonthBucket(BaseModel):
    month: str
    count: int
    spent: float


class AcquisitionStats(BaseModel):
    total_acquired: int
    total_spent_eur: float
    total_current_value_eur: float
    by_source: list[SourceBucket]
    by_month: list[MonthBucket]


class WishlistSummary(BaseModel):
    total_items: int
    total_quantity: int
    total_target_eur: float
    total_current_eur: float
    items_below_target: int
    items_above_target: int
    items_unknown_price: int
    by_priority: dict[int, int] = {}
    by_deck: list[dict] = []


class CardPrinting(BaseModel):
    """A specific set printing of a card from Scryfall."""
    scryfall_id: str
    set_code: str
    set_name: str
    collector_number: str
    rarity: str
    released_at: str
    image_uri: str | None = None
    price_eur: float | None = None
    price_eur_foil: float | None = None
    is_foil_available: bool = False
    is_nonfoil_available: bool = False


# --- Deck Combo Models ---

class DeckCombo(BaseModel):
    id: int
    combo_id: str
    name: str = ""
    color_identity: str = ""
    cards: list[str] = []
    result: list[str] = []
    prerequisites: str = ""
    steps: str = ""
    is_partial: bool = False
    missing_cards: list[str] = []


# --- Deck Compare Models ---

class CardSummary(BaseModel):
    name: str
    set_code: str = ""
    image_uri: str = ""
    price_eur: str = ""


class PairwiseOverlap(BaseModel):
    deck_a: int
    deck_b: int
    overlap_count: int
    overlap_cards: list[str] = []


class DeckCompareResponse(BaseModel):
    decks: list[DeckSummary]
    common_cards: list[CardSummary]
    pairwise_overlap: list[PairwiseOverlap]
    unique_to: dict[int, list[CardSummary]]
    color_identity_intersection: list[str]
    color_identity_union: list[str]


# --- Deck Completeness Models ---

class MissingCard(BaseModel):
    name: str
    quantity_needed: int = 1
    current_market_price_eur: float = 0


class DeckCompletenessResponse(BaseModel):
    deck_id: int
    total_unique_cards: int
    owned_unique: int
    completeness_pct: float
    missing_cards: list[MissingCard]
    total_acquisition_cost_eur: float
    most_expensive_missing: list[MissingCard]


# --- Card Search Owned Indicator ---

class CardSearchResult(BaseModel):
    """Extended card result with ownership info."""
    id: int
    scryfall_id: str
    name: str
    mana_cost: str = ""
    cmc: float = 0
    type_line: str = ""
    oracle_text: str = ""
    colors: list[str] = []
    color_identity: list[str] = []
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    rarity: str = ""
    image_uri: str = ""
    image_art_crop: str = ""
    power: str = ""
    toughness: str = ""
    loyalty: str = ""
    keywords: list[str] = []
    price_usd: str = ""
    price_eur: str = ""
    price_usd_foil: str = ""
    price_eur_foil: str = ""
    owned_quantity: int = 0
    owned_foil_quantity: int = 0
    in_decks: list[str] = []


# --- Acquisition / Inbox Triage Models ---

TRIAGE_STATE = Literal["pending", "keep", "sold_new", "swapped", "dismissed"]


class ExistingPrinting(BaseModel):
    collection_id: int
    set_code: str
    set_name: str
    is_foil: bool
    quantity: int
    foil_quantity: int
    price_eur: str
    keep_score: float


class TriageSuggestion(BaseModel):
    action: Literal["keep", "sold_new", "swap"]
    reason: str
    sell_collection_id: int | None = None
    estimated_price_eur: float
    suggested_sell_price_eur: float = 0.0


class AcquisitionEventResponse(BaseModel):
    id: int
    created_at: datetime
    qty_delta: int
    is_foil: bool
    condition: str
    language: str
    triage_state: str
    card: CardResponse
    in_decks: int
    existing_printings: list[ExistingPrinting]
    suggestion: TriageSuggestion


class TriageDecisionRequest(BaseModel):
    action: Literal["keep", "sold_new", "swap", "dismiss"]
    source: SOURCE_VALUES | None = None
    listing_price_eur: float | None = Field(None, ge=0)
    listing_condition: str | None = "NM"
    listing_language: str | None = "English"
    listing_quantity: int | None = Field(1, ge=1)
    sell_qty: int | None = Field(None, ge=1)  # partial sell for sold_new
    sell_collection_id: int | None = None
    notes: str | None = ""


class InboxAcquisitionStats(BaseModel):
    pending_count: int
    decided_last_30d: int
    by_state_30d: dict[str, int]
