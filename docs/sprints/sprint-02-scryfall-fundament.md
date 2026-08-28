# Sprint 02 — Scryfall-Datenfundament

**Status: ✅ umgesetzt in 0.36.0, deployed + verifiziert am 2026-08-28.** Ist-Protokoll am Ende.

**Ziel:** Die Löcher in der `cards`-Tabelle schließen, die jede weitere Arbeit blockieren:
`legalities` (war 0 % — Archidekt liefert hartcodiert `"{}"`), `game_changer`, `reserved`,
`cardmarket_id` (in Deck-1-Stichprobe 0/98), und `type_line` auf Scryfall-Form normalisieren.
**Voraussetzung für Sprints 04, 05, 06.**

**Warum (Befunde):** B4, B3, B23 in [review-befunde.md](review-befunde.md).

## Umgesetzt

| # | Paket | Befund | Datei |
|---|---|---|---|
| 1 | **Migration 21**: `cards.game_changer`, `cards.reserved`, `cards.scryfall_enriched_at` (alle NULL-fähig — NULL heißt „nie gefragt", nicht „nein") + Normalisierung der Bestands-Typzeilen | B4/B23 | `database.py` (`CARD_COLUMN_MIGRATIONS`, `_migration_21`) |
| 2 | **Backfill** `backfill_scryfall_fields()`: `POST /cards/collection`, 75er-Chunks, Pflicht-Header (im Client), **0,5 s Chunk-Pacing** wegen der 2/s-Grenze auf `/collection`, 429 → Lauf beenden statt weiterklopfen. Schreibt `game_changer`, `reserved`, `legalities`, `keywords`, `edhrec_rank`, `cardmarket_id`, `type_line`; füllt `oracle_text`/`cmc`/`mana_cost` **nur wo leer** | B4 | **neu:** `services/card_enrichment.py` |
| 3 | `parse_scryfall_card()`: `game_changer` + `reserved` mitlesen (als 0/1) | B23 | `clients/scryfall.py` |
| 4 | `parse_archidekt_card()`: Typzeile in Scryfall-Form (`_type_line()`), `normalize_type_line()` am **einzigen Schreibpfad** — dasselbe Muster wie die Farben in 0.34.0 | B3 | `clients/archidekt.py`, `services/queries.py`, `services/sync_service.py` |
| 5 | **Post-Sync-Hook**: läuft nach jedem Sync, gedeckelt auf 3000 Printings (`POST_SYNC_MAX_CARDS`), best effort **mit** `logger.warning` — nicht still geschluckt | — | `services/sync_service.py` |
| 6 | Manueller Trigger `POST /api/cards/backfill-scryfall` (`max_cards`, `force`) + Statusabfrage `GET /api/cards/enrichment` | — | `routers/cards.py` |
| 7 | Version 0.36.0 an allen drei Stellen + CHANGELOG | — | `config.yaml`, `version.py`, `package.json` |

### Zwei Dinge, die im Sprint-Text nicht standen und trotzdem dazugehörten

**(a) Der Sync hätte den Backfill jede Nacht überschrieben.** `upsert_card` ist der einzige
Karten-Schreibpfad, und die nächtliche Synchronisierung fährt ihn mit **Archidekt**-Daten:
`legalities=excluded.legalities` schrieb also `{}` über jede gerade gelernte Legalität, und ein
dünner Eintrag (ohne `oracleCard`) nullte zusätzlich `edhrec_rank` und `oracle_text`. Die Felder,
zu denen Archidekt nichts sagen kann, sind jetzt dort geschützt — genau wie `cardmarket_id` es
schon war. **Ohne diesen Teil hätte die Anreicherung bis 03:00 gehalten.**

**(b) Die Kommaform war nicht nur unschön.** Der Typfilter aus 0.34.0 matcht einen Substring vor
dem Halbgeviertstrich, deshalb antworteten beide Formen korrekt und der Unterschied blieb
unsichtbar (so steht es auch in B3). Was sie **wirklich** brach, ist jedes Muster mit **zwei**
Typwörtern: `type_line NOT LIKE '%Basic Land%'` traf kein einziges Archidekt-Basisland, weil dort
`Basic, Land — Plains` steht. Im Preisalarm trägt eine zweite, namensbasierte Ausschlussliste die
Last; in der MTGStocks-Near-ATH-Abfrage gibt es keine zweite Hälfte (folgenlos nur, weil
MTGStocks deaktiviert ist). Beides ist mit der Normalisierung erledigt.

### Entscheidungen, die beim Bauen gefallen sind

- **NULL bleibt NULL.** Eine Printing, die Scryfall nicht auflösen kann, wird gestempelt (also nicht
  wieder gefragt), behält aber `game_changer = NULL`. Ein erfundenes `0` wäre bequemer, aber genau
  dieses Feld entscheidet in Sprint 04 einen Bracket. `GET /api/cards/enrichment` weist deshalb
  **`asked`** getrennt von **`game_changers`** aus.
- **Stempel + 7-Tage-Frist statt „einmal und fertig".** Ohne Stempel würde jede Nacht der ganze
  Bestand neu gecrawlt; mit einer *unbefristeten* Einmal-Anreicherung wäre er für immer auf dem
  Stand des ersten Kontakts. Die Frist macht drei Dinge selbstheilend: WotC ändert die
  Game-Changers-Liste, EDHREC-Ränge wandern, und ein Archidekt-Sync schreibt seine eigenen
  `keywords` zurück. Im Dauerbetrieb ist das ein Zehntel des Bestands pro Nacht.
- **Der Post-Sync-Lauf ist gedeckelt, der Endpunkt nicht.** Ein Erstlauf soll die nächtliche
  Synchronisierung nicht unvorhersehbar verlängern; wer das Fundament *jetzt* braucht, ruft den
  Endpunkt.
- **Preise fasst die Anreicherung nicht an.** Scryfall-Preise sind ein Tages-Snapshot Retail; sie
  würden mit dem Cardmarket-Pfad um dieselben Spalten streiten.

## Akzeptanz

- [x] Der Backfill schreibt `legalities` ≠ `{}`, `game_changer`/`reserved`, `cardmarket_id` und die
  kanonische `type_line` — 9 Tests in `tests/test_card_enrichment.py`.
- [x] Ein Archidekt-Sync danach macht nichts davon rückgängig (eigener Test).
- [x] `type_line` ohne Kommas zwischen Typwörtern; Typfilter-Verhalten aus 0.34.0 unverändert
  (`tests/test_type_line.py` + die bestehenden `test_collection_filters.py`).
- [x] **Live:** `game_changers = 26` von 7770 Printings (Scryfall `is:gamechanger` = 53 gesamt).
  ⚠️ **Welche 26 es sind, ist noch nicht nachgesehen** — dafür fehlt eine Abfragemöglichkeit;
  `CardResponse` führt das Feld nicht, und die Karten-Tabelle enthält neben Besitz auch Deck- und
  Wunschlisten-Printings. Kommt mit der Bracket-UI in Sprint 04 von selbst.

## Verifikation

- [x] Migrationstest auf einer **Alt-Datenbank** (Schema 20, ohne die drei Spalten, mit einer
  Komma-Typzeile) → Spalten da, Typzeile kanonisch, Flags weiterhin NULL:
  `tests/test_schema_upgrade.py::test_startup_adds_the_enrichment_columns_and_fixes_the_type_lines`.
- [x] Typfilter-Regressionstests grün.
- [x] Backend: **242/244 grün** (die 2 Fehlschläge sind der Altbestand `test_static_files.py`, auch
  auf unverändertem Stand — siehe [README](README.md)).
- [x] Backfill-Lauf auf der Live-DB: **7770 Printings, 104 Requests, 147 s, `status: completed`,
  0 unresolved, kein einziger 429** (Log: „Scryfall enrichment completed"). Die 10.214 aus dem
  Sprint-Text waren Sammlungs-*Exemplare*, nicht Printings — `cards` hat 7770 Zeilen.

## Ist-Protokoll (2026-08-28, gegen den Pi 5 gemessen)

| Schritt | Ergebnis |
|---|---|
| Deploy | `healthz` → `{"status":"ok","version":"0.36.0","db":true,"scheduler_running":true}`, `state: started` |
| **Migration 21** | „canonicalised the type line of **3382 of 3382** comma-form cards" in **70 ms**. Die 3382 sind genau die Archidekt-Zeilen mit ≥2 Typwörtern oder ≥2 Subtypen — eine Zeile wie `Creature — Bear` trug auch in der alten Fassung kein Komma und war schon kanonisch. |
| **Backfill** | `checked: 7770 · enriched: 7770 · unresolved: 0 · game_changers: 26` in **147 s**, keine 429. |
| `legalities` | **41 → 7770** Karten. Das war das größte Loch: praktisch der gesamte Bestand hatte keine Format-Legalität. |
| `cardmarket_id` | `without_cardmarket_id: 0` — der Cardmarket-Backfill hatte den Bestand inzwischen von selbst erreicht (B4 maß hier 0/98 in Deck 1). Nichts nachzuholen, aber jetzt aus einer Quelle. |
| `reserved` | **0 von 7770.** Plausibel für eine Sammlung mit ~0,9 € Durchschnittswert je Printing, aber ⚠️ **unbestätigt** — dass der Schreibpfad funktioniert, belegen die 26 Game Changers aus demselben `UPDATE`. |
| Typzeilen Deck 1 | 98 Karten, **0 mit Komma**, 38 mit Halbgeviertstrich (B3 maß 37 — der Backfill hat eine Zeile aus Scryfall vervollständigt). Beispiel: `Legendary, Enchantment` → `Legendary Enchantment`. |
| **Voller Sync danach** | `completed`, 9188 Einträge, 15 min, `error: ""` — und **`with_legalities` steht danach immer noch auf 7770**, `game_changers` auf 26, Deck 1 weiter bei 0 Kommas. Das ist der Beweis für Punkt (a): derselbe Sync hätte vorher alle 7770 Legalitäten mit `{}` überschrieben. Der Post-Sync-Hook lief und fand nichts (`checked: 0`, deshalb keine Logzeile) — die „einmal fragen"-Regel greift in Produktion. |

**Nebenbefund beim Verifizieren:** `GET /api/cards/enrichment` brauchte **12 s** für sechs
Aggregate über 7770 Zeilen. Das ist zu langsam für das, was es tut — ein Kandidat für Sprint 09,
kein Blocker.
