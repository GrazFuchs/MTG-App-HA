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
- Cardmarket-Profil-Scraping als Alternative zum CSV-Import
- Automatischer Cardmarket-Sync bei App-Start und bei globalem Sync
- Neue Konfigurationsfelder: `archidekt_password`, `archidekt_user_id`, `cardmarket_username`
- Settings-Seite zeigt Authentifizierungsstatus für Archidekt und Cardmarket

### Changed
- Collection wird nun direkt aus Archidekt ausgelesen (nicht mehr aus Deck-Karten aufgebaut)
- Deck-Sync fügt Karten nicht mehr automatisch zur Collection hinzu
- Cardmarket: Profil-Scraping ersetzt OAuth-API (API nicht zugänglich)

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
