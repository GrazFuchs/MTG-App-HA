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
  card_id: number;
  collector_number: string;
}

export interface PaginatedDuplicates {
  items: DuplicateEntry[];
  total: number;
  page: number;
  page_size: number;
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
  flaresolverr_configured: boolean;
  flaresolverr_available: boolean;
}

// API calls
export const api = {
  // Decks
  getDecks: () => request<DeckSummary[]>('/api/decks/'),
  getDeck: (id: number) => request<DeckDetail>(`/api/decks/${id}`),

  // Collection
  getCollection: (params?: URLSearchParams) =>
    request<PaginatedCollection>(`/api/collection/?${params?.toString() ?? ''}`),
  deleteCollectionEntry: (id: number) =>
    request<void>(`/api/collection/${id}`, { method: 'DELETE' }),

  // Stats
  getStats: () => request<CollectionStats>('/api/stats/'),

  // Cardmarket
  getCardmarketListings: (params?: URLSearchParams) =>
    request<CardmarketListing[]>(`/api/cardmarket/listings?${params?.toString() ?? ''}`),
  getCardmarketStats: () => request<{ unique_listings: number; total_quantity: number; total_value: number }>('/api/cardmarket/stats'),
  importCardmarketCSV: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/api/cardmarket/import`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(`Import failed: ${res.status}`);
    return res.json();
  },
  syncCardmarket: () => request<{ total_rows: number; imported: number; errors: number }>('/api/cardmarket/sync', { method: 'POST' }),
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

  // Cardmarket add/clear
  addCardmarketListing: (data: { card_name: string; set_name?: string; set_code?: string; quantity: number; price: number; condition: string; language: string; is_foil?: boolean; rarity?: string; comments?: string }) =>
    request<{ status: string }>('/api/cardmarket/add-listing', { method: 'POST', body: JSON.stringify(data) }),
  clearCardmarketListings: () =>
    request<{ status: string }>('/api/cardmarket/clear-listings', { method: 'DELETE' }),
};
