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
