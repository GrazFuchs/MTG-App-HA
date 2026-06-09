// Extract the HA ingress base path (stable across all sub-pages)
// e.g. /api/hassio_ingress/<token>/decks/1 → /api/hassio_ingress/<token>
// For standalone (no ingress): returns ''
function getBasePath(): string {
  const path = window.location.pathname;
  const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
  if (match) return match[1];
  return '';
}
const BASE = getBasePath();

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export interface Card {
  id: number;
  scryfall_id: string;
  name: string;
  mana_cost: string;
  cmc: number;
  type_line: string;
  oracle_text: string;
  colors: string[];
  color_identity: string[];
  set_code: string;
  set_name: string;
  collector_number: string;
  rarity: string;
  image_uri: string;
  image_art_crop: string;
  power: string;
  toughness: string;
  loyalty: string;
  keywords: string[];
  price_usd: string;
  price_eur: string;
  price_usd_foil: string;
  price_eur_foil: string;
}

export interface DeckSummary {
  id: number;
  archidekt_id: number;
  name: string;
  format: string;
  commander_name: string;
  featured_image: string;
  card_count: number;
  folder_name: string;
  bracket: number;
  last_synced: string;
}

export interface DeckCardEntry {
  card: Card;
  quantity: number;
  category: string;
  is_commander: boolean;
}

export interface DeckDetail {
  id: number;
  archidekt_id: number;
  name: string;
  format: string;
  description: string;
  commander_name: string;
  bracket: number;
  user_bracket: number | null;
  gameplan: string;
  ai_assessment: string;
  ai_assessment_updated_at: string | null;
  featured_image: string;
  owner_username: string;
  cards: DeckCardEntry[];
}

export interface CollectionEntry {
  id: number;
  card: Card;
  quantity: number;
  foil_quantity: number;
  condition: string;
  language: string;
  archidekt_tags: string;
  notes: string;
  added_at: string;
  in_decks: number;
  cardmarket_listing_count: number;
  cardmarket_listed_qty: number;
}

export interface PaginatedCollection {
  items: CollectionEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface CollectionSet {
  set_code: string;
  set_name: string;
}

export interface PriceHistoryEntry {
  date: string;
  avg: number;
  low: number;
  trend: number;
  avg1: number;
  avg7: number;
  avg30: number;
}

export interface PriceAlert {
  card_name: string;
  expansion: string;
  set_name: string;
  set_code: string;
  cm_product_id: number;
  trend: number;
  avg30: number;
  spike_pct: number;
  total_owned: number;
  in_decks: number;
  unused_copies: number;
  suggestion: string;
}

export interface CollectionStats {
  total_cards: number;
  unique_cards: number;
  total_value_eur: number;
  total_value_usd: number;
  total_decks: number;
  total_cardmarket_listings: number;
  cardmarket_total_value: number;
}

export type WishlistSource =
  | 'cardmarket' | 'whatnot' | 'booster' | 'trade'
  | 'gift' | 'shop' | 'secret_lair' | 'other';

export type WishlistStatus =
  | 'wanted' | 'ordered' | 'acquired' | 'dropped' | 'not_received';

export interface WishlistItem {
  id: number;
  card_id: number;
  card_name: string;
  scryfall_id: string;
  set_code: string | null;
  set_name: string | null;
  is_foil: boolean;
  quantity: number;
  target_price_eur: number;
  priority: number;
  status: 'wanted' | 'acquired' | 'dropped' | 'not_received';
  deck_id: number | null;
  deck_name: string | null;
  tags: string[];
  notes: string;
  added_at: string;
  acquired_at: string | null;
  current_price_eur: number | null;
  is_deal: boolean;
  image_uri: string | null;
  color_identity: string[];
  // Sprint 9: Acquisition tracking
  is_ordered: boolean;
  ordered_at: string | null;
  expected_price_eur: number | null;
  paid_price_eur: number | null;
  source: WishlistSource | null;
  not_received_at: string | null;
  price_delta_eur: number | null;
  price_delta_pct: number | null;
}

export interface WishlistSummary {
  total_items: number;
  total_quantity: number;
  total_target_eur: number;
  total_current_eur: number;
  items_below_target: number;
  items_above_target: number;
  items_unknown_price: number;
  by_priority: Record<number, number>;
  by_deck: { deck_id: number; deck_name: string; count: number }[];
}

export interface CardPrinting {
  scryfall_id: string;
  set_code: string;
  set_name: string;
  collector_number: string;
  rarity: string;
  released_at: string;
  image_uri: string | null;
  price_eur: number | null;
  price_eur_foil: number | null;
  is_foil_available: boolean;
  is_nonfoil_available: boolean;
}

export interface AcquisitionStats {
  total_acquired: number;
  total_spent_eur: number;
  total_current_value_eur: number;
  by_source: Array<{
    source: string;
    count: number;
    total_spent_eur: number;
    total_current_value_eur: number;
  }>;
  by_month: Array<{
    month: string;
    count: number;
    spent: number;
  }>;
}

// --- Inbox / Triage ---

export interface ExistingPrinting {
  collection_id: number;
  set_code: string;
  set_name: string;
  is_foil: boolean;
  quantity: number;
  foil_quantity: number;
  price_eur: string;
  keep_score: number;
}

export interface TriageSuggestion {
  action: 'keep' | 'sold_new' | 'swap';
  reason: string;
  sell_collection_id: number | null;
  estimated_price_eur: number;
  suggested_sell_price_eur: number;
}

export interface AcquisitionEvent {
  id: number;
  created_at: string;
  qty_delta: number;
  is_foil: boolean;
  condition: string;
  language: string;
  triage_state: string;
  card: Card;
  in_decks: number;
  existing_printings: ExistingPrinting[];
  suggestion: TriageSuggestion;
}

export interface InboxAcquisitionStats {
  pending_count: number;
  decided_last_30d: number;
  by_state_30d: Record<string, number>;
}

export interface PaginatedAcquisitions {
  items: AcquisitionEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface TriageDecisionPayload {
  action: 'keep' | 'sold_new' | 'swap' | 'dismiss';
  source?: string | null;
  listing_price_eur?: number | null;
  listing_condition?: string;
  listing_language?: string;
  listing_quantity?: number;
  sell_qty?: number | null;
  sell_collection_id?: number | null;
  notes?: string;
}

export interface ListingHealthBucket {
  listing_id: number;
  card_name: string;
  my_price: number;
  trend_price: number;
  suggested_price: number;
  delta_pct: number;
}

export interface ListingHealthResponse {
  underpriced: ListingHealthBucket[];
  overpriced: ListingHealthBucket[];
  fair: ListingHealthBucket[];
  no_match: Array<{ listing_id: number; card_name: string; my_price: number }>;
}

// --- Deck Combos ---

export interface DeckCombo {
  id: number;
  combo_id: string;
  name: string;
  color_identity: string;
  cards: string[];
  result: string[];
  prerequisites: string;
  steps: string;
  is_partial: boolean;
  missing_cards: string[];
}

// --- Deck Compare ---

export interface CardSummary {
  name: string;
  set_code: string;
  image_uri: string;
  price_eur: string;
}

export interface DeckCompareResponse {
  decks: DeckSummary[];
  common_cards: CardSummary[];
  pairwise_overlap: Array<{
    deck_a: number;
    deck_b: number;
    overlap_count: number;
    overlap_cards: string[];
  }>;
  unique_to: Record<number, CardSummary[]>;
  color_identity_intersection: string[];
  color_identity_union: string[];
}

// --- Deck Completeness ---

export interface MissingCard {
  name: string;
  quantity_needed: number;
  current_market_price_eur: number;
}

export interface DeckCompletenessResponse {
  deck_id: number;
  total_unique_cards: number;
  owned_unique: number;
  completeness_pct: number;
  missing_cards: MissingCard[];
  total_acquisition_cost_eur: number;
  most_expensive_missing: MissingCard[];
}

// --- Card Search with Owned Indicator ---

export interface CardSearchResult extends Card {
  owned_quantity: number;
  owned_foil_quantity: number;
  in_decks: string[];
}

export interface WishlistAddPayload {
  card_name?: string;
  scryfall_id?: string;
  set_code?: string;
  is_foil?: boolean;
  quantity?: number;
  target_price_eur?: number;
  priority?: number;
  deck_id?: number;
  tags?: string;
  notes?: string;
}

export interface ValueSnapshot {
  date: string;
  total_cards: number;
  unique_cards: number;
  value_eur: number;
  value_usd: number;
}

export interface CardmarketListing {
  id: number;
  card_name: string;
  set_name: string;
  set_code: string;
  quantity: number;
  price: number;
  condition: string;
  language: string;
  is_foil: boolean;
  card: Card | null;
  article_id: string;
  expansion_code: string;
  rarity: string;
  condition_full: string;
  reverse_holo: boolean;
  comments: string;
  product_url: string;
  source: string;
}

export interface DuplicateEntry {
  card_name: string;
  set_name: string;
  set_code: string;
  rarity: string;
  image_uri: string;
  price_eur: string;
  price_eur_foil: string;
  total_copies: number;
  in_decks: number;
  extras: number;
  is_foil: boolean;
  listed_quantity: number;
  extras_after_listings: number;
  card_id: number;
  collector_number: string;
  color_identity: string[];
  type_line: string;
}

export interface PaginatedDuplicates {
  items: DuplicateEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface DuplicatePrinting {
  card_name: string;
  set_name: string;
  set_code: string;
  rarity: string;
  image_uri: string;
  is_foil: boolean;
  price_eur: string;
  price_eur_foil: string;
  total_copies: number;
  in_decks: number;
  total_global: number;
  listed_for_printing: number;
  card_id: number;
  collector_number: string;
}

export interface SyncLogEntry {
  id: number;
  source: string;
  status: string;
  started_at: string;
  finished_at: string;
  items_synced: number;
  error: string;
}

export interface SyncStatus {
  last_sync: SyncLogEntry | null;
  sync_enabled: boolean;
  next_sync_hour: number;
  archidekt_username: string;
  archidekt_authenticated: boolean;
  cardmarket_configured: boolean;
}

export interface MCPSetupInstructions {
  download_url: string;
  config_example: Record<string, unknown>;
  instructions: { step: number; text: string }[];
  config_paths: { macos: string; windows: string; linux: string };
}

// API calls
export const api = {
  // Decks
  getDecks: () => request<DeckSummary[]>('/api/decks/'),
  getDeck: (id: number) => request<DeckDetail>(`/api/decks/${id}`),
  updateDeckUserFields: (deckId: number, fields: { user_bracket?: number | null; gameplan?: string }) =>
    request<DeckDetail>(`/api/decks/${deckId}/user-fields`, {
      method: 'PUT',
      body: JSON.stringify(fields),
    }),

  // Collection
  getCollection: (params?: URLSearchParams) =>
    request<PaginatedCollection>(`/api/collection/?${params?.toString() ?? ''}`),
  deleteCollectionEntry: (id: number) =>
    request<void>(`/api/collection/${id}`, { method: 'DELETE' }),

  // Stats
  getStats: () => request<CollectionStats>('/api/stats/'),
  getValueHistory: (days?: number) =>
    request<ValueSnapshot[]>(`/api/stats/value-history${days ? `?days=${days}` : ''}`),

  // Cardmarket
  getCardmarketListings: (params?: URLSearchParams) =>
    request<{ items: CardmarketListing[]; total: number; page: number; page_size: number }>(`/api/cardmarket/listings?${params?.toString() ?? ''}`),
  getCardmarketStats: () => request<{
    unique_cards: number;
    total_rows: number;
    total_quantity: number;
    total_value: number;
    /** @deprecated use total_rows */
    unique_listings: number;
  }>('/api/cardmarket/stats'),
  importCardmarketCSV: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/api/cardmarket/import`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(`Import failed: ${res.status}`);
    return res.json();
  },
  exportCardmarketCSV: async () => {
    const res = await fetch(`${BASE}/api/cardmarket/export`);
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?(.+?)"?$/);
    const filename = match ? match[1] : `cardmarketUpdate_${new Date().toISOString().slice(0, 10)}.csv`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Sync
  getSyncStatus: () => request<SyncStatus>('/api/sync/status'),
  getSyncHistory: () => request<SyncLogEntry[]>('/api/sync/history'),
  triggerSync: () => request<{ status: string }>('/api/sync/trigger', { method: 'POST' }),
  triggerResync: () => request<{ status: string }>('/api/sync/trigger-resync', { method: 'POST' }),

  // Cards (Scryfall proxy)
  searchCards: (q: string) => request<any>(`/api/cards/search?q=${encodeURIComponent(q)}`),
  autocomplete: (q: string) => request<{ data: string[] }>(`/api/cards/autocomplete?q=${encodeURIComponent(q)}`),

  // Collection sets
  getCollectionSets: () => request<CollectionSet[]>('/api/collection/sets'),
  getCollectionTags: () => request<string[]>('/api/collection/tags'),

  // Cardmarket price data
  getPriceHistory: (cmProductId: number, days?: number) =>
    request<PriceHistoryEntry[]>(`/api/cardmarket/price-history/${cmProductId}${days ? `?days=${days}` : ''}`),
  getPriceAlerts: () => request<PriceAlert[]>('/api/cardmarket/price-alerts'),
  syncPrices: () => request<any>('/api/cardmarket/sync-prices', { method: 'POST' }),
  getMatchedProducts: (search?: string) =>
    request<{ cm_product_id: number; card_name: string; expansion: string }[]>(
      `/api/cardmarket/products${search ? `?search=${encodeURIComponent(search)}` : ''}`
    ),

  // EDHREC
  getEDHRECRecommendations: (commander: string) =>
    request<{ recommendations: any[] }>(`/api/cards/edhrec/recommendations/${encodeURIComponent(commander)}`),
  getEDHRECCombos: (commander: string) =>
    request<{ combos: any[] }>(`/api/cards/edhrec/combos/${encodeURIComponent(commander)}`),

  // Duplicates
  getDuplicates: (params?: URLSearchParams) =>
    request<PaginatedDuplicates>(`/api/collection/duplicates?${params?.toString() ?? ''}`),
  getDuplicateSets: (params?: URLSearchParams) =>
    request<CollectionSet[]>(`/api/collection/duplicates/sets?${params?.toString() ?? ''}`),
  getDuplicatePrintings: (cardName: string) =>
    request<DuplicatePrinting[]>(`/api/collection/duplicates/printings?card_name=${encodeURIComponent(cardName)}`),

  // Cardmarket add/clear
  addCardmarketListing: (data: { card_name: string; set_name?: string; set_code?: string; quantity: number; price: number; condition: string; language: string; is_foil?: boolean; rarity?: string; comments?: string }) =>
    request<{ status: string }>('/api/cardmarket/add-listing', { method: 'POST', body: JSON.stringify(data) }),
  clearCardmarketListings: () =>
    request<{ status: string }>('/api/cardmarket/clear-listings', { method: 'DELETE' }),

  // Wishlist
  getWishlist: (params?: URLSearchParams) =>
    request<WishlistItem[]>(`/api/wishlist/?${params?.toString() ?? ''}`),
  getWishlistSummary: () => request<WishlistSummary>('/api/wishlist/summary'),
  addToWishlist: (payload: WishlistAddPayload) =>
    request<{ item: WishlistItem; warning: string | null }>('/api/wishlist/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateWishlistItem: (id: number, data: Partial<WishlistAddPayload>) =>
    request<WishlistItem>(`/api/wishlist/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeFromWishlist: (id: number) =>
    request<{ ok: boolean }>(`/api/wishlist/${id}`, { method: 'DELETE' }),
  acquireWishlistItem: (id: number, paid_price_eur?: number, source?: WishlistSource, set_code?: string, is_foil?: boolean) =>
    request<{ ok: boolean }>(`/api/wishlist/${id}/acquire`, {
      method: 'POST',
      body: JSON.stringify({ paid_price_eur: paid_price_eur ?? null, source: source ?? null, set_code: set_code ?? null, is_foil: is_foil ?? null }),
    }),
  markWishlistOrdered: (id: number, expected_price_eur?: number, set_code?: string, is_foil?: boolean) =>
    request<{ ok: boolean }>(`/api/wishlist/${id}/order`, {
      method: 'POST',
      body: JSON.stringify({ expected_price_eur: expected_price_eur ?? null, set_code: set_code ?? null, is_foil: is_foil ?? null }),
    }),
  unorderWishlistItem: (id: number) =>
    request<{ ok: boolean }>(`/api/wishlist/${id}/unorder`, { method: 'POST' }),
  markWishlistNotReceived: (id: number) =>
    request<{ ok: boolean }>(`/api/wishlist/${id}/mark-not-received`, { method: 'POST' }),
  getAcquisitionStats: (days = 365) =>
    request<AcquisitionStats>(`/api/wishlist/acquisitions/stats?days=${days}`),
  restoreWishlistItem: (id: number) =>
    request<{ ok: boolean }>(`/api/wishlist/${id}/restore`, { method: 'POST' }),
  getCardPrintings: (cardName: string) =>
    request<CardPrinting[]>(`/api/cards/printings?name=${encodeURIComponent(cardName)}`),

  // MCP Setup
  getMcpSetupInstructions: () => request<MCPSetupInstructions>('/api/mcp/setup-instructions'),

  // Listing health
  getListingHealth: (threshold_pct = 15) =>
    request<ListingHealthResponse>(`/api/cardmarket/listings/health?threshold_pct=${threshold_pct}`),

  // Deck combos
  getDeckCombos: (deckId: number, includePartial = true) =>
    request<DeckCombo[]>(`/api/decks/${deckId}/combos?include_partial=${includePartial}`),
  syncDeckCombos: (deckId: number) =>
    request<{ count: number }>(`/api/decks/${deckId}/combos/sync`, { method: 'POST' }),

  // Deck compare
  compareDecks: (ids: number[]) =>
    request<DeckCompareResponse>(`/api/decks/compare?ids=${ids.join(',')}`),

  // Deck completeness
  getDeckCompleteness: (deckId: number) =>
    request<DeckCompletenessResponse>(`/api/decks/${deckId}/completeness`),

  // Inbox / Acquisitions
  getPendingTriage: (page = 1, pageSize = 20, minValue = 0, filter = '', search = '', color = '', sort = 'newest') => {
    const p = new URLSearchParams({ page: String(page), page_size: String(pageSize), min_value_eur: String(minValue), sort });
    if (filter) p.set('filter', filter);
    if (search) p.set('search', search);
    if (color) p.set('color', color);
    return request<PaginatedAcquisitions>(`/api/acquisitions/pending?${p.toString()}`);
  },
  getInboxStats: () =>
    request<InboxAcquisitionStats>('/api/acquisitions/stats'),
  backfillInboxColors: () =>
    request<{ candidates: number; enriched: number; failed: number }>('/api/acquisitions/backfill-colors', { method: 'POST' }),
  decideTriage: (eventId: number, body: TriageDecisionPayload) =>
    request<{ status: string; event_id: number; triage_state: string }>(`/api/acquisitions/${eventId}/decide`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  undoTriage: (eventId: number) =>
    request<{ status: string; event_id: number }>(`/api/acquisitions/${eventId}/undo`, { method: 'POST' }),
};
