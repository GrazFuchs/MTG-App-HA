# MCP Setup für Claude Desktop

Verbinde dein MTG Collection Manager Add-on mit Claude Desktop, um deine Sammlung per natürlicher Sprache zu durchsuchen, Preise abzufragen und Decks zu analysieren.

---

## 1. Voraussetzungen

- **Claude Desktop** installiert ([claude.ai/download](https://claude.ai/download))
- **MTG Collection Manager** Add-on läuft in Home Assistant
- Zugriff auf **Home Assistant** → Profil → Sicherheit (für Long-Lived Token)
- **Node.js** ≥ 18 auf dem Rechner, auf dem Claude Desktop läuft

---

## 2. Quick-Setup via Add-on UI

Der einfachste Weg: über die **Settings-Page** im Add-on.

1. Öffne das Add-on → **Settings** (Zahnrad-Icon)
2. Scrolle zu **"MCP Setup for Claude Desktop"**
3. Klicke **"⬇ mcp-proxy.mjs herunterladen"** → speichere die Datei an einem permanenten Ort (z.B. `~/mcp/mcp-proxy.mjs`)
4. Erstelle einen **Long-Lived Token** (siehe [Abschnitt 4](#4-token-erstellen))
5. Klicke **"📋 Copy to clipboard"** beim Config-Snippet
6. Füge das Snippet in deine `claude_desktop_config.json` ein (Pfade siehe unten)
7. Ersetze die Platzhalter:
   - `<PATH_TO>` → absoluter Pfad zu deiner `mcp-proxy.mjs`
   - `<TODO: your long-lived token>` → den Token aus Schritt 4
8. **Claude Desktop neu starten** (komplett beenden + öffnen)

---

## 3. Manueller Setup

Falls du keinen Zugriff auf die Settings-Page hast oder CLI bevorzugst:

### Proxy-Datei herunterladen

```bash
curl -o ~/mcp/mcp-proxy.mjs https://<YOUR_HA_URL>/api/mcp/proxy.mjs
```

### Config-Datei bearbeiten

Pfad zur `claude_desktop_config.json`:

| OS | Pfad |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

### Config-Snippet

```json
{
  "mcpServers": {
    "mtg-collection": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-proxy.mjs"],
      "env": {
        "MTG_BASE_URL": "https://<YOUR_HA_URL>",
        "MTG_TOKEN": "<YOUR_LONG_LIVED_TOKEN>",
        "MTG_SSE_ENDPOINT": "https://<YOUR_HA_URL>/mcp/sse"
      }
    }
  }
}
```

> ⚠️ Verwende **absolute Pfade** — relative Pfade funktionieren nicht zuverlässig.

---

## 4. Token erstellen

1. Öffne Home Assistant
2. Klicke auf dein **Profil** (unten links)
3. Scrolle zu **Sicherheit** → **Long-Lived Access Tokens**
4. Klicke **Token erstellen**
5. Name: z.B. `MTG Claude Desktop`
6. Token kopieren — er wird nur einmal angezeigt!

<!-- TODO: screenshot of HA token page -->

---

## 5. Verbindung testen

Nach dem Neustart von Claude Desktop:

1. Öffne ein neues Gespräch
2. Frage: **"What's on my MTG wishlist?"**
3. Claude sollte das Tool `get_wishlist` aufrufen und deine Wishlist anzeigen

Weitere Test-Prompts:
- "How much is my collection worth?"
- "Show me my deck list"
- "What are the price spikes in my Cardmarket listings?"

---

## 6. Troubleshooting

### "Connection refused"

- Prüfe ob das Add-on läuft (HA → Add-ons → MTG Collection Manager → Status)
- Die URL muss die **Ingress-URL** sein, nicht `localhost:8099`
- Von extern: stelle sicher dass dein HA per HTTPS erreichbar ist

### "Tool not found"

- Claude Desktop **komplett neu starten** (nicht nur das Fenster schließen)
- Prüfe ob die `claude_desktop_config.json` valides JSON ist
- Prüfe: `node /path/to/mcp-proxy.mjs` — sollte ohne Fehler starten

### "401 Unauthorized"

- Token korrekt in `MTG_TOKEN` eingefügt?
- Keine Leerzeichen oder Zeilenumbrüche im Token?
- Token nicht abgelaufen? (Long-Lived Tokens laufen nicht ab, aber können gelöscht werden)

### "Server disconnected" / "ENOENT"

- Pfad zu `mcp-proxy.mjs` muss **absolut** sein (z.B. `/Users/me/mcp/mcp-proxy.mjs`)
- Datei muss existieren und lesbar sein: `ls -la /path/to/mcp-proxy.mjs`

---

## 7. Verfügbare MCP-Tools

| Tool | Beschreibung |
|------|-------------|
| `search_card` | Kartensuche via Scryfall |
| `get_card` | Karten-Details abrufen |
| `list_decks` | Alle Decks auflisten |
| `get_deck` | Deck-Details mit Kartenliste |
| `search_collection` | Sammlung durchsuchen |
| `get_collection_stats` | Sammlungs-Statistiken |
| `get_card_price` | Aktueller Preis einer Karte |
| `get_cardmarket_listings` | Cardmarket-Listings anzeigen |
| `get_price_alerts` | Preis-Spike-Alerts |
| `get_price_history` | 30-Tage-Preisverlauf |
| `get_duplicates` | Doubletten mit Verkaufsempfehlung |
| `suggest_what_to_sell` | KI-Verkaufsempfehlungen |
| `get_wishlist` | Wishlist anzeigen |
| `add_to_wishlist` | Karte zur Wishlist hinzufügen |
| `set_deck_ai_assessment` | AI-Bewertung für ein Deck schreiben |
| `get_edhrec_recommendations` | EDHREC-Empfehlungen für Commander |
| `trigger_sync` | Manuellen Sync starten |

Vollständige Liste: siehe [README → MCP-Server](../README.md#mcp-server-ai-integration)
