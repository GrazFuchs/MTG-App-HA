# Plan — Standard- und andere 60-Karten-Decks im MTG Collection Manager

**Status: ✅ vollständig umgesetzt.** Plan vom 2026-09-12, Entscheidungen getroffen am 2026-09-14,
Sprints 12–15 umgesetzt bis 2026-09-15 (0.47.0 · 0.48.0 · 0.49.0 · 0.50.0, dazu der Nachtrag 0.49.1
zur letzten offenen Entscheidung). Die Ist-Protokolle stehen in den vier Sprint-Dateien; diese Datei
bleibt die Analyse und der Schnitt. Vier
Sprints (12–15), einzeln deploybar,
Bauform wie die Reihe 01–11 (**Ziel · Warum · Arbeitspakete · Akzeptanz · Verifikation**). Jeder
Sprint bekommt beim Start seine eigene `sprint-NN-*.md` mit Ist-Protokoll; diese Datei bleibt die
Analyse und der Schnitt.

**Auftrag (Max, 2026-09-12):** „Ich möchte nun auch Standard oder 60 Karten Decks im MTG
Collection Manager verwalten."

## Ausgangslage — live gemessen 2026-09-12

| Messung | Wert | Woher |
|---|---|---|
| Decks in der DB | **22, alle `format = "Commander"`** (Ordner: Maxi · Carina · Work in Progress · Older Versions · Disassembled) | `GET /api/decks/` am Container |
| Karten mit Scryfall-Legalitäten | **7.858 von 7.858**, `pending 0`, Refresh alle 7 Tage | `GET /api/cards/enrichment` |
| Deck-Auswahl im Sync | **Auto-Discovery aller Decks des Archidekt-Users, kein Format-Filter** | `sync_service._do_full_sync` |
| Formatname | Archidekt `deckFormat` → 24 Namen (`1 = Standard`, `3 = Commander`, …), gespeichert in `decks.format` | `archidekt._format_name` |
| Arbeitsbaum | **0.46.2 ist ungecommittet** (Hotfix React #310 + `rules-of-hooks.test.ts`) | `git status` |

**Die wichtigste Erkenntnis vorweg: ein Standard-Deck auf Archidekt würde heute schon
synchronisiert — und danach falsch beschrieben.** Kein Codepfad lehnt es ab. Was passiert:

- `compute_brackets_for_all_decks()` rechnet ihm **Bracket 2** („keine Regel ausgelöst") aus und
  schreibt es in `computed_bracket` → Badge „BR.2" auf der Kachel, `bracket: 2` im HA-Deck-Sensor.
  Eine Commander-Einstufung an einem Standard-Deck.
- `compute_power_for_all_decks()` rechnet den edhpowerlevel-Score — dessen `popCurve` aus den
  Commander-legalen Karten von 2024 stammt und dessen Landfaktor für 99+1 kalibriert ist →
  „PWR 412" ohne Bedeutung.
- Spellbook `estimate-bracket` wird gefragt, `spellbook_bracket_tag` gesetzt.
- Hero-Bild bleibt leer (kein Commander), obwohl `featured_image` da wäre; Kopfzeile
  „DOSSIER · Standard · BRACKET —".
- Der Game-Logger schlägt `pod_size = 4` vor.
- Maybeboard-Karten zählen als Deckbedarf — das tun sie heute schon bei Commander (Befund 10).

Kurz: **kein Feature fehlt hart, aber vier Analysen behaupten Dinge, die für das Format nicht
definiert sind.** Es gilt die Hausregel aus `sensor.astro_score` und `sensor.humphrey_care`:
**nicht anwendbar heißt `NULL` + Grund, nie eine Zahl.**

## Befund — was Commander annimmt (Komponenten-Inventar)

| # | Komponente | Datei(en) | Annahme heute | Folge für ein 60-Karten-Deck | Sprint |
|---|---|---|---|---|---|
| 1 | Deck-Tabelle | `database.py` | `format` vorhanden, `commander_name`/`commander_card_id` leer erlaubt | **keine Migration fürs Format nötig** | — |
| 2 | Deck-Karten | `database.py` | `category` = Freitext von Archidekt, **kein Board-Begriff**; `UNIQUE(deck_id, card_id, modifier)` | dieselbe Karte in Main **und** Sideboard wird zu einer Zeile verschmolzen (Menge addiert, Kategorien gejoint); Maybeboard zählt überall mit | 12 |
| 3 | Archidekt-Parser | `clients/archidekt.py` | Commander = erste Karte mit Kategorie „Commander"; die deck-weiten `categories[]` (mit `includedInDeck`) werden **nicht gelesen** | Sideboard/Maybeboard nur über Kategorienamen im Frontend unterscheidbar | 12 |
| 4 | Sync-Nachlauf | `services/sync_service.py` | Bracket + Power für **alle** Decks, Combo-Sync für alle | Commander-Urteile am Standard-Deck | 12 |
| 5 | Bracket | `services/bracket.py` | WotC-Commander-Brackets, **kein Format-Gate** | falsches „2" | 12 |
| 6 | Power | `services/power_level.py` | edhpowerlevel-Port (`commanderImpact`, Commander-`popCurve`, Landfaktor 99+1) | bedeutungslose Zahl | 12 |
| 7 | Combos | `services/combo_sync.py`, `clients/spellbook.py` | `find-my-combos` funktioniert auf jeder Liste (**bleibt**); `estimate-bracket` ist Commander; „almost included" schlägt Karten ohne Rücksicht auf Legalität vor | Klassifikation sinnlos; Vorschläge Commander-only | 12 (Gate), 14 (Filter) |
| 8 | EDHREC | `clients/edhrec.py`, `routers/cards.py`, `DeckView` | braucht einen Commander; UI-Link nur mit `commander_name` | Link bleibt weg — richtig. Nur der MCP-Prompt fordert den Aufruf | 12 |
| 9 | MCP | `mcp_server.py` | Prompt `analyze_deck` verlangt `explain_bracket` · `compute_power_level` · `get_edhrec_recommendations`; `suggest_bracket_safe_upgrades` läuft Bracket-Regeln + EDHREC; `list_decks`/`get_deck` tragen `format` bereits | Assistent improvisiert auf nicht anwendbaren Tools | 12, 14 |
| 10 | Deckbedarf / Überschuss | `queries.DUPLICATES_CTE`, `sell_advisor.py`, `cardmarket_prices.py` (Spikes), MCP `suggest_bracket_safe_upgrades`, HA-Surplus-Sensoren | `SUM(dc.quantity)` über **alle** Decks inkl. Maybeboard, „Disassembled", „Older Versions" — **vier eigene Kopien** der Abfrage | mit Playsets strukturell: 3 Decks × 4 = **12 „in Decks" bei 4 besessenen** → Überschuss 0, Einkaufsliste „8 fehlen" | 13 |
| 11 | Completeness | `routers/decks.py` | `needed = dc.quantity` (4-of ok), Basics raus; zählt Maybeboard; ignoriert, dass andere Decks Kopien binden | Prozent zu niedrig, `most_expensive_missing` falsch | 13 |
| 12 | Legalität | `cards.legalities` (Scryfall-JSON) | **vollständig befüllt, von niemandem gelesen**; nicht in `CardResponse`; keine Deckregeln (60/15/4) | Rotation/Bans unsichtbar | 14 |
| 13 | Spielprotokoll | `schemas.DeckGameBase`, `DeckPerformanceSection.tsx`, `services/ha_form.py`, HA-`FORMULAR` | `pod_size` Default **4**, Label „Opponents / commanders", Hint „Atraxa, Krenko" | jede 1v1-Partie muss korrigiert werden; MQTT-`log_game` ohne `pod_size` → 4 | 15 |
| 14 | HA-Deck-Sensor | `ha_metrics.deck_stats`, `ha_publisher.publish_deck_sensors` | Attribute `bracket`/`power_*`, **kein `format`** | Commander-Zahlen am Standard-Deck | 12 |
| 15 | Deck-Liste | `pages/Decks.tsx` | Format-Badge da; Filter nur Bracket; Kachelfuß = Commander; `card_count` = alle Boards | „115 CARDS" bei 60+15+Maybeboard | 12 |
| 16 | Deck-Seite | `pages/DeckView.tsx` | Hero aus Commander-Art; Kopfzeile zeigt **`deck.bracket`** (Archidekt-Import, auf allen Decks 0 → immer „—", **Nebenbefund**); `SIDEBOARD_CATEGORIES` namensbasiert; alle Sektionen unbedingt | leerer Hero, Bracket-/Power-Sektion am Standard-Deck | 12, 14 |
| 17 | Tests | `tests/_helpers.insert_deck` (13 Dateien), `test_schema_upgrade.py` (2 direkte INSERTs) | Decks ohne `format` (DEFAULT `''`) | ein Format-Gate ließe alle Bracket-/Power-Tests fallen | 12 |
| 18 | Doku | `README.md` (Commander-zentriert), `docs/ha-integration.md`, `CLAUDE.md`-MTG-Abschnitt | — | — | je Sprint |

## Leitentscheidungen (Architektur)

1. **Eine Formattabelle als einzige Quelle — `services/formats.py`.** Jeder der 24 Archidekt-Namen
   bekommt eine Zeile; ein unbekannter Name bekommt die Zeile „nichts anwendbar", **keine Vermutung**.

   | Format | Familie | Commander | Bracket | Power | Scryfall-Key | Main | Side | Kopien |
   |---|---|---|---|---|---|---|---|---|
   | Commander | commander | ✓ | ✓ | ✓ | `commander` | 100 exakt | 0 | 1 |
   | Duel Commander · 1v1 Commander · Pauper Commander · Predh | commander | ✓ | — | — | `duel` · — · `paupercommander` · `predh` | 100 | 0 | 1 |
   | Brawl · Standard Brawl · Oathbreaker | commander | ✓ | — | — | `brawl` · `standardbrawl` · `oathbreaker` | 60 | 0 | 1 |
   | **Standard** · Pioneer · Modern · Legacy · Vintage · Pauper · Premodern · Explorer · Historic · Alchemy · Timeless · Penny Dreadful · Gladiator | constructed | — | — | — | je eigener Key | **≥ 60** | **≤ 15** | **4** |
   | Frontier · Future Standard · Historic Brawl · Unknown | — | — | — | — | — (kein Check) | — | — | — |

   Gates: `has_commander()` · `bracket_applies()` · `power_applies()` · `scryfall_legality_key()` ·
   `deck_rules()` (main_min/max, side_max, max_copies, singleton, default_pod_size). **Bracket bleibt
   allein bei „Commander"** — das WotC-System ist für casual Multiplayer-Commander geschrieben, nicht
   für Duel Commander mit eigener Banlist. Das Frontend bekommt die Regeln **im Deck-Payload**
   (`format_rules`), nicht als zweite Tabelle in TypeScript — dieselbe Lehre wie die `ziele`-Map in
   `abwesenheit/` und `sommer_monate` in `luften/`: ein Fakt an zwei Stellen driftet.
2. **Nicht anwendbar = `NULL` + Grund.** `compute_bracket`/`compute_power_level` liefern
   `{"bracket": None, "reason": "not_applicable", "format": …}` **und nullen gespeicherte Werte** —
   ein Deck, das auf Archidekt von Commander auf ein anderes Format umgestellt wird, behielte sonst
   sein altes Bracket. UI blendet aus, MCP antwortet `not_applicable`.
3. **`board` statt Kategorienamen.** Neue Spalte `deck_cards.board ∈ main | side | maybe`, beim Sync
   aus Archidekts deck-weiten `categories[]` abgeleitet: `includedInDeck` → main; Kategorie
   „Sideboard" → side; alles andere → maybe. ⚠️ **In Schritt 0 verifizieren:** meine Probe am
   2026-09-12 gegen zwei eigene Decks lieferte anonym `Deck not found.` (privat) — mit dem
   authentifizierten Client des Add-ons `raw["categories"]` loggen. Wahrscheinlich führt Archidekt
   „Sideboard" mit `includedInDeck: false` (sein Deckzähler zählt es nicht mit) — dann braucht es
   die Namensregel; steht es auf `true`, reicht das Flag. `SIDEBOARD_CATEGORIES` im Frontend fällt weg.
4. **Ein Bedarfs-Helper.** `deck_usage_sql()` in `queries.py`, von allen fünf Konsumenten benutzt; ein
   Test prüft, dass jeder den Helper enthält (Bauform `test_duplicates` „die zwei stimmen überein",
   Sprint-11-Lehre „zwei Aufrufstellen driften leise").
5. **Kein Power-Score, kein Bracket-Analogon für 60-Karten-Formate.** Der Port ist dem Original
   treu, und das Original ist Commander-only; eine „Standard-Variante" wäre erfunden. Was 60-Karten-
   Decks stattdessen bekommen, ist der **Deck-Check** (Sprint 14): Größe, Sideboard, Kopienlimit,
   Legalität — **Fakten statt Urteile.**
6. **Die 22 Commander-Decks dürfen sich nicht bewegen.** Gegenprobe in jedem Sprint: die
   Bracket-Verteilung aus Sprint 04 (**7× 2 · 6× 3 · 9× 4**) und die Power-Scores vorher/nachher
   identisch.

---

## Sprint 12 — Format-Wahrheit (Fundament)

**Ziel:** Ein Standard-Deck wird korrekt beschrieben — kein Bracket, kein Power, Boards getrennt,
Format sichtbar — und die 22 Commander-Decks ändern sich nicht.

**Warum:** Befunde 1–9, 14–17. Alles Weitere baut darauf.

### Schritt 0 — Vorbedingungen

- **0.46.2 committen und deployen.** Der Arbeitsbaum ist schmutzig; der Sprint startet auf 0.47.0.
- **Max legt zwei Testdecks auf Archidekt an**: ein **Standard**-Deck und ein Deck aus der übrigen
  60-Karten-Familie, die er absehbar spielt (**Pioneer, Modern, Pauper, Premodern, Legacy** —
  Entscheidung 2026-09-14; eines davon genügt als Zweitprobe, Pauper ist der lehrreichste Fall, weil
  dort die Legalität an der Seltenheit hängt und Scryfall das im `pauper`-Key bereits eingerechnet
  hat). Die Auto-Discovery holt beide beim nächsten Sync. Empfehlung: eigener Ordner „Constructed"
  o. ä. — die heutigen Ordner sind Besitzer bzw. Zustand, das Format kommt aus `deckFormat`, nicht
  aus dem Ordner.
- **Archidekt-Payload verifizieren** (Leitentscheidung 3): `raw["categories"]` eines eigenen
  Commander-Decks und des Standard-Decks loggen, Beleg in die Sprint-Datei.
- **Ist-Messung vor dem Umbau** (DB-Kopie über den Backup-Endpoint, Memory-Rezept): Zeilen in
  `deck_cards` je Kategorie (Maybeboard · Sideboard · Considering · …); Bracket und Power aller 22
  Decks als Referenztabelle; `sensor.mtg_duplicates_surplus_cards` / `_value_eur`; Karten mit
  `in_decks > total_owned` (Vorgriff auf Sprint 13).

### Arbeitspakete

| # | Paket | Datei(en) |
|---|---|---|
| 1 | **`services/formats.py`**: Tabelle + Gates + `deck_rules()`. Test: jeder Name aus `archidekt._format_name` hat eine Zeile (Bauform des Prompt-Tests aus Sprint 11) | neu, `tests/test_formats.py` |
| 2 | **Migration 26**: `deck_cards.board TEXT DEFAULT 'main'`, UNIQUE neu `(deck_id, card_id, modifier, board)` — Tabellen-Neubau wie Migration 8 (`wishlist_new` → rename). Gefahrlos, weil `sync_deck` `deck_cards` ohnehin per DELETE + INSERT neu schreibt. Startwert aus dem Kategorienamen (`Sideboard` → side; `Maybeboard`/`Considering`/`Slot In`/`Slot Out` → maybe), damit bis zum nächsten Sync nichts falsch dasteht | `database.py`, `tests/test_schema_upgrade.py` (**gegen die echte DB-Kopie**, 0.33.0-Lehre) |
| 3 | Parser liest die deck-weiten `categories[]` → `included_in_deck` je Kategoriename; `parse_archidekt_card` bekommt `board`; `sync_deck` schreibt es | `clients/archidekt.py`, `services/sync_service.py` |
| 4 | **Gates**: `compute_bracket` / `compute_power_level` / `classify_deck_cards` prüfen `formats`; bei nicht anwendbar Werte nullen + `reason`. Combo-Sync bleibt für alle Formate (Leitentscheidung, Befund 7) | `services/bracket.py`, `services/power_level.py`, `services/combo_sync.py` |
| 5 | `card_count` = main, neu `sideboard_count`; `DeckSummary`/`DeckDetail` tragen **`format_rules`** und je Karte `board` | `services/queries.py`, `models/schemas.py`, `routers/decks.py` |
| 6 | **Frontend**: `Decks.tsx` Format-Filter neben dem Bracket-Filter, Kachelfuß Commander-Name **oder** „60 + 15"; `DeckView.tsx` Hero fällt auf `featured_image` zurück, Kopfzeile format-bewusst (Commander: **effektiver** Bracket — heute `deck.bracket`, Nebenbefund 16; Standard: „60 + 15 · Standard"), `UserBracketBadge`/`DeckPowerSection` nur bei `bracket_applies`/`power_applies`, `SIDEBOARD_CATEGORIES` → `board`. i18n EN + DE | `pages/Decks.tsx`, `pages/DeckView.tsx`, `api.ts`, `i18n.ts` |
| 7 | **MCP**: Prompt `analyze_deck` verzweigt nach `format` („ohne Bracket-Format: `explain_bracket`/`compute_power_level` **nicht** aufrufen; EDHREC nur mit Commander"); die drei Tools antworten `not_applicable`; `get_deck` trägt `board`. Der Prompt-Test aus Sprint 11 (jedes genannte Tool existiert) bleibt scharf | `mcp_server.py`, `tests/test_mcp_server.py` |
| 8 | **HA**: Attribut `format` am Deck-Sensor; `bracket`/`power_*` sind `null` statt Zahl. HA-Seite: keine Dashboard-Änderung — `deck_liste()` in `patch-mtg-gameroom.py` zeigt nur die Siegquote | `services/ha_metrics.py`, `services/ha_publisher.py`, `docs/ha-integration.md` |
| 9 | **Tests**: `insert_deck(db, name, format="Commander")` — der Default hält die 13 Testdateien auf ihrem heutigen Sinn (ein leeres Format wäre „nicht anwendbar", und jeder Bracket-Test fiele); neue Tests: Standard-Deck → `bracket None`, `power None`; Board-Trennung; dieselbe Karte in Main + Side bleibt zwei Zeilen; Formatwechsel nullt gespeicherte Werte | `tests/_helpers.py`, neue Tests |
| 10 | Version **0.47.0** + CHANGELOG + README (Feature-Liste ist Commander-zentriert) | — |

### Akzeptanz

- [ ] **Beide** Testdecks nach Sync: `computed_bracket IS NULL`, `power_score IS NULL`,
  `spellbook_bracket_tag = ''`; Kachel ohne BR/PWR; Deck-Seite ohne Bracket-/Power-Sektion, Hero
  aus `featured_image`, Kopfzeile „60 + 15 · Standard" bzw. „… · Pauper".
- [ ] Format-Filter in `Decks.tsx` zeigt genau drei Werte (Commander + die zwei Testformate).
- [ ] Die 22 Commander-Decks: Bracket-Tabelle byteidentisch zur Ist-Messung (7× 2 · 6× 3 · 9× 4),
  Power-Scores identisch.
- [ ] Ein Deck mit derselben Karte in Main und Sideboard hält **zwei** `deck_cards`-Zeilen.
- [ ] Migration 26 läuft gegen die echte DB-Kopie durch; `test_schema_upgrade` kennt den Fall.
- [ ] MCP-Prompt `analyze_deck` auf dem Standard-Deck ruft kein Bracket-/Power-Tool (Trockenlauf mit
  Claude, Protokoll in die Sprint-Datei).
- [ ] Testsuite grün (heute 320 + neue).

### Verifikation

`healthz` + Direktabruf am Container (Memory-Rezept), `GET /api/decks/<standard-id>`,
`GET /api/decks/` (alle 22 unverändert). ⚠️ `sensor.mtg_deck_<id>_winrate` entsteht erst nach einer
Partie im 90-Tage-Fenster — dass er fürs neue Deck fehlt, ist kein Fehler.

---

## Sprint 13 — Bedarf & Bestand bei Playsets

**Ziel:** „Wie viele Kopien sind frei, wie viele fehlen?" stimmt auch, wenn drei Decks je vier
Kopien wollen.

**Warum:** Befunde 10, 11. Bei Commander kostet der Doppelzähler eine Kopie je Deck, bei Playsets
vier — aus einem Schönheitsfehler wird eine **falsche Einkaufsliste**. Heute zählen zudem Maybeboard
und die Ordner „Disassembled"/„Older Versions" mit: Deck 10 ist die Altfassung von Deck 1, dieselben
Karten sind zweimal gebunden.

**Braucht:** 12 (`board`).

### Arbeitspakete

| # | Paket | Datei(en) |
|---|---|---|
| 1 | **`deck_usage_sql()`**: `board IN ('main','side')` **und** nur bindende Decks; ersetzt die vier Kopien (DUPLICATES_CTE, `sell_advisor`, `cardmarket_prices`-Spikes, MCP `suggest_bracket_safe_upgrades`) und die Completeness. Test: alle Konsumenten enthalten den Helper | `services/queries.py`, die vier Konsumenten, `tests/test_duplicates.py` |
| 2 | **Bindungs-Begriff**: `decks.binds_copies INTEGER DEFAULT 1` (Migration 27). Startwert aus Add-on-Option `non_binding_folders`, **Default `["Disassembled", "Older Versions"]` — entschieden 2026-09-14** („Work in Progress" bindet weiter); beim Sync nachgeführt; in der UI je Deck umschaltbar, Override gewinnt (wie `user_bracket`). Optionen schreiben = ganzes Objekt (Falle 10). ⚠️ Live betroffen: Deck 10 (Altfassung Sharknado), 11, 12, 17 — ihre ~430 Karten binden danach nichts mehr | `database.py`, `config.py`, `config.yaml`, `sync_service.py`, `routers/decks.py` |
| 3 | **Completeness** je Karte `owned` · `needed` · `bound_elsewhere` (Kopien in anderen bindenden Decks) — die eine Scheibe aus dem Vier-Zustands-Modell (Backlog), die Playsets brauchen; `most_expensive_missing` rechnet auf `needed − (owned − bound_elsewhere)` | `routers/decks.py`, `mcp_server.analyze_deck_completeness` |
| 4 | **Frontend**: Completeness-Sektion zeigt die drei Zahlen; Deck-Kachel trägt still „bindet keine Kopien"; Duplicates-Spalte „in Decks" = bindende Decks | `DeckCompletenessSection.tsx`, `Decks.tsx`, `Duplicates.tsx` |
| 5 | **HA**: `sensor.mtg_duplicates_surplus_*` und `unlisted_value_eur` bewegen sich — Ist-Messung vorher/nachher ins Protokoll. `mtg_verkauf_wochenreport` schwellt auf `unlisted_value_eur`: die Zahl ändert sich, **das ist die Korrektur, kein Rückfall** (W5-Lehre aus Sprint 06) | Protokoll, `CLAUDE.md` |
| 6 | Version **0.48.0** + CHANGELOG | — |

### Akzeptanz

- [ ] Konstruierter Test: 4 Kopien besessen, Deck A (bindend) will 4, Deck B (nicht bindend) will 4
  → Überschuss 0, `bound_elsewhere` für A = 0, Completeness A = 100 %.
- [ ] Live: keine Karte mehr mit `in_decks > total_owned`, deren Decks alle bindend sind (Ausgangswert
  aus Schritt 0 von Sprint 12).
- [ ] Die Abweichung der drei Verkaufszahlen vorher/nachher steht im Protokoll und ist erklärt.

---

## Sprint 14 — Legalität & Deck-Check

**Ziel:** Ein 60-Karten-Deck bekommt, was ihm statt Bracket und Power zusteht: **Fakten** — Größe,
Sideboard, Kopienlimit, Legalität im eigenen Format. Standard ist zudem das eine Format, das sich
**unter dem Deck wegbewegt** (Rotation, Bans).

**Warum:** Befunde 7, 12. Die Datenbasis liegt vollständig vor (7.858/7.858 Legalitäten, wöchentlicher
Refresh) und wird von niemandem gelesen — dieselbe Klasse wie `next_due_days`, das zwei Wochen lang
niemand las.

**Braucht:** 12 (`formats.py`, `board`).

### Arbeitspakete

| # | Paket | Datei(en) |
|---|---|---|
| 1 | **`services/legality.py`**: `check_deck(deck_id)` → `{main_count, side_count, rules, violations: [{kind: size · sideboard · copies · legality, card?, status?}], unknown_legality}`. Legalität aus `cards.legalities[scryfall_key]`: `legal` ok; `banned`/`not_legal`/`restricted` Verstoß; **fehlender Key = unknown, nicht legal** (gleiche Regel wie „unklassifiziert ≠ sauber" im Bracket). Kopienlimit: Basics und „A deck can have any number of cards named …" ausgenommen (Oracle-Text-Muster, eng wie die MLD-Muster) | neu, `tests/test_legality.py` |
| 2 | `GET /decks/{id}/legality`; nach jedem Sync **und nach jedem Scryfall-Refresh** für alle Decks mit Legality-Key rechnen, Ergebnis in `decks.legality_json` / `legality_checked_at` (Migration 28) — der Refresh ist der Weg, auf dem Rotation und Bans hereinkommen | `routers/decks.py`, `services/sync_service.py`, `services/card_enrichment.py`, `database.py` |
| 3 | **Frontend**: Sektion „Deck-Check" auf der Deck-Seite (je Regel grün/rot, illegale Karten mit Status), Kachel-Badge „⚠ 2" bei Verstößen. Läuft auch bei Commander (100/Singleton/`commander`-legal) — ergänzt, ersetzt nichts | `DeckLegalitySection.tsx` (neu), `Decks.tsx`, `api.ts`, `i18n.ts` |
| 4 | **Partial-Combos** („almost included") nach Legalität im Deckformat filtern; Commander unverändert | `services/combo_sync.py` |
| 5 | **MCP**: Tool `check_deck_legality`; `analyze_deck`-Prompt nennt es für alle Formate; `suggest_bracket_safe_upgrades` liefert für Formate ohne Bracket nur legale Surplus-Kandidaten | `mcp_server.py` |
| 6 | **HA**: Attribute `legal` (bool) + `violations` (Anzahl) am Deck-Sensor. **Entschieden 2026-09-14: ja** — Störungskarte `stoerung_mtg_deck_illegal_<id>` + Push, wenn ein Deck durch einen Refresh illegal wird (Dedup über `decks.legality_notified_at`; Konvention Störungstafel: bleibt stehen bis erledigt; `dismiss` **vor** dem Push, Hausregel). Weg wie die Price-Spike-Meldungen: Core-API-Proxy für die Karte, `notify_via_ha_service` für den Push. Nur **bindende** Decks melden — ein zerlegtes Deck darf illegal werden. HA-Seite: ⚠-Spalte in `deck_liste()`, Zeile in der `stoerung_*`-Tabelle der CLAUDE.md | `ha_metrics.py`, `ha_publisher.py`, `notifications.py`, `ha-infrastructure/tools/patch-mtg-gameroom.py`, `CLAUDE.md` |
| 7 | Doku: **Rotations-Rezept** — nach einer Rotation `POST /api/cards/backfill-scryfall?force=true`, sonst bis 7 Tage Verzug. Version **0.49.0** | `README.md`, `docs/ha-integration.md` |

### Akzeptanz

- [ ] Standard-Test-Deck: 60/15/≤ 4 grün; eine per Fixture eingelegte gebannte Karte wird mit Status
  benannt.
- [ ] Commander-Decks: Check läuft und meldet bei den 22 nichts Neues — meldet er doch etwas, ist das
  ein **Fund**, kein Fehler, und gehört ins Protokoll.
- [ ] Partial-Combos eines Standard-Decks enthalten keine Commander-only-Karten mehr.
- [ ] `unknown_legality` wird gezählt und angezeigt, nie als legal gewertet.

**Bewusst nicht:** Rotationsvorhersage („rotiert in 3 Monaten") — braucht eine gepflegte
Set→Rotationsdatum-Tabelle, die veraltet, sobald WotC den Rhythmus ändert (2023 auf drei Jahre) →
Backlog.

---

## Sprint 15 — Spielprotokoll für 1v1 und Best-of-3

**Ziel:** Eine Standard-Partie ist mit denselben Taps erfasst wie eine Commander-Partie — ohne jedes
Mal „4 Spieler" zu korrigieren — und **drei Partien lassen sich zu einem Match zusammenfassen**, mit
der Sideboard-Entscheidung je Partie.

**Warum:** Befund 13. Der Game Logger ist laut Entscheidung des Auftraggebers (2026-08-23)
unangetastet zu lassen; Teil A sind deshalb nur **Defaults, die dem Deck folgen.** Teil B (Bo3) ist
am **2026-09-14 gegen die Empfehlung entschieden** — der Plan hatte „Partie bleibt die Einheit"
vorgeschlagen, weil heute 1 Partie in 90 Tagen im Log steht. Max will das Match trotzdem als
Einheit. Konsequenz für den Bau: **das Match darf keinen zusätzlichen Pflichtschritt kosten**, sonst
wird es genau der Erfassungsweg, der nicht benutzt wird (fetchlog-Lehre: was in HA einen Knopf hat,
wird benutzt; was zusätzliche Felder verlangt, nicht).

**Braucht:** 12.

### Arbeitspakete — Teil A: Defaults folgen dem Deck

| # | Paket | Datei(en) |
|---|---|---|
| 1 | `deck_rules().default_pod_size` (Commander-Familie 4, Duel/Constructed 2). `DeckGameBase.pod_size` bleibt im Schema optional; **fehlt es, setzt `log_game` den Format-Default statt 4** — sonst landet jede Sprach-/Skript-Buchung über `mtg_log_game` (setzt kein `pod_size`) auf 4 | `services/formats.py`, `models/schemas.py`, `services/game_log.py` |
| 2 | **Das HA-Formular folgt dem Deck**: `ha_form.set_field("deck")` publiziert nach der Auswahl den `pod_size`-State auf den Format-Default; ein danach von Hand gesetzter Wert bleibt bis zum nächsten Deckwechsel | `services/ha_form.py`, `tests/test_ha_form.py` |
| 3 | **Frontend** `DeckPerformanceSection`: Default nach Format; Labels format-bewusst („Gegner / Commander" → „Gegner / Archetyp", Hint „z. B. Mono-Rot Aggro"); `on_play`-Statistik unverändert — in 1v1 aussagekräftiger als je | `DeckPerformanceSection.tsx`, `i18n.ts` |

### Arbeitspakete — Teil B: Best-of-3 (entschieden 2026-09-14)

| # | Paket | Datei(en) |
|---|---|---|
| 4 | **Migration 29**: `deck_games.match_id TEXT` (NULL = Einzelpartie, wie alle 1v1-Partien bisher und jede Commander-Partie), `deck_games.game_in_match INTEGER` (1–3), `deck_games.sideboard_notes TEXT` („was rein, was raus"). **Keine eigene Match-Tabelle** — das Match ist die Gruppe seiner Partien; Matchsieger = wer zuerst zwei Partien hat, gerechnet, nicht gespeichert. Damit kann ein Match nie einen anderen Stand haben als seine Partien | `database.py`, `models/schemas.py`, `tests/test_schema_upgrade.py` |
| 5 | **Der Match-Einstieg ist der Zeitstempel, nicht ein Formular**: eine Partie, die binnen `MATCH_WINDOW_MINUTES` (Startwert 90) nach der letzten Partie **desselben Decks gegen denselben Gegner** gebucht wird, erhält deren `match_id`, sonst eine neue. Damit kostet Bo3 im Alltag **null zusätzliche Eingaben** — drei Buchungen hintereinander sind ein Match. Explizites Übersteuern (`match_id: null` = „neues Match", oder eine bestehende id) geht über die API. Gegner-Gleichheit über `opponents` case-insensitiv getrimmt; leer = kein Auto-Match | `services/game_log.py`, `tests/test_game_log.py` |
| 6 | **Statistik**: `compute_performance_stats` bekommt `matches`, `match_wins`, `match_win_rate` und `game_2_3_win_rate` (Siegquote **nach** Sideboarding — die eine Zahl, die nur Bo3 liefern kann und die den Sideboard-Notizen ihren Sinn gibt). Commander-Decks zeigen den Block nicht (`format_rules.matches` false) | `services/deck_performance.py`, `models/schemas.py`, `tests/test_deck_performance.py` |
| 7 | **Frontend** `DeckPerformanceSection`: Partien eines Matches gruppiert („Match 2–1 · 12.09.", darunter G1/G2/G3 mit Play/Draw und Sideboard-Notiz), Feld „Sideboard" nur bei `game_in_match ≥ 2`; Knopf „weitere Partie dieses Matches" setzt Gegner und `match_id` vor | `DeckPerformanceSection.tsx`, `api.ts`, `i18n.ts` |
| 8 | **HA-Formular**: **ein** neues Feld `text.mtg_log_sideboard` (bleibt leer bei Commander); `match_id` kommt über das Zeitfenster, kein Feld. `sensor.mtg_log_status` sagt „Logged loss with Mono-Red · Match 1–1“, damit man sieht, dass die Gruppierung gegriffen hat | `services/ha_form.py`, `docs/ha-integration.md`, `ha-infrastructure/tools/patch-mtg-gameroom.py` (FORMULAR-Zeile) |
| 9 | **MQTT `log_game`** nimmt `sideboard_notes` und optional `match_id`; `mtg_log_game`-Skript bekommt ein optionales Feld `sideboard` | `services/ha_mqtt.py`, `ha-infrastructure/pi-ha/config/scripts.yaml` |
| 10 | **HA-Deck-Sensor**: Attribute `matches`, `match_win_rate` neben `win_rate` (bei Commander `null`) | `ha_metrics.py`, `ha_publisher.py` |
| 11 | Doku + Version **0.50.0** + CHANGELOG | — |

> ⚠️ **Das Zeitfenster ist ein Urteil, keine Regel** — 90 Minuten decken ein Bo3 mit Pause, aber
> zwei getrennte Bo1-Partien gegen denselben Gegner am selben Abend würden zusammengezogen. Das ist
> der bewusst gewählte Fehler: eine falsche Gruppierung korrigiert man mit einem Klick, ein
> zusätzliches Pflichtfeld verhindert die Erfassung. Konstante mit Begründung im Code, wie
> `EARLY_COMBO_MANA_CEILING`.

### Akzeptanz

- [ ] HA-Formular: Standard-Deck wählen → `number.mtg_log_pod_size` springt auf 2, Commander-Deck → 4;
  ein manuell gesetzter Wert überlebt bis zum nächsten Deckwechsel.
- [ ] `log_game` per MQTT **ohne** `pod_size` auf ein Standard-Deck → 2 in `deck_games`.
- [ ] Drei Buchungen binnen 90 Min gegen denselben Gegner → **eine** `match_id`, Statistik
  `matches = 1`, `match_wins` nach der 2-von-3-Regel; die vierte Buchung nach 2 h → neue `match_id`.
- [ ] Commander-Partien tragen `match_id NULL`, ihre Statistik ist byteidentisch zu vorher (Test mit
  den heutigen Fixtures aus `test_deck_performance.py`).
- [ ] Migration 29 gegen die echte DB-Kopie; alle bestehenden Partien bleiben Einzelpartien.

---

## Entscheidungen des Auftraggebers (getroffen 2026-09-14)

| # | Frage | Entscheidung | Folge im Plan |
|---|---|---|---|
| 1 | Welche Ordner binden keine Kopien? | **`Disassembled` + `Older Versions`** (Empfehlung angenommen). „Work in Progress" bindet | Sprint 13, Paket 2: Default der Option steht fest |
| 2 | Rotation-/Ban-Push als Störungskarte? | **Ja** (Empfehlung angenommen) | Sprint 14, Paket 6 ist Pflicht, nicht optional |
| 3 | Bo3-Match-Erfassung? | **Ja, `match_id` + Sideboard-Notiz** — **gegen die Empfehlung** | Sprint 15 bekommt Teil B (Pakete 4–10) und ist damit kein kleiner Sprint mehr; Bauform „Zeitfenster statt Pflichtfeld", damit der Weg auch benutzt wird |
| 4 | Formate über Standard hinaus? | **Pioneer, Modern, Pauper, Premodern, Legacy.** Brawl **nicht** | Sprint 12: zwei Testdecks (Standard + eines der fünf), Akzeptanz an beiden. Die fünf teilen die 60/15/4-Regeln und unterscheiden sich nur im Scryfall-Key (`pioneer` · `modern` · `pauper` · `premodern` · `legacy`) — alle fünf stehen in der Tabelle. Brawl bleibt als Zeile drin, ungetestet |

## Bewusst nicht gemacht → Backlog

- Power-Score oder Bracket-Analogon für 60-Karten-Formate (Leitentscheidung 5).
- Rotationsvorhersage (Sprint 14).
- Vollständiges Vier-Zustands-Missing-Modell — nur `bound_elsewhere` kommt (Sprint 13).
- Meta-/Archetyp-Daten (MTGGoldfish o. ä.) — eine neue Fremdquelle braucht ihre eigene Bewertung.
- Eine eigene Match-Tabelle mit gespeichertem Matchergebnis (Sprint 15 rechnet es aus den Partien).

## Reihenfolge, Versionen, Größe

```
0.46.2 committen + deployen (Schritt 0)
12 Format-Wahrheit (0.47.0) ──► 13 Bedarf & Bestand (0.48.0)
                             ├─► 14 Legalität & Deck-Check (0.49.0)
                             └─► 15 Spielprotokoll 1v1 + Bo3 (0.50.0)
```

13, 14 und 15 sind untereinander unabhängig; 12 ist Pflicht zuerst. Grobe Größe: 12 ≈ Sprint 04
(Migration + drei Schichten + Tests), 13 ≈ Sprint 06, 14 ≈ Sprint 03, 15 seit der Bo3-Entscheidung
≈ Sprint 07 (Migration, Statistik, Frontend, HA-Formular, HA-Seite). Empfohlene Reihenfolge nach 12:
**14 vor 13 vor 15** — Legalität ist das, was ein Standard-Deck ohne Zutun kaputtgehen lässt, der
Bedarf wird erst mit mehreren 60er-Decks falsch, und Bo3 braucht gespielte Partien, die es noch
nicht gibt.

**Deploy-Erinnerungen** wie in der [README](README.md): drei Versionsstellen, `healthz` **und**
Direktabruf am Container, Migrationen gegen die echte DB-Kopie, Add-on-Optionen als ganzes Objekt,
HA-Dashboards über `patch-mtg-gameroom.py --apply` und Snapshots neu ziehen.
