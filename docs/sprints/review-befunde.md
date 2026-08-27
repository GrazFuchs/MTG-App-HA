# Begutachtung MTG Collection Manager — Befunde (2026-08-23)

Kritische Begutachtung der App (v0.34.1) und ihrer HA-Integration. **Alle B- und W-Befunde sind
selbst verifiziert** — gegen die Live-API auf dem Pi 5, gegen `/api/states` von HA oder am
Quellcode mit file:line. Der Abschnitt „Ungeprüfte Audit-Hinweise" ist klar getrennt.

Vergleichsmaßstäbe der Recherche: ManaBox, edhpowerlevel.com, WotC-Bracket-System, Scryfall /
MTGJSON / Commander Spellbook / EDHREC (Abschnitt R).

---

## Gesamturteil

**Stärken, die man erst würdigt, wenn man den Markt daneben legt:**

- **Die Changelog-Kultur ist Lehrbuchniveau.** Die 0.34.1-Analyse (Stacking-Context durch
  `backdrop-filter`) und die 0.34.0-Farbanalyse (`LIKE '%G%'` matcht „Green" doppelt) sind
  präzise Post-Mortems, nicht Release-Notes.
- **Die MQTT-Plumbing-Schicht ist ungewöhnlich sauber:** Birth/Will-Availability, retained
  Discovery, `object_id`-Pinning, Discovery-Clearing für abgelaufene Entities, 5-s-Debounce,
  per-Bundle-Fehlerisolierung.
- **Das Datenmodell trägt:** 19 Tabellen, `decision_snapshot` als Entscheidungsarchiv,
  Printing-exakte Cardmarket-Preise seit 0.33.0 (`cards.cardmarket_id` als Join-Key — genau das,
  was Scryfall empfiehlt).
- **Preishistorie + Alerts existieren** (`cardmarket_price_history`, `value_snapshots`,
  Spike-Erkennung) — ManaBox speichert bewusst *keine* Zeitreihe. Hier ist das Add-on dem
  kommerziellen Marktführer voraus.
- **42 MCP-Tools, 3 Resources, 2 Prompts** — eine AI-Anschlussfläche, die kaum ein Hobby-Projekt hat.

**Schwächen — als Systemklassen, nicht Einzelfälle:**

1. **Fabrizierte oder fehlende Wahrheit in der UI** (W2/W3: Browser-Uhr als „LAST SYNC",
   String-Literal als Delta; W12: kein `isError` auf den Dashboard-Queries).
2. **i18n strukturell gemischt** (B22: ~27 % Abdeckung, ~222 hartcodierte Literale, 76 tote Keys).
3. **Overlay-/Stacking-Klasse im Design-System** (B3b: `backdrop-filter` im `Panel` — die Ursache
   der wiederkehrenden „Dialog liegt unter der nächsten Karte"-Bugs).
4. **Tote Features:** Bracket (B1/B26), EDHREC-Anbindung (fertig, unerreichbar), Voice
   (end-to-end tot), `POST /undo` (kein Aufrufer), MCP-Wizard (W8).
5. **Null Render-Tests** (B18) — der kausale Grund für die Serie der Darstellungsbugs.

---

## B — Live-Befunde (gemessen am 2026-08-23)

### B1 — `bracket` ist auf allen 22 Decks `0`
`GET /api/decks/` → `Counter({0: 22})`; `user_bracket` ebenfalls `null`. Die gesamte Bracket-UI
(„All Brackets"-Filter, `BR.n`-Tag, Badge) ist totes Gewicht. Ursache: **B26**.
**Entscheidung Auftraggeber:** Brackets bleiben (WotC-System) und werden pflegbar → Sprint 04.

### B2 — `sensor.mtg_last_sync_at` = `unknown`, obwohl die Daten da sind ✅ behoben in 0.35.0
`/api/sync/status` liefert `finished_at: 2026-08-23T01:15:13`, `status: completed`,
`items_synced: 9188`. Root-Cause siehe **W4**.

### B3 — `type_line` in Archidekt-Form (Kommas), nicht Scryfall-Form
`Legendary, Creature — Pirate, Shark`. Der Typfilter funktioniert damit (geprüft) — aber jeder
künftige Code, der Scryfall-Form annimmt (Power-Level!), muss normalisieren → Sprint 02.

### B3b — `backdrop-filter` im Sothera-`Panel` ist ein systemisches Overlay-Risiko
`Panel` (sothera/Panel.tsx) macht via `backdrop-filter: blur(14px)` jedes Panel zugleich zum
Containing Block für `position: fixed` und zum Stacking Context. v0.34.1 hat **einen** Fall
portalt (`TriageDecisionDialog`); `CardHoverPreview` portalt ebenfalls — `PriceTrendHover`
(fixed + z-index 10000, kein Portal) trägt denselben Defekt weiter, und jedes künftige Overlay in
einem Panel erbt ihn. → zentrale Portal-Utility, Sprint 09.

### B4 — Datentiefe für Offline-Scoring: ausreichend, mit zwei Löchern
Deck 1 (98 Karten): `type_line` 98/98 · `oracle_text` 95/98 · `edhrec_rank` 94/98 ·
`price_eur` 97/98 · `cmc` 65/98 (Länder!) · `keywords` 45/98 (unzuverlässig) ·
**`legalities` 0/98** (Archidekt liefert hartcodiert `"{}"`) · **`cardmarket_id` 0/98 (`None`)**.
→ Scryfall-Backfill, Sprint 02 (bestätigt inkl. `legalities` + `cardmarket_id`).

### B5 — Der Triage-Trichter ist die eigentliche Arbeitslast
137 offen, **964 Entscheidungen/30 Tage** (`dismiss` 411 · `keep` 398 · `sold_new` 155) —
~32/Tag von Hand, 43 % davon „interessiert mich nicht". Und **alle** 137 offenen haben
`age_days = 0`. → Sprint 08 (erst Ursache prüfen, dann Bulk-UI + Undo).

### B6 — Game-Logger: gebaut, 1 erfasste Partie
11 MQTT-Form-Entities, `deck_games` (14 Spalten), Dashboard-Sektion, `script.mtg_log_game` ohne
Aufrufer. **Entscheidung Auftraggeber: bleibt unangetastet** (wenig gespielt ≠ Defekt).

### B7 — Die AI-Schicht existiert als Einzelfall
Deck 1 „Sharknado" hat ein starkes `ai_assessment` (3029 Zeichen) — **Stand 2026-06-03**,
1 von 22 Decks, kein UI-Trigger. Einziger Schreiber: MCP-Tool `set_deck_ai_assessment` (W11).
→ Sprint 11.

### B8 — Wishlist-Priorität ist de facto tot; Zielpreis-Lücken
`by_priority: {3: 72, 1: 1, 5: 1}` (97 % Default). Zielpreissumme 461 € gegen Marktwert 831 € —
nur 4 Einträge unter Ziel. Und mehrere teure Einträge haben `target_price_eur = 0`, wo `is_deal`
nie feuern kann (siehe B27). **Auftraggeber-Schwerpunkt: „unter Wunschpreis gefallen" erkennen**
→ Sprint 06.

### B9 — Drei Entity-ID-Präfixe live
`sensor.mtg_*` (42 begradigte) · `sensor.mtg_collection_manager_mtg_wishlist_*` (74) ·
`sensor.mtg_collection_mtg_deck_*_win_rate` (1). Registry gewinnt über Discovery-`object_id`.
→ Sprint 07.

### B10 — CLAUDE.md (ha-infrastructure) ist an drei Stellen veraltet
`notify_min_alert_value_eur` steht live auf **5.0** (nicht 999999 — der offene Punkt ist
erledigt); Version ist 0.34.1→0.35.0; `active_price_alerts` = **712** und `sell_potential_eur` =
**1817 €** sind wieder gestiegen (CLAUDE.md: „behoben — 258 / 965 €") — klären, ob sachlich
(mehr Listings/Preisbewegung) oder Rückfall → Sprint 07.

### B11 — 22 „Decks" sind nicht 22 spielbare Decks
10 Maxi · 4 Carina · 4 Work in Progress · 3 Disassembled · 1 Older Versions; Deck 14 hat 8
Karten, Deck 10 ist eine Altfassung. Alle Format Commander (Power-Level zu 100 % anwendbar).

### B12 — Cardmarket halb konfiguriert, MTGStocks aus
`cardmarket_configured: false`, aber 1223 Listings (798 Unikate, 503 €) importiert.
`mtgstocks_enabled: false` → 2 Sensoren + Dashboard-Bereich existieren nicht (korrekt gecleart).

### B13/B17 — Sicherheit: unauthentifiziert, aber nicht LAN-exponiert
Vom Container gemessen: `POST /mcp` initialize → **200 ohne Token** (Token leer, Guard
`mcp_server.py:2086-2091` übersprungen); `GET /api/backup/backup` → 200, **326 MB** DB ohne Auth.
**Fair eingeordnet:** Port 8099 ist **nicht** ins LAN publiziert (kein `ports:` in config.yaml,
TCP-Probe verweigert) — erreichbar nur aus dem Supervisor-Docker-Netz und über Ingress
(HA-Auth). Härtungsthema, kein Leck. → Token gesetzt in Sprint 01.

### B14 — KORRIGIERT: `state_class: total` auf Bestandswerten ist richtig so
Ursprünglicher Befund („sollte `measurement` sein") war **falsch**: HA erlaubt bei
`device_class: monetary` **nur** `total` — der Code-Kommentar in `ha_publisher.py:17-19`
dokumentiert das bereits. Die Zwei-Graphen-Lösung im Dashboard ist damit die korrekte Antwort
auf eine HA-Einschränkung, kein Workaround-Schuldschein. **Kein Handlungsbedarf.**

### B15 — Attribut-Last ist kein Problem (Gegenbefund)
128 MTG-Entities: 40,8 KiB Attribute gesamt, Maximum 2,2 KiB (`inbox_pending`). Weit unter der
16-KiB-Grenze. Die `items`-Kappung auf 10 könnte auf 25–30 steigen, ohne HA zu belasten.

### B16 — Wishlist-Sensoren: namensbasierte IDs, kein `state_class`
IDs wie `…mtg_wishlist_confusion_in_the_ranks_mrd` (Registry-Altbestand, Discovery sagt
`mtg_wishlist_{id}`); 0/74 mit `state_class` → HA führt keinen Preisverlauf je Karte, obwohl das
Add-on ihn intern hat. → Sprint 06/07.

### B18 — Null Render-Tests im Frontend
`vite.config.ts`: `test.environment: 'node'`. `Inbox.test.tsx` rendert **keine** Komponente
(eigener Kommentar: api.ts fasst `window` beim Modul-Load an). Erklärt die Bug-Serie
(0.34.1 Dialog begraben, 0.22.0 hover overlap, 0.17.3 row multiplication). → Sprint 09.

### B19 — Ein 1,15-MB-JS-Chunk, 3,3 KB CSS
Kein Code-Splitting; Griffel injiziert Styles zur Laufzeit → FOUC im iframe, JS-Fehler = weiße
Seite. → Sprint 09/10 (React.lazy je Route).

### B20 — Google Fonts vom CDN in einer Local-First-Appliance
`index.html` lädt 3 Fonts von fonts.googleapis.com — Offline-Degradation, Privacy-Inkonsistenz
zum AdGuard-Setup, blockbar durch Filterlisten. → bundlen, Sprint 10.

### B21 — `<html lang="en">` hart verdrahtet ✅ behoben in 0.35.0 (Runtime-Sync auf UI-Sprache)

### B22 — i18n deckt ~27 % der UI ab
158 en-Keys / 159 de-Keys definiert, nur **83** per `t()` benutzt (76 tote Strings), daneben
**~222 hartcodierte Literale in 34 Dateien** (Duplicates 35, DeckPerformance 23, Collection 19,
Settings 15 …). In deutschen Browsern strukturell gemischtsprachig. `common.loading` fehlte in
`en` ✅ behoben in 0.35.0. Rest → Sprint 10.

### B23 — Scryfall liefert `game_changer` nativ
Verifiziert: Rhystic Study/Demonic Tutor/Thassa's Oracle `game_changer: true`, Sol Ring `false`;
`is:gamechanger` → **exakt 53 Karten** (Stand 2026-02-09: +Farewell, +Biorhythm). Dazu
`legalities`, `reserved`, `keywords`. **Nicht abschreiben — abfragen.** → Sprint 02/04.

### B24 — Combo-Daten: der Bracket-Input ist da, aber verschüttet
Über alle 19 Decks gemessen: **484 Combos gecacht, nur 15 vollständig im Deck**
(`is_partial: false`), davon 4 zweikartig; **`missing_cards` ist auf allen 469 Teil-Combos
leer**; **14 von 19 Decks haben `[]`** — Combos haben nur Decks, die ab 2026-06-04 synchronisiert
wurden (inkrementeller Sync überspringt Unveränderte; Hypothese, am Code zu verifizieren).
Deck 5 hat 3 echte 2-Karten-Infinites (Kiki-Jiki + Deceiver Exarch) — und zeigt Bracket 0.
UX-Folge: Deck 1 zeigt 27 Combos, von denen **keine** im Deck vollständig ist. → Sprint 03.

### B25 — `completeness` zählte Basisländer als fehlende Karten ✅ behoben in 0.35.0
`Forest ×3` stand in `missing_cards` und `most_expensive_missing`; der vorhandene
Basisland-Ausschluss aus `queries.py` wird jetzt angewendet.

### B26 — Der Bracket-Import las einen Schlüssel, den es nicht gibt ✅ Schlüssel behoben in 0.35.0
`archidekt.py` las `bracket`/`deckBracket`; die echte API liefert **`edhBracket`** (verifiziert
gegen zwei Live-Decks) — und der ist dort ebenfalls `null`. Doppelte Sackgasse: falscher
Schlüssel **und** leere Quelle. Konsequenz: die einzige tragfähige Bracket-Anzeige ist eine
lokal gerechnete bzw. gepflegte → Sprint 04.

### B27 — 24 % der Wunschliste sind offizielle Game Changers (437 €)
12 von 50 aktiven Einträgen (Chrome Mox 87 €, Force of Will 54 €, Vampiric Tutor 43 €, Fierce
Guardianship 42 €, Rhystic Study 36 €, …). Alle auf Priorität 3 (Default), keine bestellt,
**vier mit `target_price_eur = 0`** — für die kann `is_deal` nie feuern. Das stärkste Argument
für die Bracket-Funktion: ein Viertel der Kaufabsichten ist bracketentscheidend, und diese
Entscheidungen fallen heute blind. → Sprint 04/06.

### B28 — `/estimate-bracket` (Commander Spellbook) validiert exakt gegen die eigenen Daten
POST ohne Auth; Combo-Zahlen decken sich **exakt** mit dem `is_partial: false`-Bestand
(Deck 5: 3/3 · Deck 2: 12/12 · Deck 13: 0/0 · Deck 1: 0/0); erkennt zusätzlich
`massLandDenial` (Death Cloud in Deck 2), `extraTurn`, `banned`, `gameChanger`.
⚠️ `bracketTag` liefert Kurzcodes (`E`, `R`) — Mapping vor Verwendung über `/schema/` klären.
⚠️ Bewertet nur Karten aus der Spellbook-DB (34/87 bei Deck 5) — Game Changers deshalb aus
Scryfall nehmen, nicht von hier. → Sprint 04.

### B29 — HA-Dashboard: 28 Controls, davon tun 5 etwas
Live-Inventar (dashboard = home_desktop, byteidentisch; mobile 23 Controls): 1× Sync + 4×
Triage-Knöpfe (nur oberste Karte!), 10 Formularfelder (1 Partie je erfasst), 13 more-info-Popups,
5 Markdown-Deep-Links. `docs/dashboard-strategie.md` (ha-infrastructure) schlägt bereits vor,
auf eine Sektion + Deep-Link einzudampfen — gut und nicht umgesetzt.

### B30 — Haupt-Dashboard außerhalb der Generator-Reichweite
`tools/patch-mtg-gameroom.py` kennt nur `home_desktop`/`home_mobile`; das De-facto-Hauptdashboard
`dashboard` trägt eine byteidentische, ungewartete Kopie. → Sprint 07.

### B31 — Eine 5 Wochen alte Warnkarte diskreditiert einen wieder gültigen Wert
„`sell_potential` ist nicht belastbar … Stand 2026-07-22" steht live in 2 Dashboards, obwohl der
Bug seit 0.33.0 behoben ist (heute 1817 € bei 7126 € Sammlungswert — plausibel).
`mtg_verkauf_wochenreport` hängt weiter am Ausweich-Trigger. Erst Gegenprobe der drei Zahlen
(1817 / 937 / 1073 €), dann Karte ersetzen. **Gegenbeispiel richtig gemacht:** die
`last_sync_at`-Warnkarte war korrekt und aktuell — nach 0.35.0 entfernen. → Sprint 07.

---

## W — Am Quellcode nachgeprüfte Audit-Befunde

| # | Befund | Beleg | Status |
|---|---|---|---|
| W1 | Weiße Seite bei Reload verschachtelter Routen: `base: './'` + SPA-Fallback → Assets werden relativ zur Route aufgelöst | `vite.config.ts:6`, `dist/index.html` | Sprint 09 |
| W2 | „LAST SYNC" = Browser-Uhr, „SYNCED" = Konstante | `Dashboard.tsx:258-265` | ✅ 0.35.0 |
| W3 | „+7.70 % vs. 90d" = String-Literal | `Dashboard.tsx:291` | ✅ 0.35.0 |
| W4 | Root-Cause B2: naiver SQLite-Timestamp an `device_class: timestamp` | `ha_publisher.py:338` | ✅ 0.35.0 |
| W5 | Duplicates-`extras` = `total_copies` statt des eine Zeile darüber berechneten `extras_global`; deck-gebundene Kopien zählen als Überschuss; `listed_quantity` matcht nur auf Namen | `queries.py:383-390` | Sprint 09 |
| W6 | Status → „Gesucht" rief `restore` (400 außer bei Soft-Delete); `not_received` war Endstation | `WishlistEditDialog.tsx:64-71`, `wishlist.py:779-790` | ✅ 0.35.0 |
| W7 | „Deals only" sendete `deals_only`, Backend liest `is_deal_only` — No-op; dahinter: Deal-Filter lief **nach** LIMIT | `WishlistFilterBar.tsx:54`, `wishlist.py:297` | ✅ 0.35.0 |
| W8 | MCP-Wizard: `/mcp/sse` existiert nicht; emittierte `MTG_*`-Env-Vars, die der Proxy nie liest (er nimmt Positionsargumente) | `mcp_setup.py:35`, `mcp-proxy.mjs:17-24` | ✅ 0.35.0 |
| W9 | HA-„Tauschen"-Knopf = garantierter stiller No-op (`swap` verlangt `listing_price_eur` → 422 auf ungelesenem Response-Topic) | `acquisitions.py:320-321`, `scripts.yaml` | Sprint 07 |
| W10 | State-vor-Attribut-Publikationsreihenfolge → actionable Push kann veraltete `event_id` tragen (ms-Fenster) | `ha_publisher.py:250-257` | Sprint 07 |
| W11 | **Kein LLM im Add-on** (11 Pakete, kein SDK); „AI" = Heuristik + eine per MCP beschriebene Spalte → Ausbau ist eine Client-Frage | `requirements.txt`, `mcp_server.py:1471` | Sprint 11 |
| W12 | `t` importiert, nie benutzt, dann verschattet; kein `isError` auf 7 Queries → totes `/api/stats` renderte €0.00 unter grünem „SYNCED" | `Dashboard.tsx:8,240` | ✅ teilw. 0.35.0 (Banner + Hero); Rest Sprint 09 |

---

## Ungeprüfte Audit-Hinweise (aus dem 8-Bereichs-Audit; vor Verwendung verifizieren)

Der Audit-Workflow inventarisierte **440 Controls** und meldete **361 Befunde**; die
adversariale Stichprobe widerlegte 8 von 12 geprüften → die Liste unten ist **Hinweis, nicht
Befund**. Die wichtigsten, nach Sprint:

- **Sync/Inbox (Sprint 08):** abgebrochener Sync hinterlässt halb-aggregierte Mengen → Folgesync
  bucht Phantom-Events (`sync_service.py:322`) — plausible Erklärung für 43 % dismiss und
  age_days=0; `run_full_resync` committet das Löschen der Collection vor dem ersten Netzaufruf;
  Event-Erzeugung hängt an einem sync_log-Status, den ein einzelner Fehler dauerhaft unterdrückt;
  kein `catch` auf dem Entscheidungspfad; `POST /undo` ohne Aufrufer; Liste springt nach
  Entscheidung.
- **Cardmarket (Backlog/Sprint 09):** Neu-Format-CSV schreibt `set_code=''` → „LISTED"-Spalte
  dauerhaft 0, 🛒-Badge nie sichtbar; Foil geht im Roundtrip verloren; `clear-listings` löscht vor
  Parse-Erfolg; Listing-Health vergleicht Foil-Listings gegen Non-Foil-Trend.
- **Settings:** Restore-from-Backup ohne Bestätigung, meldet Erfolg, serviert aber die alte DB
  weiter (kein Reconnect); jedes Backup hinterlässt eine Vollkopie in `/data`; Sync-History
  zeigt Erfolge rot / Zeiten um UTC-Offset falsch.
- **Voice (Sprint 11):** 7 Intents definiert, 0 auf HA installiert; Doku-REST-Snippet zeigt auf
  `localhost:8099` (von HA Core unerreichbar) — HA-Seite von uns bestätigt tot.
- **Decks:** Completeness matcht Ownership printing-exakt (fremdes Set zählt als fehlend) und
  zählt Sideboard/Maybeboard mit; zwei verschiedene Kartenzahlen zwischen Liste und Detail;
  „Compare Decks"-Einstieg nur sichtbar, wenn ein Archidekt-Bracket existiert (= nie, B1);
  EDHREC-Endpunkte + Client fertig, von keinem Button erreichbar.
- **A11y/Responsive (Sprint 10):** Navigation + Tabellen als `<div onClick>` ohne Tastaturpfad;
  Hover-Preview auf Touch unerreichbar; Collection 601–768 px kaputt; Duplicates ohne
  Mobil-Layout; PageHeader kollidiert bei 320–375 px.
- **MCP (Sprint 11):** `decide_triage` via MCP schreibt kein `decision_snapshot` und triggert
  kein HA-Publish; Triage-Vorschlag via MCP ohne Sibling-Awareness (weicht von der UI ab);
  `clear_cardmarket_listings` als ungeschützter Mass-Delete-Tool-Call.

---

## R — Recherche (Vergleichsmaßstäbe)

### R1 — Korrektur zur Aufgabenstellung: mythic.tools
Ist eine **Companion-App** (Lebenspunktzähler, Playgroups, Bo3-Match-Tracker, Scanner via
Scryfall, OBS-Overlay) — **keine** Bracket-Berechnung, keine Salt-Scores, keine Combo-Erkennung.
Die Tools dieser Klasse heißen: **edhcheck.com** (am nächsten), playgroup.gg, brackcheck.com,
scrollvault.net, ratemydecks.com, commanderbrackets.com (alle nur Snippet-Ebene, unverifiziert).

### R2 — edhpowerlevel.com: Algorithmus vollständig extrahiert
Rechnet rein clientseitig; komplette Konfiguration im Bundle `js/main-C1lbqCDd.js`:

```javascript
factors: { land: 0.6, reserved: 0.2, favorPrice: 0.25,
  powerCurve:  [0,250,320,350,380,420,470,560,760,890,1000],
  popCurve:    [0,8500,13600,17100,19800,21900,23700,25300,26200,26700,27000],
  priceCurve:  [0,0.5,1.5,3.5,6,10,15,25,40,65,100],
  bracketCurve:[0,4.7,6.7,7.7,9.25,10],
  cmcFloor: 1.75, cmcCeiling: 6, efficiencyLimits: [0.65,1.1] }
```

Kette: `Impact = (de(price,priceCurve,1.25) + de(27000−edhrec_rank,popCurve,0.75)) × qty` →
`Score = ΣImpact × (0.65 + 0.45·Ce)` → `PowerLevel = de(Score, powerCurve)`. Dazu ~90
Karten-Overrides (Sol Ring Preis ×8, Sisay commanderImpact ×4, 25 Free Spells → cmc 0), 33
MLD-Karten, 12 chainable Extra Turns. Braucht je Karte nur: `price` (USD), `edhrec_rank`, `cmc`,
`type_line`/`layout`, `reserved` — **alles von Scryfall**.

**Sieben Nachbau-Fallen:** (1) `de()`s Bruchteil ist UNgewichtet; (2) `Ce` nicht klemmen;
(3) MDFC = Land, CMC nicht in avgCost; (4) Basics NACH dem Land-Faktor auf `2×qty`;
(5) `commanderImpact` nur bei echtem Commander; (6) `tutors`-Kategorie ist **absichtlich tot**
(WotC strich Tutoren-Limits 10/2025); (7) `PowerLevel == 0` → Bracket-Default **5**.
`popCurve`-Deckel 27.000 stammt aus 9/2024 — als Erstes aktualisieren, verschiebt alle Werte.

### R3 — Power Level und Bracket sind zwei unabhängige Ausgaben
Auch bei edhpowerlevel: Combos/Tutoren/Extra Turns/MLD/Game Changers gehen **nur** in den
Bracket, nie in den Score. Der Autor empfiehlt für Vergleiche den **Score** statt des Power
Levels und nennt den Score selbst manipulierbar. → zwei Felder am Deck, nicht eins.

### R4 — Commander Spellbook: `/estimate-bracket`, `/find-my-combos`, `/card-list-from-url`
Frei, kein Key, Lesen ohne Auth. `bracketTag`, `manaValueNeeded`, `uses[].zoneLocations`,
`produces[].feature.id` — verifizierte Feldnamen. `/card-list-from-url` parst
Moxfield/Archidekt/Deckstats/TappedOut (legaler Moxfield-Weg).

### R5 — WotC-Brackets (offiziell)
1 Exhibition · 2 Core · 3 Upgraded (≤3 Game Changers, keine early 2-Karten-Combos) ·
4 Optimized · 5 cEDH. Game-Changers-Liste = **exakt 53** (Scryfall `is:gamechanger`,
Stand 2026-02-09). Tutoren-Beschränkungen seit 21.10.2025 gestrichen. MLD = trifft ≥4 Länder
je Spieler.

### R6 — EDHREC: `json.edhrec.com` (auf Duldung)
`pages/top/salt.json` (Salt 0–4, 321 Seiten paginierbar; ⚠️ ohne `/top/` → 403);
`pages/commanders/<slug>.json` (synergy, num_decks, bracket_counts, combocounts). Keine Doku,
keine Lizenz → hart cachen, weich degradieren. `clients/edhrec.py` existiert bereits.

### R7 — ManaBox: was zu lernen ist
Scanner = **Artwork-Erkennung, kein OCR** (3 Features kaschieren nur die Reprint-Mehrdeutigkeit);
Kernidee = **physischer Aufbewahrungsort** (Binder vs. List vs. Deck) — fehlt diesem Add-on
komplett; **keine Preishistorie** (nur Delta gegen Kaufpreis) — hier ist das Add-on überlegen;
fehlende Deckkarten als **Vier-Zustands-Modell** (partially/completely missing, exact/other
versions) — Vorlage für completeness; „Teilstapel verschieben"-Geste; Preisband-Audiofeedback
beim Scannen. Kursierende Gratis-Limits („5 Decks/Binder") stammen von einem Konkurrenten —
nicht zitierfähig.

### R8 — Datenquellen-Empfehlung
**Scryfall** (Identität, Oracle, Bilder, Legalitäten, Game Changers; Pflicht-Header User-Agent +
Accept; 10/s bzw. 2/s; Preise 1 Snapshot/Tag, „dangerously stale after 24 hours") +
**MTGJSON** (90 Tage Preishistorie inkl. Buylist, 26 Marktplatz-IDs, MIT-Lizenz) +
**Commander Spellbook**. Cardmarket-API nimmt keine Anträge an; TCGPlayer faktisch zu; beides
über MTGJSON ersetzbar. ⚠️ `scryfall.com/docs/*` → 403 direkt, über `r.jina.ai/<url>` erreichbar.
