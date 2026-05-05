# MTG Collection Manager — Home Assistant Add-on

A Home Assistant add-on for managing your Magic: The Gathering collection with automatic Archidekt sync, Scryfall price data, EDHREC Commander recommendations, Cardmarket integration, and an MCP server for AI assistants such as Claude.

## Tech Requirements

| Component | Value |
|-----------|-------|
| App version | 0.7.0 |
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
- **Cardmarket**: CSV import for listings, price data sync, price-spike detection
  - Daily price sync via Cardmarket JSON feeds (owned cards only)
  - 30-day price sparklines on card name hover
  - Automatic price-spike alerts with sell recommendations for unused copies
- **MCP Server**: Streamable HTTP endpoint for AI assistants (Claude, etc.)
  - 27 tools, 3 resources, 2 prompts — price alerts, price history, deck usage, duplicates, wishlist, deck completeness, sell advisor, AI deck assessment
  - MCP setup wizard in Settings (download, config snippet, step-by-step guide)
- **Web UI**: React frontend with Fluent UI
  - Dashboard: stats overview cards + price-spike alerts
  - Decks: collapsible folders, bracket badges, deck previews
  - Deck Detail: Commander header, user bracket, gameplan, AI assessment (Markdown), mana curve
  - Collection: set filter, deck filter, grouping by card name, in-decks column
  - Duplicates: duplicate view with sell dialog for Cardmarket listings
  - Cardmarket: price alerts, sparkline graphs, CSV import/export, workflow banner
  - Wishlist: add form, priorities, status tracking, CSV export
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
    │       ├── version.py       # VERSION = "0.7.0"
    │       ├── mcp_server.py    # MCP server (27 tools, 3 resources, 2 prompts)
    │       ├── clients/
    │       │   ├── archidekt.py # Archidekt API client (auth, decks, collection)
    │       │   ├── scryfall.py  # Scryfall API client (search, prices)
    │       │   └── edhrec.py    # EDHREC JSON client (recommendations, combos)
    │       ├── models/
    │       │   └── schemas.py   # Pydantic models (request/response)
    │       ├── routers/
    │       │   ├── backup.py    # /api/backup/* (backup, restore)
    │       │   ├── cards.py     # /api/cards/* (Scryfall proxy, EDHREC)
    │       │   ├── cardmarket.py# /api/cardmarket/* (CSV, sync, listings)
    │       │   ├── collection.py# /api/collection/* (CRUD, duplicates)
    │       │   ├── decks.py     # /api/decks/* (deck list, detail, user fields)
    │       │   ├── mcp_setup.py # /api/mcp/* (proxy download, setup instructions)
    │       │   ├── stats.py     # /api/stats/ (collection statistics)
    │       │   ├── sync.py      # /api/sync/* (trigger, status, history)
    │       │   └── wishlist.py  # /api/wishlist/* (CRUD, acquire, export)
    │       └── services/
    │           ├── cardmarket_import.py # Cardmarket CSV import
    │           ├── cardmarket_prices.py # Cardmarket price sync and alerts
    │           ├── ha_publisher.py      # MQTT sensor discovery and publishing
    │           ├── notifications.py     # Price-spike notifications
    │           ├── queries.py           # Shared DB query helpers
    │           ├── sell_advisor.py      # Sell recommendation logic
    │           └── sync_service.py      # Archidekt → DB sync logic
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
    │       │   ├── DeckView.tsx    # Deck detail with mana curve
    │       │   ├── Duplicates.tsx  # Duplicates with sell dialog
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
| Deck Detail | `/decks/:id` | Commander header, mana curve, card table, sideboard separation |
| Collection | `/collection` | Set filter, grouping by card name, in-decks column, Scryfall links |
| Cardmarket | `/cardmarket` | Listings, CSV import/export, price sync, sparklines, alerts |
| Duplicates | `/duplicates` | Duplicate cards with sell-to-Cardmarket dialog |
| Wishlist | `/wishlist` | Wishlist with priorities, status tracking, CSV export |
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

### Collection

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/collection/` | List collection (filters: `search`, `color`, `rarity`, `set_code`, `deck_id`; pagination) |
| `GET` | `/api/collection/sets` | Sets present in the collection |
| `GET` | `/api/collection/duplicates` | List duplicates (cards with excess copies) |
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
| `GET` | `/api/cardmarket/listings` | List listings (filter: `search`; pagination) |
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

- [MCP Setup für Claude Desktop](docs/mcp-setup.md) — How to connect this add-on to Claude Desktop
- [Cardmarket Workflow](docs/cardmarket-workflow.md) — CSV-based listing management

---

## Changelog

### 0.7.0

#### Added
- **Wishlist**: Full wishlist management with add form, priorities, status tracking, filters, and CSV export
- **Deck Header Features**: User bracket (editable 1–5), gameplan field (500 chars), AI assessment (Markdown, MCP-write-only)
- **MCP Setup UX**: Settings section with proxy download, config snippet (copy-to-clipboard), OS-specific paths
- **Cardmarket Workflow Banner**: 5-step CSV roundtrip guide on the Cardmarket page (dismissible)
- **AI Assessment Markdown**: react-markdown + remark-gfm for safe Markdown rendering
- **MCP Tool**: `set_deck_ai_assessment` — AI can write deck assessments
- **API Endpoints**: `GET /api/mcp/proxy.mjs`, `GET /api/mcp/setup-instructions`, `PUT /api/decks/{id}/user-fields`
- **Documentation**: [MCP Setup Guide](docs/mcp-setup.md), [Cardmarket Workflow Guide](docs/cardmarket-workflow.md)

#### Changed
- Deck detail header now shows Archidekt bracket and editable user bracket side by side
- Schema migration #10: 4 new columns on the `decks` table

### 0.6.0

#### Added
- **Duplicates tab**: New tab shows all cards with excess copies (owned > in decks)
  - Sell dialog: create Cardmarket listings directly from duplicates (price, condition, language, quantity)
  - Pagination and search
- **Dashboard price alerts**: Price-spike alerts now shown on the dashboard (instead of sync status)
  - Grouped by price tier with collapsible groups
- **Collection deck filter**: Dropdown to filter the collection by deck
- **EDHREC link**: Deck detail view shows EDHREC link for the Commander
- **Cardmarket source tracking**: Listings distinguish between CSV-import and manually created entries
  - Manual entries highlighted in the listings table
  - CSV re-import merges manual entries when card name matches
- **Clear Listings button**: Settings page has a button to delete all Cardmarket listings
- **MCP Server**: 3 new tools (`get_duplicates`, `add_cardmarket_listing`, `clear_cardmarket_listings`)

#### Changed
- Dashboard no longer shows a sync-status card (moved to Settings)
- Cardmarket CSV import preserves manual entries on re-import

### 0.4.2

#### Added
- **Collection pagination**: Server-side pagination (100 per page) instead of loading 6 000+ entries at once
- **Price alert tier grouping**: Alerts grouped by price tier with collapsible groups

### 0.4.1

#### Fixed
- **Collection performance**: CTE with LEFT JOIN instead of a correlated O(n²) subquery for in-decks count
- **Cardmarket price sync**: HTTP 403 is treated as end of page list (not only 404)

### 0.4.0

#### Added
- **Cardmarket price data sync**: Daily automatic sync via Cardmarket JSON feeds
  - Only owned cards are matched and stored
  - Price history (avg, low, trend, avg1/7/30) in a new `cardmarket_price_history` table
  - 30-day sparkline graphs on card name hover in the Cardmarket tab
  - "Sync Prices" button for a manual price sync
- **Price spike detection**: Automatic alerts when trend > 30% above the 30-day average
  - Sell recommendations for unused copies (not in any deck)
  - Alert section on the Cardmarket page
- **Deck bracket**: Bracket value extracted from Archidekt and displayed
- **Collapsible deck folders**: Folders on the Decks page collapsed by default
- **Deck detail redesign**: Commander image as header, bracket badge, color-identity pips, total value, Archidekt link, compact card table without images
- **Sideboard/Maybeboard separation**: Non-deck categories shown as a dimmed section at the bottom
- **Scryfall links**: Clicking a card name opens Scryfall in a new tab (Decks and Collection)
- **Collection set filter**: Dropdown to filter by set
- **Collection grouping**: Cards grouped by name, collapsible
- **In-decks column**: "In Decks" column in the Collection view
- **Oracle text on hover**: Card text shown below the preview image
- **MCP Server**: 5 new tools (`get_price_alerts`, `get_price_history`, `get_deck_usage`, `sync_prices`)
- **Cardmarket product table**: DB table for matched products with card foreign key

#### Fixed
- **Collection data loss on sync**: Stale-entry cleanup only on a complete sync (`sync_complete` flag)
- **Collection display empty**: `page_size` limit raised to 5 000 (was 1 000; frontend requested 5 000)

### 0.3.0

#### Added
- Archidekt authentication (login for private decks and collection)
- Collection sync directly via Archidekt Collection API
- Cardmarket CSV import and price data sync
- MCP server with 11 tools and 2 prompts (Streamable HTTP)
- Card hover preview with Scryfall images
- Mana symbol rendering via Scryfall SVG API

#### Changed
- Collection is now read directly from Archidekt (no longer built from deck cards)
- Deck sync no longer automatically adds cards to the collection

#### Fixed
- Rate limiting (429) with exponential backoff
- Incremental commit during collection sync
- API base URL correctly extracted from ingress path

### 0.2.0

#### Fixed
- Docker: replaced HA base image with `python:3.12-alpine` (s6-overlay PID 1 crash)
- `run.sh`: removed bashio dependency, uses plain `sh` with Supervisor API
- Frontend: API base URL extracted dynamically from ingress path
- MCP server import/mount made fault-tolerant

#### Added
- `CHANGELOG.md` for Home Assistant add-on updates
- Centralized version in `version.py`

### 0.1.0

#### Added
- Initial release
- Archidekt deck sync with configurable schedule
- Scryfall card search and price lookup
- EDHREC Commander recommendations and combos
- Collection management with SQLite
- Cardmarket CSV import
- MCP server (Streamable HTTP)
- Fluent UI React frontend
- Home Assistant Ingress integration
