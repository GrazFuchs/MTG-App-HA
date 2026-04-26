# MTG Collection Manager — Home Assistant Add-on

Ein Home Assistant Add-on zur Verwaltung deiner Magic: The Gathering Sammlung mit automatischer Synchronisierung von Archidekt, Preisinformationen über Scryfall, Commander-Empfehlungen von EDHREC, Cardmarket-Integration und einem MCP-Server für AI-Assistenten wie Claude.

---

## Inhaltsverzeichnis

- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [Architektur](#architektur)
  - [Projektstruktur](#projektstruktur)
  - [Backend](#backend)
  - [Frontend](#frontend)
  - [Datenbank](#datenbank)
- [API-Referenz](#api-referenz)
- [MCP-Server (AI-Integration)](#mcp-server-ai-integration)
  - [Verfügbare Tools](#verfügbare-tools)
  - [Prompts](#prompts)
  - [Claude Desktop anbinden](#claude-desktop-anbinden)
- [Externe Dienste](#externe-dienste)
- [Entwicklung](#entwicklung)
- [Changelog](#changelog)

---

## Features

- **Archidekt-Sync**: Automatische tägliche Synchronisierung von Decks und Collection
  - Login mit Username/Passwort für private Decks & Collection
  - Auto-Discovery aller Decks eines Benutzers
  - Rate-Limiting mit exponentiellem Backoff (kein 429-Spam)
  - Inkrementelles Speichern pro Seite (bei Abbruch bleibt der Fortschritt erhalten)
  - Robuster Sync: Stale-Entry-Bereinigung nur bei vollständigem Sync
- **Scryfall-Integration**: Kartensuche, Preise (USD/EUR), Autocomplete, direkte Scryfall-Links
- **EDHREC-Integration**: Commander-Empfehlungen und Combo-Vorschläge
- **Cardmarket**: Profil-Scraping oder CSV-Import, Preisdaten-Sync, Preis-Spike-Erkennung
  - Täglicher Preis-Sync über Cardmarket JSON-Feeds (nur eigene Karten)
  - Preisverlauf-Sparklines (30 Tage) beim Hovern über Kartennamen
  - Automatische Preis-Spike-Alerts mit Verkaufsempfehlungen für ungenutzte Kopien
- **MCP-Server**: Streamable HTTP-Endpoint für AI-Assistenten (Claude, etc.)
  - 19 Tools inkl. Preisalerts, Preisverlauf, Deck-Nutzung, Preis-Sync, Doubletten, Listings verwalten
- **Web-UI**: React-Frontend mit Fluent UI
  - Dashboard: Übersichtskarten mit Statistiken + Preis-Spike-Alerts
  - Decks: Einklappbare Ordner, Bracket-Badges, Deck-Previews
  - Deck-Detail: Commander-Header, kompakte Kartentabelle, Sideboard-Trennung, Scryfall- und EDHREC-Links
  - Collection: Set-Filter, Deck-Filter, Gruppierung nach Kartenname, Deck-Nutzungs-Spalte
  - Duplicates: Doubletten-Ansicht mit Verkaufsdialog für Cardmarket-Listings
  - Cardmarket: Preisalerts, Sparkline-Graphen, CSV Import/Export, Source-Tracking
  - Karten-Hover: Scryfall-Vorschaubild + Oracle-Text
- **Home Assistant Ingress**: Nahtlose Einbindung ins HA-Panel

---

## Installation

### Als Home Assistant Add-on

1. Repository als lokales Add-on einrichten:
   ```
   /addons/mtg-collection/
   ```
2. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → Lokale Add-ons** → „MTG Collection Manager" installieren
3. Add-on konfigurieren (siehe [Konfiguration](#konfiguration))
4. Add-on starten — erscheint als Panel „MTG Collection" in der Sidebar

### Manuell (Entwicklung)

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

## Konfiguration

Alle Optionen werden über die Home Assistant Add-on-Konfiguration (UI) gesetzt und landen in `/data/options.json`.

| Option | Typ | Standard | Beschreibung |
|---|---|---|---|
| `archidekt_username` | string | `""` | Archidekt-Benutzername für Deck-Discovery & Sync |
| `archidekt_password` | password | `""` | Archidekt-Passwort (für private Decks & Collection) |
| `archidekt_user_id` | int | `0` | Archidekt User-ID (aus der Collection-URL, z.B. `123456`) |
| `archidekt_deck_ids` | list[int] | `[]` | Deck-IDs zum Syncen (leer = Auto-Discovery aller Decks) |
| `sync_enabled` | bool | `true` | Tägliche automatische Synchronisierung aktivieren |
| `sync_hour` | int (0–23) | `3` | Uhrzeit für den täglichen Sync |
| `mcp_auth_token` | string | `""` | Optionaler Bearer-Token für MCP-Server-Authentifizierung |
| `cardmarket_username` | string | `""` | Cardmarket-Benutzername für Profil-Scraping |
| `mqtt_enabled` | bool | `false` | MQTT-Sensor-Publishing aktivieren (HA Auto-Discovery) |
| `mqtt_host` | string | `""` | MQTT-Broker Hostname (z.B. `core-mosquitto` für HA Add-on) |
| `mqtt_port` | int | `1883` | MQTT-Broker Port |
| `mqtt_username` | string | `""` | MQTT-Benutzername |
| `mqtt_password` | password | `""` | MQTT-Passwort |
| `mqtt_topic_prefix` | string | `"mtg-collection"` | Prefix für MQTT State-Topics |

### Minimale Konfiguration

```yaml
archidekt_username: "DeinUsername"
```

### Vollständige Konfiguration (mit privaten Decks & Collection)

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

## Architektur

### Projektstruktur

```
mtg-collection-ha/
├── config.yaml              # HA Add-on Metadaten
├── build.yaml               # HA Build-Konfiguration (Base Images)
├── Dockerfile               # Multi-Stage Build (Node → Python)
├── run.sh                   # Entrypoint: Ingress-Erkennung → Uvicorn
├── CHANGELOG.md             # Versionsverlauf
├── mcp-proxy.mjs            # Lokaler stdio→HTTP MCP-Proxy für Claude Desktop
├── backend/
│   ├── requirements.txt     # Python-Abhängigkeiten
│   └── app/
│       ├── main.py          # FastAPI App, Lifespan, Router-Mounting
│       ├── config.py        # Pydantic Settings (aus options.json)
│       ├── database.py      # SQLite-Schema, Init, Connection
│       ├── scheduler.py     # APScheduler für täglichen Sync
│       ├── version.py       # VERSION = "0.4.0"
│       ├── mcp_server.py    # MCP-Server (16 Tools, 2 Prompts)
│       ├── clients/
│       │   ├── archidekt.py # Archidekt API Client (Auth, Decks, Collection)
│       │   ├── scryfall.py  # Scryfall API Client (Suche, Preise)
│       │   ├── edhrec.py    # EDHREC JSON Client (Recommendations, Combos)
│       │   └── cardmarket.py# Cardmarket Web Scraper
│       ├── models/
│       │   └── schemas.py   # Pydantic-Modelle (Request/Response)
│       ├── routers/
│       │   ├── cards.py     # /api/cards/* (Scryfall-Proxy, EDHREC)
│       │   ├── decks.py     # /api/decks/* (Deck-Liste, Detail)
│       │   ├── collection.py# /api/collection/* (CRUD)
│       │   ├── cardmarket.py# /api/cardmarket/* (CSV, Sync, Listings)
│       │   ├── sync.py      # /api/sync/* (Trigger, Status, History)
│       │   └── stats.py     # /api/stats/ (Sammlung-Statistiken)
│       └── services/
│           ├── sync_service.py      # Archidekt→DB Sync-Logik
│           ├── cardmarket_import.py # Cardmarket CSV/Scrape Import
│           └── cardmarket_prices.py # Cardmarket Preisdaten-Sync & Alerts
├── frontend/
│   ├── package.json         # React 18, Fluent UI, React Router, Vite
│   ├── vite.config.ts       # Vite Build-Config
│   ├── tsconfig.json        # TypeScript-Konfiguration
│   ├── index.html           # SPA Entry Point
│   └── src/
│       ├── main.tsx         # React Root, FluentProvider, BrowserRouter
│       ├── App.tsx          # Tab-Navigation, Routes
│       ├── api.ts           # API Client (fetch-basiert, Ingress-aware)
│       ├── pages/
│       │   ├── Dashboard.tsx   # Übersicht: Stats, Sync-Status
│       │   ├── Decks.tsx       # Deck-Grid mit Vorschaubildern
│       │   ├── DeckView.tsx    # Deck-Detail nach Kategorie
│       │   ├── Collection.tsx  # Kartensammlung mit Suche
│       │   ├── Cardmarket.tsx  # Cardmarket Listings, CSV Import
│       │   └── Settings.tsx    # Sync-Konfiguration, History
│       └── components/
│           ├── ManaSymbol.tsx      # {W}{U}{B} → Scryfall SVG Icons
│           └── CardHoverPreview.tsx# Karten-Hover zeigt Scryfall-Bild
└── translations/
    └── en.yaml              # Englische UI-Texte für HA Config
```

### Backend

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, aiosqlite, httpx, APScheduler, Pydantic, MCP SDK

Der Backend-Server wird über `run.sh` gestartet, das die Supervisor-API abfragt, um den Ingress-Pfad zu ermitteln. Anschließend startet Uvicorn die FastAPI-App auf Port 8099.

#### Lifecycle (Lifespan)

1. **Startup**: Datenbank initialisieren → Cardmarket-Scraper konfigurieren → Scheduler starten → MCP-Session-Manager starten → (optional) Cardmarket-Sync im Hintergrund
2. **Laufzeit**: API-Requests, geplante Syncs, MCP-Anfragen
3. **Shutdown**: Scheduler stoppen → Datenbank schließen

#### API-Clients

| Client | Datei | Basis-URL | Rate-Limiting |
|---|---|---|---|
| Archidekt | `clients/archidekt.py` | `https://archidekt.com` | 2s Delay + Backoff (4/8/16/32s bei 429) |
| Scryfall | `clients/scryfall.py` | `https://api.scryfall.com` | 100ms zwischen Requests |
| EDHREC | `clients/edhrec.py` | `https://json.edhrec.com/pages` | 24h In-Memory-Cache |
| Cardmarket | `clients/cardmarket.py` | `https://www.cardmarket.com` | 1.5s zwischen Seiten |

#### Sync-Service

Der `sync_service.py` implementiert den Haupt-Synchronisierungsprozess:

1. **Archidekt-Login** (falls Credentials vorhanden)
2. **Collection-Sync** (falls authentifiziert + User-ID gesetzt) — seitenweise mit DB-Commit pro Seite
3. **Deck-Discovery** — Auto-Entdeckung via Username oder explizite IDs
4. **Deck-Sync** — Jedes Deck einzeln mit 1.5s Pause dazwischen
5. **Logging** — Jeder Sync wird in der `sync_log`-Tabelle protokolliert

### Frontend

**Tech Stack:** React 18, Fluent UI v9, React Router v7, Vite, TypeScript

Die SPA wird im Multi-Stage Docker Build mit Node.js 20 gebaut und dann als statische Dateien vom Backend ausgeliefert (`/static`).

#### Seiten

| Seite | Route | Beschreibung |
|---|---|---|
| Dashboard | `/` | Übersichtskarten (Total Cards, Value, Decks, Sync-Status) |
| Decks | `/decks` | Einklappbare Ordner, Bracket-Badges, Commander, Format |
| Deck Detail | `/decks/:id` | Commander-Header, kompakte Kartentabelle, Sideboard-Trennung, Scryfall-Links |
| Collection | `/collection` | Set-Filter, Gruppierung nach Name, Deck-Nutzungs-Spalte, Scryfall-Links |
| Cardmarket | `/cardmarket` | Listings, CSV-Import, Preis-Sync, Sparklines, Preis-Spike-Alerts |
| Settings | `/settings` | Sync-Konfiguration, manueller Trigger, Sync-History |

#### Ingress-Handling

Die API-Base-URL wird dynamisch aus dem Pfad extrahiert:
```typescript
// /api/hassio_ingress/<token>/decks/1 → /api/hassio_ingress/<token>
const match = path.match(/^(\/api\/hassio_ingress\/[^/]+)/);
```
So funktioniert die App sowohl im HA-Ingress als auch standalone.

### Datenbank

SQLite mit WAL-Modus und Foreign Keys. Schema:

| Tabelle | Beschreibung |
|---|---|
| `cards` | Alle Karten (Scryfall-ID, Name, Mana, Preise, …) |
| `decks` | Deck-Metadaten (Name, Format, Commander, Bracket, Archidekt-ID) |
| `deck_cards` | Zuordnung Karte→Deck (Quantity, Category, Commander-Flag) |
| `collection` | Persönliche Sammlung (Quantity, Foil, Condition, Language) |
| `cardmarket_listings` | Cardmarket-Angebotslistungen |
| `cardmarket_products` | Cardmarket-Produkte gematcht auf eigene Karten |
| `cardmarket_price_history` | Tägliche Preisdaten (Avg, Low, Trend, Avg1/7/30) |
| `sync_log` | Sync-Verlauf (Source, Status, Dauer, Fehler) |
| `schema_version` | DB-Versionierung |

Daten werden unter `/data/mtg.db` persistent gespeichert (HA `data`-Mount).

---

## API-Referenz

Basis-URL: `http://<ha-host>:8123/api/hassio_ingress/<token>`

### Decks

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/decks/` | Alle Decks auflisten |
| `GET` | `/api/decks/{id}` | Deck-Detail mit allen Karten |

### Collection

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/collection/` | Sammlung auflisten (Filter: `search`, `color`, `rarity`, `set_code`, `deck_id`, Paginierung) |
| `GET` | `/api/collection/sets` | Verfügbare Sets in der Sammlung |
| `GET` | `/api/collection/duplicates` | Doubletten auflisten (Karten mit überschüssigen Kopien) |
| `POST` | `/api/collection/` | Karte zur Sammlung hinzufügen (Body: `scryfall_id`, `quantity`, …) |
| `DELETE` | `/api/collection/{id}` | Karte aus Sammlung entfernen |

### Cards (Scryfall-Proxy)

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/cards/search?q=...` | Scryfall-Suche (volle Syntax) |
| `GET` | `/api/cards/named?name=...` | Karte nach exaktem Namen |
| `GET` | `/api/cards/autocomplete?q=...` | Autocomplete-Vorschläge |
| `GET` | `/api/cards/edhrec/recommendations/{name}` | EDHREC-Empfehlungen für Commander |
| `GET` | `/api/cards/edhrec/combos/{name}` | EDHREC-Combos für Commander |

### Cardmarket

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/cardmarket/listings` | Listings auflisten (Filter: `search`, Paginierung) |
| `GET` | `/api/cardmarket/stats` | Statistiken (Anzahl, Gesamtwert) |
| `POST` | `/api/cardmarket/import` | CSV-Datei hochladen und importieren |
| `POST` | `/api/cardmarket/sync` | Profil-Scraping starten |
| `GET` | `/api/cardmarket/export` | Listings als CSV exportieren |
| `GET` | `/api/cardmarket/price-history/{id}` | Preisverlauf für ein Cardmarket-Produkt |
| `GET` | `/api/cardmarket/price-alerts` | Preis-Spike-Alerts für ungenutzte Karten |
| `POST` | `/api/cardmarket/sync-prices` | Manueller Cardmarket-Preisdaten-Sync |
| `GET` | `/api/cardmarket/products` | Gematchte Cardmarket-Produkte auflisten |
| `POST` | `/api/cardmarket/add-listing` | Manuelles Listing erstellen (Body: card_name, quantity, price, …) |
| `DELETE` | `/api/cardmarket/clear-listings` | Alle Listings löschen |

### Sync

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/sync/status` | Aktueller Sync-Status und Konfiguration |
| `GET` | `/api/sync/history` | Letzte 20 Sync-Einträge |
| `POST` | `/api/sync/trigger` | Manuellen Sync starten |
| `GET` | `/api/sync/probe-archidekt` | Debug: Archidekt-API-Verbindung prüfen |

### Stats

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/stats/` | Gesamtstatistiken (Cards, Value, Decks, Cardmarket) |

---

## MCP-Server (AI-Integration)

Der integrierte MCP-Server (Model Context Protocol) ermöglicht es AI-Assistenten wie Claude, direkt auf die Sammlung zuzugreifen.

**Transport:** Streamable HTTP (stateless, JSON responses)
**Endpoint:** `/mcp` (über HA Ingress erreichbar)
**Authentifizierung:** Wenn `mcp_auth_token` in der Add-on-Konfiguration gesetzt ist, muss jede Anfrage an `/mcp` den Header `Authorization: Bearer <token>` enthalten. Bei fehlendem oder falschem Token: HTTP 401. Ist der Token leer, bleibt der Endpoint ohne Auth zugänglich (Backward-Compat).

### Verfügbare Tools

| Tool | Beschreibung |
|---|---|
| `search_card` | Scryfall-Kartensuche (volle Syntax) |
| `get_card` | Karte nach exaktem Namen mit allen Details |
| `list_decks` | Alle gesyncten Decks auflisten (mit Ordner, Bracket) |
| `get_deck` | Deck-Detail mit Kartenliste und Bracket |
| `search_collection` | Sammlung nach Name durchsuchen |
| `get_collection_stats` | Sammlungs-Statistiken (Karten, Wert, Decks) |
| `get_cardmarket_listings` | Cardmarket-Angebote auflisten |
| `get_card_price` | Aktuelle Preise über Scryfall |
| `get_edhrec_recommendations` | EDHREC-Empfehlungen für Commander |
| `get_edhrec_combos` | EDHREC-Combos für Commander |
| `trigger_sync` | Manuellen Archidekt-Sync auslösen |
| `get_price_alerts` | Preis-Spike-Alerts für ungenutzte Karten |
| `get_price_history` | Cardmarket-Preisverlauf für eine Karte |
| `get_deck_usage` | In welchen Decks eine Karte verwendet wird |
| `sync_prices` | Manuellen Cardmarket-Preisdaten-Sync starten |
| `get_duplicates` | Doubletten auflisten (Karten mit überschüssigen Kopien) |
| `add_cardmarket_listing` | Manuelles Cardmarket-Listing erstellen |
| `clear_cardmarket_listings` | Alle Cardmarket-Listings löschen |

### Prompts

| Prompt | Parameter | Beschreibung |
|---|---|---|
| `analyze_deck` | `deck_name` | Deck analysieren (Manakurve, Synergien, Verbesserungen) |
| `suggest_upgrades` | `deck_name`, `budget` | Deck-Upgrades innerhalb eines Budgets vorschlagen |

### Claude Desktop anbinden

Der MCP-Server läuft hinter HA Ingress und erfordert einen lokalen stdio→HTTP Proxy (`mcp-proxy.mjs`), der die Authentifizierung übernimmt.

#### Voraussetzungen

- Node.js installiert (lokal)
- HA Long-Lived Access Token (Profil → Sicherheit → Tokens)
- Ingress-Token des Add-ons (aus der URL oder Supervisor API)

#### 1. Proxy testen

```bash
cd /pfad/zu/mtg-collection-ha
npm install  # installiert ws-Paket

echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | \
node mcp-proxy.mjs \
  http://<HA_IP>:8123 \
  <LONG_LIVED_TOKEN> \
  /api/hassio_ingress/<INGRESS_TOKEN>/mcp \
  <MCP_AUTH_TOKEN>
```

> **Hinweis:** Das vierte Argument `<MCP_AUTH_TOKEN>` ist optional. Alternativ kann die Umgebungsvariable `MCP_AUTH_TOKEN` gesetzt werden.

#### 2. Claude Desktop konfigurieren

Datei: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "mtg-collection": {
      "command": "node",
      "args": [
        "/pfad/zu/mtg-collection-ha/mcp-proxy.mjs",
        "http://<HA_IP>:8123",
        "<LONG_LIVED_TOKEN>",
        "/api/hassio_ingress/<INGRESS_TOKEN>/mcp",
        "<MCP_AUTH_TOKEN>"
      ]
    }
  }
}
```

#### 3. Claude Desktop neu starten

Nach dem Neustart erscheint „MTG Collection Manager" als verfügbarer MCP-Server mit 11 Tools.

#### Wie der Proxy funktioniert

```
Claude Desktop ↔ stdio ↔ mcp-proxy.mjs ↔ HTTP ↔ HA Ingress ↔ Add-on /mcp
```

> **Hinweis:** Port 8099 ist nur intern im HA-Netzwerk erreichbar. Der einzige offizielle Zugangsweg von außen ist über HA Ingress mit dem `mcp-proxy.mjs`.

1. Proxy verbindet sich per WebSocket zur HA-API und authentifiziert sich
2. Erzeugt eine Ingress-Session (Cookie)
3. Leitet JSON-RPC-Nachrichten von stdin an den HTTP-Endpoint weiter
4. Antwortet auf stdout mit den Ergebnissen
5. Erneuert die Session automatisch bei 401/403

---

## Externe Dienste

| Dienst | Nutzung | Authentifizierung |
|---|---|---|
| [Archidekt](https://archidekt.com) | Deck-Sync, Collection-Sync | Optional: Username/Password (JWT) |
| [Scryfall](https://scryfall.com/docs/api) | Kartensuche, Preise, Bilder | Keine (öffentliche API, 100ms Rate-Limit) |
| [EDHREC](https://edhrec.com) | Commander-Empfehlungen, Combos | Keine (inoffizielle JSON-Endpoints, 24h Cache) |
| [Cardmarket](https://cardmarket.com) | Angebotslistungen | Keine (öffentliches Profil-Scraping oder CSV) |

---

## Entwicklung

### Voraussetzungen

- Python 3.12+
- Node.js 20+
- Docker (für HA Add-on Build)

### Lokaler Start

```bash
# Backend (Terminal 1)
cd backend
pip install -r requirements.txt
export DATA_DIR=./data
export OPTIONS_PATH=./data/options.json
export CORS_ORIGINS=http://localhost:5173  # CORS für Standalone-Dev aktivieren
python -m uvicorn app.main:app --reload --port 8099

# Frontend (Terminal 2)
cd frontend
npm install
npm run dev  # Startet Vite Dev Server mit Proxy auf localhost:8099
```

### Docker Build

```bash
docker build -t mtg-collection .
docker run -p 8099:8099 -v $(pwd)/data:/data mtg-collection
```

### Auf Home Assistant deployen

```bash
scp -r ./* root@homeassistant.local:/addons/mtg-collection/
# Dann in HA: Add-on neu bauen (Rebuild)
```

### Projekt-Konventionen

- **Backend**: Singleton-Pattern für API-Clients (`archidekt`, `scryfall`, `edhrec`, `cardmarket_scraper`)
- **Frontend**: Fluent UI v9 Komponenten, funktionale React-Komponenten mit Hooks
- **Datenbank**: Alle Schema-Migrationen in `database.py` SCHEMA_SQL
- **API**: RESTful, JSON, FastAPI-Router mit Pydantic-Modellen
- **Fehlerbehandlung**: Exponentieller Backoff bei Rate-Limiting, inkrementelles Speichern bei Sync

### Linting & Type-Checking

```bash
cd backend
ruff check .
mypy .
```

Konfiguration in `backend/pyproject.toml` (line-length 100, strict mypy).

### Umgebungsvariablen (Entwicklung)

| Variable | Default | Beschreibung |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Log-Level (DEBUG, INFO, WARNING, ERROR) |
| `DATA_DIR` | `/data` | Pfad zum Datenverzeichnis |
| `OPTIONS_PATH` | `/data/options.json` | Pfad zur HA-Options-Datei |
| `CORS_ORIGINS` | (leer) | Komma-getrennte CORS-Origins |

---

## Changelog

### 0.5.0

#### Hinzugefügt
- **Duplicates-Tab**: Neuer Tab zeigt alle Karten mit überschüssigen Kopien (Owned > In Decks)
  - Verkaufsdialog: Direkt Cardmarket-Listings aus Doubletten erstellen (Preis, Zustand, Sprache, Menge)
  - Paginierung und Suche
- **Dashboard Price Alerts**: Preis-Spike-Alerts jetzt auf dem Dashboard (statt Sync-Status)
  - Gruppiert nach Preis-Tiers mit einklappbaren Gruppen
- **Collection Deck-Filter**: Dropdown zum Filtern der Collection nach Deck
- **EDHREC-Link**: Deck-Detailansicht zeigt EDHREC-Link zum Commander
- **Cardmarket Source Tracking**: Listings unterscheiden zwischen Import (CSV) und manuell erstellten Einträgen
  - Farbige Markierung manueller Einträge in der Listings-Tabelle
  - CSV-Re-Import verschmilzt manuelle Einträge wenn Kartenname übereinstimmt
- **Clear Listings Button**: Settings-Seite hat Button zum Löschen aller Cardmarket-Listings
- **MCP-Server**: 3 neue Tools (get_duplicates, add_cardmarket_listing, clear_cardmarket_listings)

#### Geändert
- Dashboard zeigt keine Sync-Status-Karte mehr (nach Settings verschoben)
- Cardmarket CSV-Import bewahrt manuelle Einträge beim Re-Import

### 0.4.2

#### Hinzugefügt
- **Collection Paginierung**: Server-seitige Paginierung (100 pro Seite) statt alle 6000+ Einträge auf einmal
- **Price Alert Tier-Gruppierung**: Alerts nach Preis-Tiers gruppiert mit einklappbaren Gruppen

### 0.4.1

#### Behoben
- **Collection Performance**: CTE mit LEFT JOIN statt korrelierter O(n²)-Subquery für Deck-Nutzung
- **Cardmarket Preis-Sync**: 403-Fehler wird als Ende der Seitenliste behandelt (nicht nur 404)

### 0.4.0

#### Hinzugefügt
- **Cardmarket Preisdaten-Sync**: Täglicher automatischer Sync über Cardmarket JSON-Feeds
  - Nur eigene Karten werden gematcht und gespeichert
  - Preisverlauf (Avg, Low, Trend, Avg1/7/30) in neuer `cardmarket_price_history`-Tabelle
  - Sparkline-Graphen (30 Tage) beim Hovern über Kartennamen im Cardmarket-Tab
  - "Sync Prices"-Button für manuellen Preis-Sync
- **Preis-Spike-Erkennung**: Automatische Alerts wenn Trend > 30% über 30-Tage-Durchschnitt
  - Verkaufsempfehlungen für ungenutzte Kopien (nicht in Decks verwendet)
  - Alert-Sektion auf der Cardmarket-Seite
- **Deck-Bracket**: Bracket-Wert aus Archidekt extrahiert und angezeigt
- **Einklappbare Deck-Ordner**: Ordner auf der Decks-Seite standardmäßig eingeklappt
- **Deck-Detail überarbeitet**: Commander-Bild als Header, Bracket-Badge, Farbidentitäts-Punkte, Gesamtwert, Archidekt-Link, kompakte Kartentabelle ohne Bilder
- **Sideboard/Maybeboard-Trennung**: Nicht-Deck-Kategorien als abgedimmter Bereich am Ende
- **Scryfall-Links**: Klick auf Kartennamen öffnet Scryfall in neuem Tab (Decks & Collection)
- **Collection Set-Filter**: Dropdown zum Filtern nach Set
- **Collection Gruppierung**: Karten nach Name gruppiert, einklappbar
- **Deck-Nutzungs-Spalte**: "In Decks"-Spalte in der Collection-Ansicht
- **Oracle-Text im Hover**: Kartentext wird unter dem Vorschaubild angezeigt
- **MCP-Server**: 5 neue Tools (get_price_alerts, get_price_history, get_deck_usage, sync_prices)
- **Cardmarket-Produkt-Tabelle**: DB-Tabelle für gematchte Produkte mit Card-FK

#### Behoben
- **Collection-Datenverlust beim Sync**: Stale-Entry-Bereinigung nur bei vollständigem Sync (sync_complete-Flag)
- **Collection-Anzeige leer**: page_size-Limit auf 5000 erhöht (war 1000, Frontend fragte 5000 an)

### 0.3.0

#### Hinzugefügt
- Archidekt-Authentifizierung (Login für private Decks & Collection)
- Collection-Sync direkt über Archidekt Collection API
- Cardmarket-Profil-Scraping als Alternative zum CSV-Import
- Automatischer Cardmarket-Sync bei Start und globalem Sync
- MCP-Server mit 11 Tools und 2 Prompts (Streamable HTTP)
- Card-Hover-Preview mit Scryfall-Bildern
- Mana-Symbol-Rendering via Scryfall SVG API

#### Geändert
- Collection wird direkt aus Archidekt ausgelesen (nicht mehr aus Deck-Karten)
- Deck-Sync fügt Karten nicht mehr automatisch zur Collection hinzu

#### Behoben
- Rate-Limiting (429) mit exponentiellem Backoff
- Inkrementelles Speichern bei Collection-Sync
- API-Base-URL korrekt aus Ingress-Pfad extrahiert

### 0.2.0

#### Behoben
- Docker: HA Base Image durch `python:3.12-alpine` ersetzt (s6-overlay PID 1 Crash)
- run.sh: bashio-Abhängigkeit entfernt, plain `sh` mit Supervisor-API
- Frontend: API-Base-URL dynamisch aus Ingress-Pfad
- MCP-Server Import/Mount fehlertolerant

#### Hinzugefügt
- CHANGELOG.md für Home Assistant Add-on Updates
- Zentralisierte Version in `version.py`

### 0.1.0

#### Hinzugefügt
- Initiales Release
- Archidekt Deck-Sync mit konfigurierbarem Zeitplan
- Scryfall Kartensuche und Preisabfrage
- EDHREC Commander-Empfehlungen und Combos
- Collection-Verwaltung mit SQLite
- Cardmarket CSV-Import
- MCP Server (Streamable HTTP)
- Fluent UI React Frontend
- Home Assistant Ingress-Integration
