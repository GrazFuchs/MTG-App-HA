# Sprint-Plan: HA-Dashboard-Integration (Sprints 28–32)

Ziel: Inbox, Verkaufs-Kandidaten und Deck-Performance als Home-Assistant-Entities
verfügbar machen — inklusive eines Schreibpfads, um gespielte Runden direkt aus HA
einzutragen. Alles über MQTT Discovery, aufbauend auf der bestehenden
`services/ha_publisher.py`.

Stand vor Sprint 28 (v0.27.0): 14 Aggregat-Sensoren, Wishlist-Einzelsensoren,
4 MQTT-Services (`trigger_sync`, `sync_prices`, `add_to_wishlist`, `mark_acquired`).

---

## Datenmodell: welche Entities entstehen

### Inbox / Triage (`acquisition_events`)

| Entity | State | Attribute |
|---|---|---|
| `sensor.mtg_inbox_pending` | Anzahl offener Karten | Top-10: Name, Set, Menge, Vorschlag (`keep`/`sold_new`/`swap`), geschätzter Preis |
| `sensor.mtg_inbox_needs_sell` | Anzahl mit Verkaufs-Vorschlag | – |
| `sensor.mtg_inbox_needs_keep` | Anzahl mit Behalten-Vorschlag | – |
| `sensor.mtg_inbox_pending_value_eur` | Marktwert der offenen Inbox | – |
| `sensor.mtg_inbox_oldest_age_days` | Alter der ältesten offenen Karte | Trigger für „liegt zu lange rum" |
| `sensor.mtg_inbox_decided_30d` | Entscheidungen der letzten 30 Tage | Aufschlüsselung nach `triage_state` |
| `binary_sensor.mtg_inbox_has_pending` | on/off | für Badges/Automationen |

### Verkaufen (`sell_advisor`, Duplicates, `listing_health`, MTGStocks)

| Entity | State | Attribute |
|---|---|---|
| `sensor.mtg_sell_candidates` | Anzahl empfohlener Verkaufskarten | Top-10: `copies_to_sell`, Trend, erwarteter Erlös, Grund |
| `sensor.mtg_sell_potential_eur` | Summe erwarteter Erlös | – |
| `sensor.mtg_duplicates_surplus_cards` | Überschüssige Kopien gesamt | – |
| `sensor.mtg_duplicates_surplus_value_eur` | Wert der Überschüsse | – |
| `sensor.mtg_unlisted_value_eur` | Wert noch nicht gelisteter Duplikate | Top-10 Kandidaten |
| `sensor.mtg_signals_sell` / `sensor.mtg_signals_buy` | MTGStocks: eigene Karten nahe ATH / Wishlist nahe ATL | Kartenliste |

Bestehen bleiben: `listings_underpriced` / `_overpriced` / `_fair`.

### Deck-Performance (`deck_games`)

| Entity | State | Attribute |
|---|---|---|
| `sensor.mtg_games_30d` | Runden der letzten 30 Tage | – |
| `sensor.mtg_winrate_30d` | Siegquote in % | W/L/D |
| `sensor.mtg_last_game_at` | Timestamp der letzten Runde | – |
| `sensor.mtg_last_game_result` | `win`/`loss`/`draw` | Deck-Name |
| `sensor.mtg_deck_<slug>_winrate` | Siegquote je **aktivem** Deck (Spiel in den letzten 90 Tagen) | `games`, W/L/D, `last_played` |

Per-Deck-Sensoren folgen dem Wishlist-Muster inklusive Discovery-Cleanup, damit
inaktiv gewordene Decks wieder aus HA verschwinden.

### Randbedingungen

- HA-States sind auf **255 Zeichen** begrenzt → Listen gehören immer in die
  Attribute und werden dort auf ~10 Einträge gekappt (Attribut-Payload < 16 KB).
- `unique_id`s bestehender Entities dürfen sich **nie** ändern, sonst verwaisen sie
  in der HA-Entity-Registry.

---

## Runden eintragen: zwei Ebenen

**Ebene A — MQTT-Service `log_game`** (Sprint 30), passt in die bestehende
Service-Registry unter `mtg-collection/service/`:

```json
{"deck": "Atraxa", "result": "win", "pod_size": 4, "on_play": true,
 "mulligans": 1, "missed_land_drops": 0, "turns": 9,
 "opponents": "Krenko, Edgar", "notes": "..."}
```

Deck-Auflösung per ID **oder** Name (case-insensitive; bei Mehrdeutigkeit
Kandidatenliste in der `/response`). Damit funktionieren Scripts, Automationen
und Sprachbefehle sofort.

**Ebene B — Formular als Add-on-eigene MQTT-Entities** (Sprint 31). Gerät
„MTG Game Logger":

`select.mtg_log_deck` (Optionen automatisch aus der DB, nach jedem Archidekt-Sync
neu publiziert) · `select.mtg_log_result` · `number.mtg_log_pod_size` /
`_mulligans` / `_turns` / `_missed_land_drops` · `switch.mtg_log_on_play` ·
`text.mtg_log_opponents` / `_notes` · `button.mtg_log_submit`

Beim Button-Druck liest das Add-on den selbst gehaltenen Formular-State, schreibt
die Runde, setzt die Felder zurück und aktualisiert die Performance-Sensoren. Das
Dashboard bleibt dadurch eine simple Entities-Karte **ohne Jinja**, und die
Deck-Liste pflegt sich selbst.

`what_worked` / `what_didnt` bleiben dem Web-UI vorbehalten (zu viel Tipperei am
Dashboard), sind aber im `log_game`-Payload enthalten.

---

## Sprint 28 — MQTT-Fundament (0.28.0)

Reiner Refactor, nach außen keine neuen Features — aber Voraussetzung für alles
Weitere und Fix zweier bestehender Schwächen.

- **Persistente MQTT-Verbindung** statt Connect-pro-Publish (`services/ha_mqtt.py`):
  ein langlebiger Client mit Reconnect-Loop, den Publisher und Service-Subscriber
  gemeinsam nutzen. Fallback auf eine Einmal-Verbindung, wenn der Manager (noch)
  nicht läuft, damit Aufrufe aus Routern in jedem Kontext funktionieren.
- **Availability-Topic + LWT** (`{prefix}/status` mit `online`/`offline`, retained):
  Entities werden in HA „unavailable", wenn das Add-on aus ist, statt veraltete
  Werte zu zeigen. Voraussetzung für die Command-Entities aus Sprint 31.
- **Entity-Abstraktion** (`services/ha_entities.py`): gemeinsame Discovery-Payload-
  Erzeugung für `sensor`, `binary_sensor`, `select`, `number`, `switch`, `text`,
  `button`.
- **`state_class` nachrüsten**: Die Zähl-Sensoren hatten keins, HA legte also keine
  Langzeitstatistik an (kein Verlaufsgraph). Zusätzlich Korrektur der
  Monetary-Sensoren: `device_class: monetary` verträgt nur `state_class: total`,
  bisher stand dort `measurement` (HA loggt das als „impossible state class").
- **Regressionsschutz**: Snapshot-Tests auf die Discovery-Payloads, die
  insbesondere die `unique_id`s festnageln.

**Risiko**: Der Refactor fasst alle bestehenden Entities an. Deshalb bewusst ohne
neue Sensoren in derselben Version.

## Sprint 29 — Inbox- & Verkaufs-Sensoren (0.29.0)

- Alle Inbox- und Sell-Entities aus der Tabelle oben.
- Publish-Trigger: nach Archidekt-Sync, nach Triage-Entscheidung, nach Preis-Sync.
- Top-N-Listen als Attribute, konsequent gekappt.
- Doku: Beispiel-Automationen (Push bei neuer Inbox-Karte, wöchentlicher
  Verkaufs-Report).

## Sprint 30 — Runden eintragen, Ebene A (0.30.0)

- MQTT-Services `log_game`, `triage` (`{"event_id": 12, "action": "keep"}`) und
  `create_listing`. `triage` macht die Inbox-Push-Notifications aus Sprint 29 erst
  wirklich nützlich (actionable notification mit „Behalten"/„Verkaufen").
- Deck-Performance-Sensoren inklusive Per-Deck-Sensoren mit Cleanup.
- `voice/sentences.yaml` erweitern: „Trag einen Sieg mit Atraxa ein."

## Sprint 31 — Game-Logger-Formular, Ebene B (0.31.0)

- Discovery + Command-Topics für die Formular-Entities.
- Formular-State in einer kleinen Tabelle persistiert, damit ein Add-on-Neustart
  die Eingabe nicht verliert.
- Deck-`select` an den Sync gekoppelt (Optionsliste bleibt aktuell).
- Submit-Flow: `deck_games`-Insert, Feld-Reset, Bestätigung, Sensor-Update.
- Edge Cases: Notizen > 255 Zeichen, während der Auswahl gelöschtes Deck,
  sehr viele Decks in der Options-Liste.

## Sprint 32 — Dashboard (in der HA-Config, nicht hier)

Das Dashboard und die Automationen gehören in die Home-Assistant-Konfiguration,
nicht ins Add-on-Repo: dort sind die Kartenbibliothek, das Theme, die
Package-Struktur und die Namenskonventionen bekannt. Übergabe an den Agenten in
der HA-Config: **[ha-dashboard-handoff.md](ha-dashboard-handoff.md)** — enthält
die vollständige Entity-Inventur, die Attribut-Shapes, die MQTT-Services, die
Aktualisierungs-Kadenz und die Fallstricke.

Add-on-Seite erledigt (v0.32.0):

- `sensor.mtg_ingress_url` publiziert die eigene Ingress-URL samt fertiger Links
  je UI-Route als Attribute — Deep-Links im Dashboard brauchen keinen manuell
  eingetragenen Slug mehr und überleben eine Neuinstallation des Add-ons.
