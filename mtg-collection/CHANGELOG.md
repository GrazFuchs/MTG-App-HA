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
- **Repository-Struktur**: Add-on-Files in `mtg-collection/`-Unterordner verschoben — erforderlich für Home Assistant Custom Repository
- Installation jetzt über HA Add-on Store: Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories → `https://github.com/HerrFuchs/mtg-collection-ha`

### Migration
Wer das Add-on bisher manuell per SCP installiert hat:
1. DB sichern: `cp /data/mtg.db /backup/mtg.db.$(date +%Y%m%d)`
2. Altes Add-on in HA deinstallieren
3. Lokalen Add-on-Ordner löschen: `rm -rf /addons/mtg-collection`
4. Repository-URL in HA hinzufügen und Add-on neu installieren
5. DB wiederherstellen: `cp /backup/mtg.db.YYYYMMDD /data/mtg.db`

## 0.5.1

### Removed
- Cardmarket Profil-Scraping komplett entfernt (FlareSolverr-basiert, unzuverlässig wegen Cloudflare)
- FlareSolverr-Integration und -Konfiguration (`flaresolverr_url`)
- „Sync from Profile"-Button in Cardmarket-UI
- Abhängigkeit: selectolax

### Changed
- Cardmarket-Listings nur noch über CSV-Import oder manuelle Eingabe
- Preisdaten-Sync über offizielle Cardmarket JSON-Feeds bleibt unverändert

## 0.5.0

### Added
- Duplicates-Tab: Zeigt Karten mit überschüssigen Kopien, mit Verkaufsdialog für Cardmarket-Listings
- Dashboard Price Alerts: Preis-Spike-Alerts auf dem Dashboard mit Tier-Gruppierung
- Collection Deck-Filter: Dropdown zum Filtern nach Deck
- EDHREC-Link in Deck-Detailansicht zum Commander
- Cardmarket Source Tracking: Import vs. manuell erstellte Listings
- Clear Listings Button auf Settings-Seite
- MCP-Server: get_duplicates, add_cardmarket_listing, clear_cardmarket_listings Tools

### Changed
- Dashboard zeigt keine Sync-Status-Karte mehr
- CSV-Import bewahrt manuelle Einträge und verschmilzt sie bei Match

## 0.4.2

### Added
- Collection Server-seitige Paginierung (100 pro Seite)
- Price Alert Tier-Gruppierung mit einklappbaren Gruppen

## 0.4.1

### Fixed
- Collection Performance: CTE statt korrelierter O(n²)-Subquery
- Cardmarket Preis-Sync: 403 als Ende der Seitenliste behandelt

## 0.3.0

### Added
- Archidekt-Authentifizierung (Login mit Username/Passwort für private Decks & Collection)
- Collection-Sync direkt über Archidekt Collection API
- Cardmarket CSV-Import für Listings
- Neue Konfigurationsfelder: `archidekt_password`, `archidekt_user_id`, `cardmarket_username`
- Settings-Seite zeigt Authentifizierungsstatus für Archidekt und Cardmarket

### Changed
- Collection wird nun direkt aus Archidekt ausgelesen (nicht mehr aus Deck-Karten aufgebaut)
- Deck-Sync fügt Karten nicht mehr automatisch zur Collection hinzu

### Fixed
- API-Base-URL wird korrekt aus Ingress-Pfad extrahiert (behebt „Deck not found" bei Navigation)
- CHANGELOG-Format für Home Assistant kompatibel gemacht

## 0.2.0

### Fixed
- Dockerfile: `ARG BUILD_FROM` vor erstem `FROM` für korrekte HA-Build-Args
- Dockerfile: `npm ci` durch `npm install` ersetzt (keine `package-lock.json` nötig)
- Icon: `CardMultiple24Regular` durch `Stack24Regular` ersetzt (existiert in @fluentui/react-icons)
- Docker: HA Base Image durch `python:3.12-alpine` ersetzt – behebt s6-overlay PID 1 Crash
- run.sh: bashio-Abhängigkeit entfernt, plain `sh` mit Supervisor-API für Ingress-Info
- Frontend: API-Base-URL dynamisch aus Ingress-Pfad abgeleitet – behebt 404-Fehler
- Frontend: `BrowserRouter basename` für HA Ingress-Routing gesetzt
- Backend: `root_path` aus `INGRESS_ENTRY` für korrekte FastAPI-Redirects
- MCP-Server Import/Mount fehlertolerant (try/except)

### Added
- CHANGELOG.md für Home Assistant Add-on Updates
- Zentralisierte Versionskonstante in `backend/app/version.py`

## 0.1.0

### Added
- Initiales Release
- Archidekt Deck-Sync mit konfigurierbarem Zeitplan
- Scryfall Kartensuche und Preisabfrage
- EDHREC Commander-Empfehlungen und Combos
- Collection-Verwaltung mit SQLite
- Cardmarket CSV-Import
- MCP Server (Streamable HTTP) für AI-Assistenten
- Fluent UI React Frontend mit Dashboard, Decks, Collection, Cardmarket, Settings
- Home Assistant Ingress-Integration
