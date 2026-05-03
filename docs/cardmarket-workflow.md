# Cardmarket Workflow — CSV-basiertes Listing-Management

Verwalte deine Cardmarket-Listings über CSV-Roundtrips. Da Cardmarket keine offene Sync-API für Stocks anbietet, ist CSV der zuverlässigste Weg.

---

## 1. Warum kein Auto-Sync?

Cardmarket schützt seine Seiten mit Cloudflare und hat keine öffentliche API für Stock-Management (nur die kostenpflichtige MKM-API für Pro-Seller). Profile-Scraping wird aktiv geblockt.

Unsere Lösung: **CSV-Import/Export** — offiziell von Cardmarket unterstützt, zuverlässig, und ohne Risiko einer Account-Sperre.

---

## 2. Der 5-Step-Roundtrip

### ① Export von Cardmarket

1. Gehe zu [cardmarket.com](https://www.cardmarket.com) → **Stock** → **My Stock**
2. Klicke **"Export to CSV"**
3. Die CSV-Datei enthält alle deine aktuellen Listings

<!-- TODO: screenshot of Cardmarket CSV export button -->

### ② Import ins Add-on

1. Öffne das Add-on → **Cardmarket**
2. Klicke **"Import CSV"** oder nutze den Button im Workflow-Banner
3. Wähle die heruntergeladene CSV-Datei
4. Das Add-on importiert alle Listings (Duplikate werden aktualisiert)

<!-- TODO: screenshot of import button in add-on -->

### ③ Bearbeiten im Add-on

- Preise anpassen
- Karten für Verkauf markieren
- Preis-Spike-Alerts beachten (automatisch erkannte Preisanstiege)
- Doubletten aus der Sammlung als Listings hinzufügen

### ④ Re-Export als CSV

1. Klicke **"Export CSV"** im Add-on
2. Die CSV enthält alle deine Änderungen im Cardmarket-kompatiblen Format

### ⑤ Upload auf Cardmarket

Die exportierte CSV kann auf Cardmarket re-importiert werden:
- **Manuell**: Cardmarket → Stock → Import → CSV-Datei hochladen
- **Per Browser-Extension**: siehe [Abschnitt 3](#3-browser-extensions)
- **Per MKM-API**: siehe [Abschnitt 4](#4-mkm-api-für-power-user)

---

## 3. Browser-Extensions

Für effizientere Bulk-Updates auf Cardmarket:

### cardmarket-bulk-import

- **Repo**: [github.com/PedroPerpetua/cardmarket-bulk-import](https://github.com/PedroPerpetua/cardmarket-bulk-import)
- Ermöglicht Massen-Upload von Stock-Änderungen direkt im Browser
- Unterstützt Preis-Updates und Mengen-Änderungen

> ⚠️ **Hinweis**: Dies ist keine offizielle Cardmarket-Extension. Nutzung auf eigene Verantwortung. Halte dich an Cardmarkets Nutzungsbedingungen.

---

## 4. MKM-API für Power-User

Cardmarket bietet eine [offizielle API](https://api.cardmarket.com/ws/documentation) mit OAuth1-Authentifizierung.

**Status im Add-on**: Noch nicht integriert. Geplant als zukünftiges Feature für automatisierte Preis-Updates.

**Was die API kann**:
- Stock-Management (Listings CRUD)
- Order-Management
- Account-Informationen
- Marketplace-Suche

**Voraussetzungen**:
- Cardmarket-Seller-Account (mindestens "Private Seller")
- API-Key beantragen in den Cardmarket Account-Settings

---

## 5. Preis-Sync (automatisch)

Unabhängig vom CSV-Workflow holt das Add-on **täglich automatisch Preisdaten**:

- Quelle: Offizielle Cardmarket JSON-Preisfeeds (kein Scraping!)
- Umfang: Nur Karten die du besitzt oder gelistet hast
- Daten: Trend, 30-Tage-Durchschnitt, Tiefstpreis
- Ergebnis: Preis-Sparklines und Spike-Alerts im UI

Du kannst den Preis-Sync auch manuell auslösen:
- Im UI: Cardmarket-Page → **"Sync Prices"** Button
- Per MCP: Tool `sync_prices` ([MCP Setup](mcp-setup.md))

---

## 6. Häufige Fragen

### Kann ich meine Wantlist exportieren?

Ja! Das Add-on hat eine eigene Wishlist mit Export-Funktion. Siehe die **Wishlist-Page** im Add-on.

### Warum erscheinen meine manuellen Einträge nach CSV-Re-Import doppelt?

Der Import matcht Karten über **exakten Namen + Set + Zustand + Sprache**. Wenn ein manueller Eintrag andere Metadaten hat als der CSV-Eintrag, wird er als separates Listing behandelt.

**Lösung**: Vor dem Re-Import bestehende Listings löschen (Settings → "Clear All Listings") oder sicherstellen dass Name/Set/Condition identisch sind.

### Wie oft muss ich CSV importieren?

**Empfehlung**: Nach jedem Verkauf auf Cardmarket. Cardmarket aktualisiert deine Stock-Menge automatisch nach Verkäufen, aber das Add-on weiß davon nichts ohne neuen CSV-Import.

Ein guter Rhythmus: einmal pro Woche oder nach größeren Verkaufstagen.

### Kann das Add-on automatisch auf Cardmarket verkaufen?

Nein. Das Add-on verwaltet nur deine **Listings-Daten lokal**. Der tatsächliche Verkauf läuft weiterhin über cardmarket.com. Das Add-on hilft dir bei:
- Preis-Optimierung (Spike-Alerts)
- Identifikation von Karten die du verkaufen könntest (Doubletten)
- Export in Cardmarket-kompatiblem Format
