## 0.15.0

### Performance
- **SQLite WAL + PRAGMA tuning**: `journal_mode=WAL`, `synchronous=NORMAL`, `cache_size=-20000` (20 MB page cache), `temp_store=MEMORY` applied to every connection.
- **Connection pool** raised from 2 → 6 concurrent DB connections.
- **Migration 14**: 5 new indices (`idx_cards_name_nocase`, `idx_cards_set_code`, `idx_deck_cards_card_id`, `idx_collection_card_id`, `idx_cardmarket_listings_card_name`) + `ANALYZE`.
- **GZip middleware** (`minimum_size=1000`) compresses API payloads by ~60–80%.
- **Cache-Control headers** on hot read endpoints: `/collection/sets` (60 s), `/decks/`, `/stats/`, `/cardmarket/stats` (30 s each).
- **React Query migration**: All 8 pages (Collection, DeckView, Decks, Cardmarket, Duplicates, Settings, Dashboard, Inbox) fully migrated to `useQuery`/`useMutation`. Zero legacy `useEffect` data-fetchers remaining. QueryClient defaults: `staleTime=30s`, `gcTime=5min`, `retry=1`, `refetchOnWindowFocus=false`, `keepPreviousData`.
- **Deck prefetch on hover**: `Decks.tsx` prefetches deck detail on mouse-enter via `queryClient.prefetchQuery`.

### Fixed
- **Cardmarket stats**: `/api/cardmarket/stats` now correctly distinguishes `unique_cards` (`COUNT(DISTINCT card_name)`) from `total_rows` (raw listing count). Header shows "X CARDS · Y LISTINGS · Z COPIES". `unique_listings` retained as deprecated backward-compat field.
- **Cardmarket search regression**: Each keystroke no longer fires an API request — search is committed on Enter only (`searchInput` / `committedSearch` split).

## 0.14.1

### Fixed
- **Inbox White-Screen Crash** (`TypeError: undefined is not an object`): `getColorBucket` now handles null/undefined cards, null/empty/JSON-array-string/concatenated-letter (`WU`) color identities without throwing. Root cause was `Map.get(undefined).push()` when a card had a malformed or missing `color_identity`.
- **`groupByColorBucket`** pre-initialises all 8 `BucketKey` slots so `.get()` can never return `undefined`.
- **`Duplicates.tsx`** migrated to `getColorBucketLegacy` — no type regression.

### Added
- **`ErrorBoundary` component** (`frontend/src/components/ErrorBoundary.tsx`): Class component with `getDerivedStateFromError`, `componentDidCatch`, and a `retry()` callback; wraps the Inbox list as defense-in-depth so a single render error cannot white-screen the whole page.
- **`BucketKey` type + `BUCKET_KEYS` + `groupByColorBucket`** exported from `utils/colors.ts`.
- **Vitest** added to frontend devDependencies (`npm test`) with 16 regression tests covering all `color_identity` edge cases — all green.

## 0.14.0

### Fixed
- **Schema-Drift Fix** (`triage_advisor.py`): Column names corrected — `cph.trend_eur` → `cph.trend`, `cph.snapshot_at` → `cph.date`. Resolves `/api/acquisitions/pending` returning HTTP 500 and Inbox showing empty despite 190+ pending cards.

### Added
- **Graceful Triage Fallback**: `get_suggestion()` wrapped in `try/except` — `sqlite3.OperationalError` and unexpected exceptions are caught, logged via `logger.error/exception`, and a safe `DEFAULT_SUGGESTION` (action: `keep`) is returned. Schema drift in future sprints can no longer crash the entire `/pending` route.
- **Inbox ErrorBanner**: Inbox page now distinguishes three states: (1) truly empty (celebration 🎉), (2) `loadError` or items/stats mismatch → `ErrorBanner` with pending count and Retry button, (3) normal items list. Prevents misleading "Inbox zero" when the backend fails.
- **ErrorBanner Component** (`frontend/src/components/ErrorBanner.tsx`): Reusable Fluent UI `MessageBar`-based error display with title, message, and optional action slot.
- **Acquisition Smoke Tests** (`backend/tests/test_acquisitions_smoke.py`): Two `pytest-asyncio` tests asserting `/api/acquisitions/pending` and `/api/acquisitions/stats` return HTTP 200 with correct response shapes against an in-memory SQLite DB.
- **`requirements-dev.txt`**: New file — `pytest>=8`, `pytest-asyncio>=0.23`, `httpx>=0.27` for backend test runs.
- **i18n**: 4 new keys per language — `inbox.empty_celebration`, `inbox.error.title`, `inbox.error.api_failed`, `common.retry` (EN + DE).

## 0.13.0

### Added
- **Sprint 13 — Triage Polish, Categorization & Hover-Fix**
- **CardHoverPreview Refactor**: Portal-based hover preview (`createPortal` → `document.body`), z-index 2147483000 — survives all Fluent UI dialogs; auto-hides on scroll/resize; 200 ms show delay; bounds-checked with oracle-text height
- **Sibling-Aware Triage**: Advisor detects earlier pending events for the same card (`ae.id < current`) and factors them into sell/keep logic — prevents double-keep on batch imports
- **Sell Price Pre-Fill**: Triage dialog pre-fills price from Cardmarket trend price (falls back to Scryfall EUR); hint text shown below field; uses `triage.sell_price_hint` i18n key
- **Multi-Copy Sell Qty**: `sold_new` triage exposes quantity selector (1…qty_delta) when more than one copy arrived; `sell_qty` validated server-side (422 if > qty_delta)
- **Inbox Filter Bar**: Three filter pills — All / Suggested: Sell / Suggested: Keep — URL-persistent via `useSearchParams`
- **Inbox Color-Grouping**: Events grouped by MTG color bucket (W/U/B/R/G/M/C/L), collapsible sections, collapse state persisted in localStorage
- **Duplicates Page Filter+Group+Sort**: Search, color dropdown, set dropdown, group-by (None/Color/Set), sort (value/extras/name/set/color) — all URL-persistent
- **Cardmarket Listings Filter**: Color, set, source (Draft/Imported), sort dropdowns; Pending-first split renders Draft and Live sections separately; card name wrapped in `CardHoverPreview`
- **`secret_lair` Source**: Added to `SOURCE_VALUES`, `WishlistSource`, `SourcePicker`, and `WishlistAcquireDialog`
- **`utils/colors.ts`**: New shared `getColorBucket` utility + `BUCKET_ORDER/LABELS/EMOJI` constants
- **i18n**: 20 new keys in EN + DE (inbox filters, color labels, triage hints, source, duplicates group-by, cardmarket sections)

### Fixed
- `TriageDecisionDialog` price hint now uses `t('triage.sell_price_hint')` instead of hardcoded English string
- Added `CREATE INDEX idx_cards_name_lower ON cards(name COLLATE NOCASE)` for sibling query and listings JOIN performance

## 0.12.0

### Added
- **Inbox & Triage Workflow** (Sprint 12): Triage newly acquired cards detected during Archidekt sync — keep, sell, swap, or dismiss with one click
- **Delta Detection**: Collection sync now snapshots quantities before sync and generates acquisition events for positive deltas (skipped on first sync and full resync)
- **Triage Advisor**: Automated keep-score engine comparing printings by price and foil status — suggests keep/swap/sell with reasoning
- **Acquisition Events API**: 4 REST endpoints — `GET /api/acquisitions/pending` (paginated), `GET /api/acquisitions/stats`, `POST /api/acquisitions/{id}/decide`, `POST /api/acquisitions/{id}/undo`
- **Inbox Page**: Full triage UI with value filter, pagination, source picker (sessionStorage-persistent), skip functionality, and empty state
- **AcquisitionCard Component**: Card detail with existing printings, deck usage, suggestion display, and action buttons
- **TriageDecisionDialog**: Modal for editing listing price/condition/language before creating Cardmarket listing
- **Collection CM-Badge**: 🛒 badge on collection entries with active Cardmarket listings (LEFT JOIN on `cardmarket_listings`)
- **Nav Badge**: Pending triage count in navigation with 60s polling + `visibilitychange` refresh
- **2 new MCP Tools**: `get_pending_triage`, `decide_triage`

### Changed
- `sync_collection()` accepts `is_resync` parameter to suppress event generation during full resyncs
- `run_full_resync()` passes `is_resync=True` through to `sync_collection()`
- Collection API enriched with `cardmarket_listing_count` and `cardmarket_listed_qty` per entry

### Technical
- Schema Migration #13: `acquisition_events` table with 13 columns, 2 indexes (`idx_acq_pending`, `idx_acq_card`)
- `backend/app/services/triage_advisor.py` — isolated suggestion engine (no router dependencies)
- `backend/app/routers/acquisitions.py` — triage REST API with cross-field validation
- `frontend/src/pages/Inbox.tsx`, `frontend/src/components/inbox/AcquisitionCard.tsx`, `TriageDecisionDialog.tsx`, `SourcePicker.tsx` — new components
- i18n: 14 new keys per language (EN + DE) for inbox/triage and collection CM-badge

## 0.11.0

### Added
- **Deck Combo Detection** (Sprint 11): Automatic combo discovery via Commander Spellbook integration — combos synced on every deck sync + manual refresh
- **Deck Compare**: Compare 2–4 decks side-by-side — overlap matrix, common cards, unique-per-deck, color identity intersection (`GET /api/decks/compare?ids=…`)
- **Deck Completeness**: Per-deck ownership progress bar with missing card list and estimated cost (`GET /api/decks/{id}/completeness`)
- **Owned-Indicator on Card Search**: Scryfall search results now show `owned_quantity`, `owned_foil_quantity`, and `in_decks` fields (batch query, no N+1)
- **Combo Detail Dialog**: Click any combo to see cards involved, results, prerequisites, steps, and Spellbook link
- **DeckCompare Page**: Full deck comparison UI with multi-select dropdowns, overlap matrix grid, URL-param-based state
- **OwnedBadge Component**: Reusable badge showing "✓ Owned (N×)" with foil indicator and deck tooltip
- **3 new MCP Tools**: `get_deck_combos`, `compare_decks`, `find_card_in_collection`

### Changed
- `sync_deck()` now triggers best-effort combo sync after successful Archidekt import (1s rate-limit between decks)
- Card search endpoints (`/api/cards/search`, `/api/cards/by-name`) enriched with collection ownership data
- Decks page adds "⌬ Compare Decks" navigation button
- DeckView page shows Combos section and Completeness section below AI Assessment

### Fixed
- FastAPI route ordering: `/compare` now correctly defined before `/{deck_id}` to prevent path-parameter matching
- `GET /api/decks/compare` returns HTTP 400 for non-numeric deck IDs (was unhandled ValueError → 500)
- React Fragment key warning in DeckCompare overlap matrix

### Technical
- Schema Migration #12: `deck_combos` table with `deck_id` FK CASCADE, UNIQUE constraint, 2 indexes
- `backend/app/clients/spellbook.py` — Commander Spellbook API client (singleton)
- `backend/app/services/combo_sync.py` — combo fetch/cache service with DELETE-before-INSERT strategy
- `frontend/src/pages/DeckCompare.tsx`, `frontend/src/components/deck/DeckCombosSection.tsx`, `DeckCompletenessSection.tsx`, `ComboDetailDialog.tsx`, `OwnedBadge.tsx` — new components
- i18n: ~20 new keys per language (EN + DE) for combos, compare, completeness, owned indicators

## 0.10.0

### Added
- **Acquisition Tracking** (Sprint 9): Wishlist items now track the full buy-lifecycle via new fields `paid_price_eur`, `expected_price_eur`, `source`, `is_ordered`, `ordered_at`, `not_received_at` (Schema Migration #11)
- **Order Flow**: `POST /api/wishlist/{id}/order` marks an item as ordered with optional expected price; `POST /api/wishlist/{id}/unorder` cancels it. Ordered items show a 📦 badge with expected price in the Active-Tab
- **Acquire Dialog**: "Mark as Received" opens a dialog pre-filled with `expected_price_eur`; user can adjust to actual paid price and select source (`cardmarket | whatnot | booster | trade | gift | shop | other`)
- **Not-Received Flow**: `POST /api/wishlist/{id}/mark-not-received` sets `status=not_received` + timestamp — for lost packages and failed deliveries
- **Acquisition Stats**: `GET /api/wishlist/acquisitions/stats?days=N` returns total acquired count, total spent, current market value, breakdown by source and by month (last 12)
- **Wishlist Tabs**: Four tabs on the Wishlist page — Active (wanted) · History (acquired) · Lost (not_received) · Dropped — each with live item count badge; tab selection persisted to URL (`?tab=…`)
- **History Δ-Column**: Acquired items show paid price vs current market price with color-coded Δ (green = cheaper than market, red = paid more)
- **Listing Health**: `GET /api/cardmarket/listings/health?threshold_pct=15` compares each listing against the latest Cardmarket trend price; returns buckets: `underpriced`, `overpriced`, `fair`, `no_match`. Listings with `price=0` or no trend data go to `no_match`
- **ListingHealthPanel**: New UI panel on the Cardmarket page with threshold slider, bucket filter chips, and suggested-price table
- **5 new MCP Tools**: `mark_wishlist_ordered`, `mark_wishlist_acquired`, `mark_wishlist_not_received`, `get_acquisition_stats`, `analyze_my_listings`

### Changed
- `POST /api/wishlist/{id}/acquire` now accepts optional body `{paid_price_eur, source}`; falls back to `expected_price_eur` when item was previously ordered and no paid price is given
- `GET /api/wishlist/` supports new query params `is_ordered: bool` and convenience alias `status=ordered`
- `WishlistItemRow` actions menu extended with Order / Undo Order / Not Received items (context-sensitive)
- Pydantic `WishlistItemCreate` / `WishlistItemUpdate` status Literal extended with `not_received`
- i18n (EN + DE): `action_order`, `action_unorder`, `action_not_received`, `status_ordered`, `status_not_received`, tab labels

### Fixed
- `POST /api/wishlist/{id}/order` now returns 400 for already-acquired or not-received items (was silently succeeding)
- `POST /api/wishlist/{id}/unorder` now returns 400 "Item is not ordered" if `is_ordered=0` (was missing validation)
- Listing Health: listings with `price=0` no longer misclassified as underpriced — moved to `no_match`

### Technical
- `backend/app/services/listing_health.py` — new service (extracted from cardmarket router)
- `idx_wishlist_status_acquired` partial index on `wishlist(status, acquired_at) WHERE status='acquired'` for stats query performance
- `WishlistAcquireDialog.tsx`, `WishlistOrderDialog.tsx` — new frontend components
- `ListingHealthPanel.tsx` — new cardmarket component with threshold slider

## 0.9.0

### Added
- **Light Theme**: "Daylight Orbital Station" variant — cool near-white (`#F4F5FA`) base, frosted-glass surfaces (`rgba(255,255,255,0.72)`), AA-compliant darker oklch accents for all 6 accent families (sothera / nebula / endstone / stellar / drift / ember)
- **Auto/Dark/Light Toggle**: 3-state theme control in the topbar (◎ AUTO · ◑ DARK · ○ LITE). Auto mode reads `prefers-color-scheme` and updates live on macOS appearance change
- **CSS Custom Property Token System** (`--sv-*`): all design tokens are CSS custom properties that switch atomically under `:root[data-sv-theme="light"]` — zero page-level code changes required
- **`SotheraThemeProvider`** + **`useSotheraTheme()`** hook (`src/theme/index.ts`): returns `{mode, setMode, isDark, fluentTheme}`. Theme choice persisted to `localStorage` under key `sothera.theme`
- **`ACCENTS_LIGHT`**: Light-mode accent map (darkened for AA contrast on white surfaces) exposed alongside `ACCENTS` (dark)

### Changed
- **BackdropFX**: Light branch — nebula masked to upper 35% of viewport (no full-bleed), no star dust, softer glow. Dark branch unchanged
- **Sparkline galaxy-foil**: Fill gradient stops use `var(--sv-foil-sN)` + `var(--sv-foil-top-opacity)` — switches automatically between dark (high-chroma) and light (−30% chroma) variants
- **Topbar accent picker**: Swatches reflect the active theme's accent variant (dark vs light)
- **`FluentProvider`**: Now picks `sotheraTheme` (dark) or `sotheraLightTheme` (light, built with `createLightTheme`) at runtime — no static import
- **220ms crossfade**: `transition: background-color 220ms, color 220ms, border-color 220ms` applied globally via `index.css` — no hard cutover flash on theme switch
- **Scrollbar**: Uses `var(--sv-border-strong)` / `var(--sv-fg-faint)` — inverts cleanly on light
- **Bundle size**: 1,010 KB → 1,024 KB (+14 KB raw / ~4 KB gzip) — delta from `createLightTheme` import

### Technical
- No `isDark` ternaries in any page or component — token layer is the single source of truth
- `tsc --noEmit`: 0 errors; `npm run build`: clean
- No new runtime dependencies

## 0.8.0

### Added
- **Sothera Vault Redesign**: Complete frontend redesign with space-opera aesthetic
- **Theme System**: `src/theme/sothera.ts` — oklch accent ramp (6 named accents: sothera/nebula/endstone/stellar/drift/ember), glass surface tokens, dark Fluent UI theme override
- **Shared Primitives**: `src/components/sothera/` — Panel, PageHeader, SectionHeader, DeltaBadge, CornerTicks, Sigil, BackdropFX
- **Accent Picker**: Swappable accent colors persisted to localStorage, accessible from the topbar
- **Galaxy-Foil Sparkline**: Rewritten Sparkline component with gradient fill, grid pattern, and glowing accent dot with concentric rings
- **BackdropFX**: Animated starfield + nebula glow + horizon haze background layer

### Changed
- **Typography**: Space Grotesk (display, 600-700), Inter (body, 400-500), JetBrains Mono (mono/data, 500-600) via Google Fonts CDN
- **All 8 pages rewritten**: Dashboard, Decks, DeckView, Collection, Cardmarket, Duplicates, Wishlist, Settings — from Fluent UI defaults to Sothera glass-panel layout with custom CSS grid tables
- **Topbar**: New branded topbar with sigil, glyph navigation, status line, and accent picker — replaces Fluent UI TabList
- **Background**: #04040A base with layered radial nebula gradients, replacing default Fluent dark/light mode
- **Surfaces**: Glass panels (rgba(20,20,32,0.55), 1px hairline border, ≤2px radius, backdrop blur) replace Fluent UI Card components
- **Bundle size**: Reduced by ~42 KB (1,052 KB → 1,010 KB) by dropping unused Fluent UI Table/Card imports

### Technical
- Styles use Griffel `makeStyles` throughout — no Tailwind, styled-components, or raw style tags
- No new runtime dependencies added (fonts loaded via `<link>` in index.html)
- `api.ts`, routing structure, data shapes, and backend unchanged
- `tsc --noEmit` passes with zero errors

## 0.7.0

### Added
- **Wishlist**: Full wishlist management — Add-Form, priorities (1-5), status tracking, filters, CSV export
- **Deck Header Features**: User-Bracket (editable 1-5), Gameplan field (500 chars), AI-Assessment (Markdown rendered, MCP-only write)
- **MCP Setup UX**: Settings section with proxy download, config snippet (copy-to-clipboard), OS-specific paths
- **Cardmarket Workflow Banner**: 5-step CSV roundtrip guide on Cardmarket page (dismissible via localStorage)
- **AI-Assessment Markdown**: react-markdown + remark-gfm for safe rendering (no rehype-raw)
- **MCP Tool**: `set_deck_ai_assessment` — AI can write deck assessments (max 5000 chars)
- **API Endpoints**: `GET /api/mcp/proxy.mjs`, `GET /api/mcp/setup-instructions`, `PUT /api/decks/{id}/user-fields`
- **Documentation**: MCP Setup Guide, Cardmarket Workflow Guide

### Changed
- Deck detail header shows Archidekt bracket + editable user bracket side-by-side
- Dockerfile copies mcp-proxy.mjs into container for download endpoint
- Schema migration #10: 4 new columns on `decks` table (user_bracket, gameplan, ai_assessment, ai_assessment_updated_at)

## 0.6.0

### Changed
- **Repository structure**: Add-on files moved into `mtg-collection/` subdirectory — required for Home Assistant custom repositories
- Installation is now via the HA Add-on Store: Settings → Add-ons → Add-on Store → ⋮ → Repositories → `https://github.com/HerrFuchs/mtg-collection-ha`

### Migration
If you previously installed the add-on manually via SCP:
1. Back up the DB: `cp /data/mtg.db /backup/mtg.db.$(date +%Y%m%d)`
2. Uninstall the old add-on in HA
3. Delete the local add-on folder: `rm -rf /addons/mtg-collection`
4. Add the repository URL in HA and reinstall the add-on
5. Restore the DB: `cp /backup/mtg.db.YYYYMMDD /data/mtg.db`

## 0.5.1

### Removed
- Cardmarket profile scraping removed entirely (FlareSolverr-based, unreliable due to Cloudflare)
- FlareSolverr integration and configuration (`flaresolverr_url`)
- "Sync from Profile" button in the Cardmarket UI
- Dependency: selectolax

### Changed
- Cardmarket listings now only via CSV import or manual entry
- Price data sync via official Cardmarket JSON feeds is unchanged

## 0.5.0

### Added
- Duplicates tab: shows cards with excess copies, with sell dialog for Cardmarket listings
- Dashboard price alerts: price-spike alerts on the dashboard with tier grouping
- Collection deck filter: dropdown to filter by deck
- EDHREC link in deck detail view for the Commander
- Cardmarket source tracking: distinguishes imported vs. manually created listings
- Clear Listings button on the Settings page
- MCP Server: `get_duplicates`, `add_cardmarket_listing`, `clear_cardmarket_listings` tools

### Changed
- Dashboard no longer shows a sync-status card
- CSV import preserves manual entries and merges them on name match

## 0.4.2

### Added
- Collection server-side pagination (100 per page)
- Price alert tier grouping with collapsible groups

## 0.4.1

### Fixed
- Collection performance: CTE instead of a correlated O(n²) subquery
- Cardmarket price sync: HTTP 403 treated as end of page list

## 0.3.0

### Added
- Archidekt authentication (login with username/password for private decks and collection)
- Collection sync directly via Archidekt Collection API
- Cardmarket CSV import for listings
- New config fields: `archidekt_password`, `archidekt_user_id`, `cardmarket_username`
- Settings page shows authentication status for Archidekt and Cardmarket

### Changed
- Collection is now read directly from Archidekt (no longer built from deck cards)
- Deck sync no longer automatically adds cards to the collection

### Fixed
- API base URL correctly extracted from the ingress path (fixes "Deck not found" on navigation)
- CHANGELOG format made compatible with Home Assistant

## 0.2.0

### Fixed
- Dockerfile: `ARG BUILD_FROM` placed before first `FROM` for correct HA build args
- Dockerfile: replaced `npm ci` with `npm install` (no `package-lock.json` required)
- Icon: replaced `CardMultiple24Regular` with `Stack24Regular` (exists in @fluentui/react-icons)
- Docker: replaced HA base image with `python:3.12-alpine` — fixes s6-overlay PID 1 crash
- `run.sh`: removed bashio dependency, uses plain `sh` with Supervisor API for ingress info
- Frontend: API base URL derived dynamically from ingress path — fixes 404 errors
- Frontend: `BrowserRouter basename` set for HA ingress routing
- Backend: `root_path` from `INGRESS_ENTRY` for correct FastAPI redirects
- MCP server import/mount made fault-tolerant (try/except)

### Added
- `CHANGELOG.md` for Home Assistant add-on updates
- Centralized version constant in `backend/app/version.py`

## 0.1.0

### Added
- Initial release
- Archidekt deck sync with configurable schedule
- Scryfall card search and price lookup
- EDHREC Commander recommendations and combos
- Collection management with SQLite
- Cardmarket CSV import
- MCP server (Streamable HTTP) for AI assistants
- Fluent UI React frontend with Dashboard, Decks, Collection, Cardmarket, Settings
- Home Assistant Ingress integration
