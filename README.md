# MTG Collection Manager — Home Assistant Add-on

A Home Assistant add-on for managing your Magic: The Gathering collection with automatic Archidekt sync, Scryfall price data, EDHREC Commander recommendations, Cardmarket integration, and an MCP server for AI assistants such as Claude.

## Tech Requirements

| Component | Value |
|-----------|-------|
| App version | 0.22.0 |
| Python runtime | 3.12 (`python:3.12-alpine`) |
| Node.js build | 20 (`node:20-alpine`) |
| Ingress port | 8099 |
| Database | SQLite, WAL mode, foreign keys ON |
| FastAPI | ≥ 0.115.0, < 1.0.0 |
| Uvicorn | ≥ 0.30.0, < 1.0.0 |
| aiosqlite | ≥ 0.20.0, < 1.0.0 |
| httpx | ≥ 0.27.0, < 1.0.0 |
| APScheduler | ≥ 3.10.0, < 4.0.0 |
| Pydantic | ≥ 2.0.0, < 3.0.0 |
| MCP SDK | ≥ 1.0.0, < 2.0.0 |
| aiomqtt | ≥ 2.1.0, < 3.0.0 |
| React | ^18.3.1 |
| TypeScript | ~5.6.2 |
| Vite | ^6.0.5 |
| Fluent UI | `@fluentui/react-components` ^9.56.0 |
| Architectures | aarch64, amd64 |

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Architecture](#architecture)
  - [Project Structure](#project-structure)
  - [Backend](#backend)
  - [Frontend](#frontend)
  - [Database](#database)
- [API Reference](#api-reference)
- [Home Assistant Integration Guide](docs/ha-integration.md)
- [MCP Server (AI Integration)](#mcp-server-ai-integration)
  - [Available Tools](#available-tools)
  - [Available Resources](#available-resources)
  - [Prompts](#prompts)
  - [Connecting Claude Desktop](#connecting-claude-desktop)
- [External Services](#external-services)
- [Development](#development)
- [Changelog](#changelog)

---

## Features

- **Archidekt Sync**: Automatic daily sync of decks and collection
  - Login with username/password for private decks and collection
  - Auto-discovery of all decks for a given username
  - Rate limiting with exponential backoff (no 429 spam)
  - Incremental page-by-page commit (progress survives interruption)
  - Robust sync: stale-entry cleanup only on a complete sync
- **Scryfall Integration**: Card search, USD/EUR prices, autocomplete, direct Scryfall links
- **EDHREC Integration**: Commander recommendations and combo suggestions
- **Commander Spellbook**: Infinite combo detection per deck (full + partial combos)
- **Cardmarket**: CSV import for listings, price data sync, price-spike detection
  - Daily price sync via Cardmarket JSON feeds (owned cards only)
  - 30-day price sparklines on card name hover
  - Automatic price-spike alerts with sell recommendations for unused copies
  - Listing health analysis (underpriced / overpriced / fair vs trend)
- **Inbox / Acquisition Triage**: Review new card acquisitions with keep/sell scoring
  - AI-powered triage advisor (Cardmarket trend price, deck usage)
  - Undo support for triage decisions
  - Colour grouping/filter, name search, and sort by colour/set/newest
  - "Fix colors" backfill re-enriches cards with missing colour identity from Scryfall
  - Basic lands excluded by name (covers snow-covered and un-enriched cards)
- **Deck Performance Tracker**: Log how each game went and review per-deck stats
  - Per game: result (win/loss/draw), date, on-the-play, pod size, mulligans, missed land drops, turns, opponents, and "what worked / what didn't / notes"
  - Aggregates: win rate, W/L/D, recent form, on-play win rate, and averages
- **Voice Integration**: HA Assist endpoints for natural-language card queries ("How many Sol Ring do I have?", "Any active deals?")
- **MCP Server**: Streamable HTTP endpoint for AI assistants (Claude, etc.)
  - 27 tools, 3 resources, 2 prompts — price alerts, price history, deck usage, duplicates, wishlist, deck completeness, sell advisor, AI deck assessment
  - MCP setup wizard in Settings (download, config snippet, step-by-step guide)
- **Web UI**: React frontend with Sothera Vault design — space-opera aesthetic, glass-panel surfaces, galaxy-foil sparklines
  - **Themes**: Dark (deep void), Light (daylight orbital station), Auto (follows system `prefers-color-scheme`) — toggle in the topbar, persisted across sessions
  - **Accent system**: 6 oklch accent families (Sothera / Nebula / Endstone / Stellar / Drift / Ember) — swappable from the topbar, persisted to localStorage
  - Dashboard: stats overview cards + price-spike alerts
  - Decks: collapsible folders, bracket badges, deck previews
  - Deck Detail: Commander header, user bracket, gameplan, AI assessment (Markdown), mana curve, performance tracker
  - Collection: set filter, deck filter, collection-tag filter, grouping by card name, in-decks column
  - Duplicates: duplicate view (incl. "includes colour" + Monocolor filter) with sell dialog for Cardmarket listings
  - Cardmarket: price alerts, sparkline graphs, CSV import/export, workflow banner
  - Wishlist: add form, priorities, status tracking, set/version + foil editing, CSV export
  - Card hover: Scryfall preview image + oracle text
- **Home Assistant Ingress**: seamless integration into the HA panel

---

## Installation

### As a Home Assistant Add-on (recommended)

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ (top right) → Repositories**
2. Enter the URL: `https://github.com/HerrFuchs/mtg-collection-ha` → **Add**
3. "MTG Collection Manager" now appears in the Add-on Store — install it
4. Configure the add-on (see [Configuration](#configuration))
5. Start the add-on — it appears as the "MTG Collection" panel in the sidebar

### Migration from a local installation

If you previously installed the add-on manually via SCP into `/addons/mtg-collection/`:

1. **Back up the database**: In the HA terminal: `cp /data/mtg.db /backup/mtg.db.$(date +%Y%m%d)`
2. Uninstall the old add-on in HA (Settings → Add-ons → MTG Collection Manager → Uninstall)
3. Delete the old local add-on folder: `rm -rf /addons/mtg-collection`
4. Add the repository as described above and reinstall the add-on
5. **Restore the database**: `cp /backup/mtg.db.YYYYMMDD /data/mtg.db`
6. Start the add-on — all data is restored

### Manual (Development)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8099

# Frontend
cd frontend
npm install
npm run dev
```

---

## Configuration

All options are set through the Home Assistant add-on configuration UI and stored in `/data/options.json`.

| Option | Type | Default | Description |
|---|---|---|---|
| `archidekt_username` | string | `""` | Archidekt username for deck discovery and sync |
| `archidekt_password` | password | `""` | Archidekt password (required for private decks and collection) |
| `archidekt_user_id` | int | `0` | Archidekt user ID (from the collection URL, e.g. `123456`) |
| `archidekt_deck_ids` | list[int] | `[]` | Specific deck IDs to sync (empty = auto-discover all decks) |
| `sync_enabled` | bool | `true` | Enable automatic daily sync |
| `sync_hour` | int (0–23) | `3` | Hour of day for the daily sync |
| `mcp_auth_token` | string | `""` | Optional Bearer token for MCP server authentication |
| `cardmarket_username` | string | `""` | Cardmarket username (display only) |
| `mqtt_enabled` | bool | `false` | Enable MQTT sensor publishing (HA auto-discovery) |
| `mqtt_host` | string | `""` | MQTT broker hostname (e.g. `core-mosquitto` for the HA add-on) |
| `mqtt_port` | int | `1883` | MQTT broker port |
| `mqtt_username` | string | `""` | MQTT username |
| `mqtt_password` | password | `""` | MQTT password |
| `mqtt_topic_prefix` | string | `"mtg-collection"` | Prefix for MQTT state topics |
| `notify_min_alert_value_eur` | float | `5.0` | Minimum card value (EUR) to trigger a price-spike notification |
| `notify_webhook_url` | string | `""` | Webhook URL for price-spike notifications |
| `notify_via_ha_service` | string | `""` | HA service call for price-spike notifications |

### Minimal Configuration

```yaml
archidekt_username: "DeinUsername"
```

### Full Configuration (with private decks and collection)

```yaml
archidekt_username: "DeinUsername"
archidekt_password: "DeinPasswort"
archidekt_user_id: 123456
archidekt_deck_ids: []
sync_enabled: true
sync_hour: 3
cardmarket_username: "DeinCardmarketName"
```

---

## Architecture

### Project Structure

```
mtg-collection-ha/                     # GitHub repository root
├── repository.yaml          # HA custom repository manifest
├── README.md                # Documentation
├── LICENSE                  # MIT license
├── SECURITY.md              # Security policy
├── docs/
│   ├── mcp-setup.md         # MCP setup guide for Claude Desktop
│   └── cardmarket-workflow.md # Cardmarket CSV workflow guide
└── mtg-collection/          # Add-on (slug = directory name)
    ├── config.yaml          # HA add-on metadata
    ├── build.yaml           # HA build config (base images)
    ├── Dockerfile           # Multi-stage build (Node → Python)
    ├── run.sh               # Entrypoint: ingress detection → Uvicorn
    ├── CHANGELOG.md         # Version history
    ├── mcp-proxy.mjs        # Local stdio→HTTP MCP proxy for Claude Desktop
    ├── backend/
    │   ├── requirements.txt     # Python dependencies
    │   └── app/
    │       ├── main.py          # FastAPI app, lifespan, router mounting
    │       ├── config.py        # Pydantic settings (from options.json)
    │       ├── database.py      # SQLite schema, init, migrations, connection
    │       ├── scheduler.py     # APScheduler for daily sync
    │       ├── version.py       # VERSION = "0.22.0"
    │       ├── mcp_server.py    # MCP server (27 tools, 3 resources, 2 prompts)
    │       ├── logging_config.py # Structured JSON logging to stdout
    │       ├── clients/
    │       │   ├── archidekt.py # Archidekt API client (auth, decks, collection)
    │       │   ├── scryfall.py  # Scryfall API client (search, prices)
    │       │   ├── edhrec.py    # EDHREC JSON client (recommendations, combos)
    │       │   └── spellbook.py # Commander Spellbook client (combo detection)
    │       ├── models/
    │       │   └── schemas.py   # Pydantic models (request/response)
    │       ├── routers/
    │       │   ├── acquisitions.py # /api/acquisitions/* (inbox triage)
    │       │   ├── backup.py    # /api/backup/* (backup, restore)
    │       │   ├── cards.py     # /api/cards/* (Scryfall proxy, EDHREC)
    │       │   ├── cardmarket.py# /api/cardmarket/* (CSV, sync, listings)
    │       │   ├── collection.py# /api/collection/* (CRUD, duplicates)
    │       │   ├── decks.py     # /api/decks/* (deck list, detail, user fields)
    │       │   ├── mcp_setup.py # /api/mcp/* (proxy download, setup instructions)
    │       │   ├── stats.py     # /api/stats/ (collection statistics)
    │       │   ├── sync.py      # /api/sync/* (trigger, status, history)
    │       │   ├── voice.py     # /api/voice/* (HA Assist integration)
    │       │   └── wishlist.py  # /api/wishlist/* (CRUD, acquire, export)
    │       └── services/
    │           ├── card_resolver.py     # Find-or-fetch card by name/ID
    │           ├── cardmarket_import.py # Cardmarket CSV import
    │           ├── cardmarket_prices.py # Cardmarket price sync and alerts
    │           ├── combo_sync.py        # Commander Spellbook combo sync
    │           ├── deck_performance.py  # Deck game-result aggregation
    │           ├── ha_publisher.py      # MQTT sensor discovery and publishing
    │           ├── listing_health.py    # Listing vs trend health analysis
    │           ├── notifications.py     # Price-spike notifications
    │           ├── queries.py           # Shared DB query helpers (incl. basic-land exclusion)
    │           ├── sell_advisor.py      # Sell recommendation logic
    │           ├── sync_service.py      # Archidekt → DB sync logic
    │           └── triage_advisor.py    # Keep/sell scoring for acquisitions
    ├── frontend/
    │   ├── package.json         # React 18, Fluent UI, React Router, Vite
    │   ├── vite.config.ts       # Vite build config
    │   ├── tsconfig.json        # TypeScript config
    │   ├── index.html           # SPA entry point
    │   └── src/
    │       ├── main.tsx         # React root, FluentProvider, BrowserRouter
    │       ├── App.tsx          # Tab navigation, routes
    │       ├── api.ts           # API client (fetch-based, ingress-aware)
    │       ├── pages/
    │       │   ├── Cardmarket.tsx  # Cardmarket listings, CSV import, alerts
    │       │   ├── Collection.tsx  # Card collection with search and filters
    │       │   ├── Dashboard.tsx   # Stats overview, price alerts
    │       │   ├── Decks.tsx       # Deck grid with folder navigation
    │       │   ├── DeckView.tsx    # Deck detail with mana curve + performance tracker
    │       │   ├── Duplicates.tsx  # Duplicates with sell dialog
    │       │   ├── Inbox.tsx       # Acquisition triage (colour groups, search, sort)
    │       │   ├── Settings.tsx    # Sync config, history, MCP setup
    │       │   └── Wishlist.tsx    # Wishlist management
    │       └── components/
    │           ├── CardHoverPreview.tsx # Card hover shows Scryfall image
    │           ├── ManaSymbol.tsx       # {W}{U}{B} → Scryfall SVG icons
    │           ├── Sparkline.tsx        # Price sparkline chart
    │           ├── cardmarket/          # Cardmarket-specific components
    │           ├── deck/                # Deck-specific components
    │           └── settings/            # Settings-specific components
    └── translations/
        └── en.yaml              # English UI strings for HA config
```

### Backend

**Tech Stack:** Python 3.12, FastAPI ≥ 0.115, Uvicorn ≥ 0.30, aiosqlite ≥ 0.20, httpx ≥ 0.27, APScheduler ≥ 3.10, Pydantic v2, MCP SDK ≥ 1.0

The backend server starts via `run.sh`, which queries the Supervisor API to determine the ingress path, then launches Uvicorn on port 8099.

#### Lifecycle (Lifespan)

1. **Startup**: initialize database → start scheduler → start MCP session manager
2. **Running**: API requests, scheduled syncs, MCP requests
3. **Shutdown**: stop scheduler → close database

#### API Clients

| Client | File | Base URL | Rate Limiting |
|---|---|---|---|
| Archidekt | `clients/archidekt.py` | `https://archidekt.com` | 2 s delay + backoff (4/8/16/32 s on 429) |
| Scryfall | `clients/scryfall.py` | `https://api.scryfall.com` | 100 ms between requests |
| EDHREC | `clients/edhrec.py` | `https://json.edhrec.com/pages` | 24 h in-memory cache |
| Cardmarket | `clients/cardmarket.py` | `https://www.cardmarket.com` | 1.5 s between pages |
| Spellbook | `clients/spellbook.py` | `https://backend.commanderspellbook.com` | On-demand, cached per deck |

#### Sync Service

`sync_service.py` implements the main synchronization process:

1. **Archidekt login** (if credentials are set)
2. **Collection sync** (if authenticated and user ID is set) — page-by-page with a DB commit per page
3. **Deck discovery** — auto-discovery via username or explicit IDs
4. **Deck sync** — each deck individually with a 1.5 s pause between them
5. **Logging** — every sync run is recorded in the `sync_log` table

### Frontend

**Tech Stack:** React 18.3, Fluent UI v9, React Router v7, TanStack Query v5, Vite 6, TypeScript 5.6

The SPA is built in the multi-stage Docker build with Node.js 20 and served as static files from the backend (`/static`).

#### Pages

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Stats cards (total cards, value, decks) + price-spike alerts |
| Decks | `/decks` | Collapsible folders, bracket badges, Commander, format |
| Deck Detail | `/decks/:id` | Commander header, mana curve, card table, combos, AI assessment, performance tracker |
| Deck Compare | `/decks/compare` | Side-by-side deck comparison matrix |
| Collection | `/collection` | Set filter, grouping by card name, in-decks column, Scryfall links |
| Cardmarket | `/cardmarket` | Listings, CSV import/export, price sync, sparklines, alerts, listing health |
| Duplicates | `/duplicates` | Duplicate cards with sell-to-Cardmarket dialog |
| Inbox | `/inbox` | Acquisition triage with keep/sell scoring |
| Wishlist | `/wishlist` | Wishlist with priorities, color filter, group-by-card, status tracking |
| Settings | `/settings` | Sync config, manual trigger, sync history, MCP setup |

#### Ingress Handling

The API base URL is extracted dynamically from the path:
```typescript
// /api/hassio_ingress/<token>/decks/1 → /api/hassio_ingress/<token>
const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
```
This makes the app work both behind HA Ingress and standalone.

### Database

SQLite with WAL mode and foreign keys enabled. Schema:

| Table | Description |
|---|---|
| `cards` | All cards (Scryfall ID, name, mana cost, prices, …) |
| `decks` | Deck metadata (name, format, Commander, bracket, user bracket, gameplan, AI assessment) |
| `deck_cards` | Card-to-deck mapping (quantity, category, Commander flag) |
| `deck_games` | Per-game performance log (result, mulligans, missed land drops, turns, notes) |
| `collection` | Personal collection (quantity, foil, condition, language) |
| `cardmarket_listings` | Cardmarket offer listings |
| `cardmarket_products` | Cardmarket products matched to owned cards |
| `cardmarket_price_history` | Daily price data (avg, low, trend, avg1/7/30) |
| `sync_log` | Sync history (source, status, duration, error) |
| `schema_version` | Database versioning |
| `wishlist` | Wishlist items (card name, set, priority, status, tags) |
| `collection_value_snapshots` | Daily collection value snapshots |

Data is stored at `/data/mtg.db` (HA `data` mount).

---

## API Reference

Base URL: `http://<ha-host>:8123/api/hassio_ingress/<token>`

### Decks

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/decks/` | List all decks |
| `GET` | `/api/decks/{id}` | Deck detail with all cards |
| `PUT` | `/api/decks/{id}/user-fields` | Update user bracket (1–5) and/or gameplan (body: `user_bracket`, `gameplan`) |
| `GET` | `/api/decks/{id}/games` | List logged games for a deck (newest first) |
| `POST` | `/api/decks/{id}/games` | Log a game (result, mulligans, missed land drops, notes, …) |
| `PATCH` | `/api/decks/{id}/games/{game_id}` | Update a logged game (partial) |
| `DELETE` | `/api/decks/{id}/games/{game_id}` | Delete a logged game |
| `GET` | `/api/decks/{id}/performance` | Aggregate performance stats (win rate, averages, …) |

### Collection

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/collection/` | List collection (filters: `search`, `color`, `rarity`, `set_code`, `collection_tag`, `deck_id`; pagination) |
| `GET` | `/api/collection/sets` | Sets present in the collection |
| `GET` | `/api/collection/tags` | Distinct collection (Archidekt) tags present in the collection |
| `GET` | `/api/collection/duplicates` | List duplicates (filters: `search`, `color` incl. `MONO`, `set_code`) |
| `POST` | `/api/collection/` | Add card to collection (body: `scryfall_id`, `quantity`, …) |
| `DELETE` | `/api/collection/{id}` | Remove card from collection |

### Cards (Scryfall Proxy)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/cards/search?q=...` | Scryfall search (full syntax) |
| `GET` | `/api/cards/named?name=...` | Card by exact name |
| `GET` | `/api/cards/autocomplete?q=...` | Autocomplete suggestions |
| `GET` | `/api/cards/printings?name=...` | All printings of a card |
| `GET` | `/api/cards/edhrec/recommendations/{name}` | EDHREC recommendations for a Commander |
| `GET` | `/api/cards/edhrec/combos/{name}` | EDHREC combos for a Commander |

### Cardmarket

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/cardmarket/listings` | List listings (filters: `search`, `color`, `set_code`, `source`, `sort_by`; pagination) |
| `GET` | `/api/cardmarket/stats` | Stats (count, total value) |
| `POST` | `/api/cardmarket/import` | Upload and import a CSV file |
| `GET` | `/api/cardmarket/export` | Export listings as CSV |
| `GET` | `/api/cardmarket/price-history/{id}` | Price history for a Cardmarket product |
| `GET` | `/api/cardmarket/price-alerts` | Price-spike alerts for unused cards |
| `POST` | `/api/cardmarket/sync-prices` | Trigger a manual Cardmarket price sync |
| `GET` | `/api/cardmarket/products` | List matched Cardmarket products |
| `POST` | `/api/cardmarket/add-listing` | Create a manual listing (body: `card_name`, `quantity`, `price`, …) |
| `DELETE` | `/api/cardmarket/clear-listings` | Delete all listings |

### Sync

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/sync/status` | Current sync status and configuration |
| `GET` | `/api/sync/history` | Last 20 sync log entries |
| `POST` | `/api/sync/trigger` | Start a manual sync |
| `POST` | `/api/sync/trigger-resync` | Delete all synced data and re-download everything |
| `GET` | `/api/sync/probe-archidekt` | Debug: test Archidekt API connectivity |

### Stats

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/stats/` | Total statistics (cards, value, decks, Cardmarket) |
| `GET` | `/api/stats/value-history` | Daily collection value snapshots (query: `days`) |

### Wishlist

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/wishlist/` | List wishlist items (filters: `status`, `priority_min`, `deck_id`, `deals_only`) |
| `GET` | `/api/wishlist/summary` | Aggregate stats (total value, deals, by priority/deck) |
| `GET` | `/api/wishlist/{id}` | Get single wishlist item |
| `POST` | `/api/wishlist/` | Add item to wishlist |
| `PATCH` | `/api/wishlist/{id}` | Update wishlist item (partial update) |
| `DELETE` | `/api/wishlist/{id}` | Remove item from wishlist |
| `POST` | `/api/wishlist/{id}/acquire` | Mark item as acquired |
| `POST` | `/api/wishlist/{id}/restore` | Restore an acquired item to active |
| `GET` | `/api/wishlist/export/cardmarket` | Export wishlist as Cardmarket wantlist (plain text) |
| `GET` | `/api/wishlist/export/json` | Export wishlist as JSON |

### Backup

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/backup/backup` | Download the SQLite database as a file |
| `POST` | `/api/backup/restore` | Upload a `.db` file to restore the database |

### Acquisitions (Inbox Triage)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/acquisitions/pending` | List pending acquisition events (filters: `search`, `color`, `sort`, `min_value_eur`; paginated) |
| `GET` | `/api/acquisitions/stats` | Inbox overview stats |
| `POST` | `/api/acquisitions/backfill-colors` | Re-fetch missing colour identity from Scryfall for pending cards |
| `POST` | `/api/acquisitions/{event_id}/decide` | Submit keep/sell triage decision |
| `POST` | `/api/acquisitions/{event_id}/undo` | Undo a triage decision |

### Voice (HA Assist)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/voice/card-count?name=` | How many copies of a card the user owns |
| `GET` | `/api/voice/active-deals` | Wishlist items where current price ≤ target |

### MCP Setup

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/mcp/proxy.mjs` | Download `mcp-proxy.mjs` |
| `GET` | `/api/mcp/setup-instructions` | Ingress-aware Claude Desktop config snippet and setup steps |

---

## MCP Server (AI Integration)

The built-in MCP server (Model Context Protocol) lets AI assistants like Claude access your collection directly.

**Transport:** Streamable HTTP (stateless, JSON responses)
**Endpoint:** `/mcp` (accessible via HA Ingress)
**Authentication:** If `mcp_auth_token` is set in the add-on configuration, every request to `/mcp` must include the header `Authorization: Bearer <token>`. Missing or incorrect token returns HTTP 401. An empty token leaves the endpoint open (backward-compatible).

See [docs/mcp-setup.md](docs/mcp-setup.md) for a step-by-step Claude Desktop setup guide.

### Available Tools

| Tool | Description |
|---|---|
| `search_card` | Scryfall card search (full syntax) |
| `get_card` | Card by exact name with full details |
| `list_decks` | List all synced decks (with folder and bracket) |
| `get_deck` | Deck detail with card list and bracket |
| `search_collection` | Search collection by name |
| `get_collection_stats` | Collection statistics (cards, value, decks) |
| `get_cardmarket_listings` | List Cardmarket listings |
| `get_card_price` | Current prices via Scryfall |
| `get_edhrec_recommendations` | EDHREC recommendations for a Commander |
| `get_edhrec_combos` | EDHREC combos for a Commander |
| `trigger_sync` | Trigger a manual Archidekt sync |
| `get_price_alerts` | Price-spike alerts for unused cards |
| `get_price_history` | Cardmarket price history for a card |
| `get_deck_usage` | Which decks use a given card |
| `sync_prices` | Trigger a manual Cardmarket price sync |
| `get_duplicates` | List duplicates (cards with excess copies) |
| `add_cardmarket_listing` | Create a manual Cardmarket listing |
| `clear_cardmarket_listings` | Delete all Cardmarket listings |
| `suggest_what_to_sell` | Sell recommendations: unused cards with high value |
| `get_wishlist` | Retrieve wishlist (filters: `status`, `priority_min`, `deck_id`, `deals_only`) |
| `add_to_wishlist` | Add card to wishlist (`set_code`, `is_foil`, `quantity`, `priority`, `deck`, `tags`) |
| `update_wishlist_item` | Update a wishlist item (PATCH semantics: only changed fields) |
| `wishlist_summary` | Aggregate wishlist stats (total value, deals, by priority/deck) |
| `find_card_printings` | All printings of a card with set, price, foil availability |
| `wishlist_to_cardmarket_decklist` | Export wishlist as Cardmarket wantlist plain text |
| `analyze_deck_completeness` | Analyze deck completeness (missing cards, acquisition cost) |
| `set_deck_ai_assessment` | Write or update the AI assessment for a deck (Markdown, max 5 000 chars) |

### Available Resources

| Resource URI | Description |
|---|---|
| `mtg://collection/stats` | Current collection statistics as JSON |
| `mtg://decks` | List of all synced decks as JSON |
| `mtg://deck/{deck_id}` | Details for a single deck (parameterized) |

### Prompts

| Prompt | Parameters | Description |
|---|---|---|
| `analyze_deck` | `deck_name` | Analyze a deck (mana curve, synergies, suggested improvements) |
| `suggest_upgrades` | `deck_name`, `budget` | Suggest deck upgrades within a budget |

### Connecting Claude Desktop

The MCP server runs behind HA Ingress and requires a local stdio→HTTP proxy (`mcp-proxy.mjs`) to handle authentication.

#### Prerequisites

- Node.js installed locally
- HA long-lived access token (Profile → Security → Tokens)
- Add-on ingress token (from the URL or Supervisor API)

#### 1. Test the proxy

```bash
cd /pfad/zu/mtg-collection-ha/mtg-collection
npm install  # installs the ws package

echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | \
node mcp-proxy.mjs \
  http://<HA_IP>:8123 \
  <LONG_LIVED_TOKEN> \
  /api/hassio_ingress/<INGRESS_TOKEN>/mcp \
  <MCP_AUTH_TOKEN>
```

> **Note:** The fourth argument `<MCP_AUTH_TOKEN>` is optional. You can also set the environment variable `MCP_AUTH_TOKEN` instead.

#### 2. Configure Claude Desktop

File: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "mtg-collection": {
      "command": "node",
      "args": [
        "/pfad/zu/mtg-collection-ha/mtg-collection/mcp-proxy.mjs",
        "http://<HA_IP>:8123",
        "<LONG_LIVED_TOKEN>",
        "/api/hassio_ingress/<INGRESS_TOKEN>/mcp",
        "<MCP_AUTH_TOKEN>"
      ]
    }
  }
}
```

#### 3. Restart Claude Desktop

After restarting, "MTG Collection Manager" appears as an available MCP server with 27 tools.

#### How the proxy works

```
Claude Desktop ↔ stdio ↔ mcp-proxy.mjs ↔ HTTP ↔ HA Ingress ↔ Add-on /mcp
```

> **Note:** Port 8099 is only reachable inside the HA network. The only official external access path is via HA Ingress with `mcp-proxy.mjs`.

1. The proxy connects to the HA API via WebSocket and authenticates
2. Creates an Ingress session (cookie)
3. Forwards JSON-RPC messages from stdin to the HTTP endpoint
4. Returns results to stdout
5. Automatically renews the session on 401/403

---

## External Services

| Service | Usage | Authentication |
|---|---|---|
| [Archidekt](https://archidekt.com) | Deck sync, collection sync | Optional: username/password (JWT) |
| [Scryfall](https://scryfall.com/docs/api) | Card search, prices, images | None (public API, 100 ms rate limit) |
| [EDHREC](https://edhrec.com) | Commander recommendations, combos | None (unofficial JSON endpoints, 24 h cache) |
| [Commander Spellbook](https://commanderspellbook.com) | Infinite combo detection | None (public API) |
| [Cardmarket](https://cardmarket.com) | Offer listings, price data | CSV import + official JSON price feeds |

---

## Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for the HA add-on build)

### Local Development

```bash
# Backend (terminal 1)
cd backend
pip install -r requirements.txt
export DATA_DIR=./data
export OPTIONS_PATH=./data/options.json
export CORS_ORIGINS=http://localhost:5173  # enable CORS for standalone development
python -m uvicorn app.main:app --reload --port 8099

# Frontend (terminal 2)
cd frontend
npm install
npm run dev  # starts the Vite dev server with proxy to localhost:8099
```

### Docker Build

```bash
cd mtg-collection
docker build -t mtg-collection .
docker run -p 8099:8099 -v $(pwd)/data:/data mtg-collection
```

### Project Conventions

- **Backend**: singleton pattern for API clients (`archidekt`, `scryfall`, `edhrec`)
- **Frontend**: Fluent UI v9 components, functional React components with hooks
- **Database**: all schema migrations in `database.py`, idempotent via `PRAGMA table_info`
- **API**: RESTful, JSON, FastAPI routers with Pydantic models
- **Error handling**: exponential backoff on rate limiting, incremental commits during sync

### Linting & Type-Checking

```bash
cd backend
ruff check .
mypy .
```

Configuration in `backend/pyproject.toml` (line-length 100, strict mypy).

### Environment Variables (Development)

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `DATA_DIR` | `/data` | Path to the data directory |
| `OPTIONS_PATH` | `/data/options.json` | Path to the HA options file |
| `CORS_ORIGINS` | (empty) | Comma-separated CORS origins |

---

## 📚 Detailed Guides

- [Home Assistant Integration](docs/ha-integration.md) — MQTT sensors, voice integration, automations, dashboard cards
- [MCP Setup für Claude Desktop](docs/mcp-setup.md) — How to connect this add-on to Claude Desktop
- [Cardmarket Workflow](docs/cardmarket-workflow.md) — CSV-based listing management

---

## Changelog

See [mtg-collection/CHANGELOG.md](mtg-collection/CHANGELOG.md) for the full version history.
