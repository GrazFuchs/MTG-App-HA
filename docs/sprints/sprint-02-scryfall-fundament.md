# Sprint 02 — Scryfall-Datenfundament

**Status: ✅ umgesetzt in 0.36.0 (2026-08-27). Deploy + Live-Backfill stehen aus** — siehe
„Offen (Deployment)" am Ende.

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
- [ ] **Live:** `SELECT COUNT(*) FROM cards WHERE game_changer = 1` ≈ Anzahl besessener Game
  Changers (Scryfall `is:gamechanger` = 53 gesamt; Stichprobe: Rhystic Study im Bestand → 1).
  → nach dem Deployment, siehe unten.

## Verifikation

- [x] Migrationstest auf einer **Alt-Datenbank** (Schema 20, ohne die drei Spalten, mit einer
  Komma-Typzeile) → Spalten da, Typzeile kanonisch, Flags weiterhin NULL:
  `tests/test_schema_upgrade.py::test_startup_adds_the_enrichment_columns_and_fixes_the_type_lines`.
- [x] Typfilter-Regressionstests grün.
- [x] Backend: **242/244 grün** (die 2 Fehlschläge sind der Altbestand `test_static_files.py`, auch
  auf unverändertem Stand — siehe [README](README.md)).
- [ ] Backfill-Lauf auf der Live-DB (10.214 Karten ÷ 75 ≈ 137 Requests) im Add-on-Log ohne
  429-Sperren.

## Offen (Deployment)

1. Deploy 0.36.0 (Build läuft auf dem Pi 5; danach `state: started` **und** `healthz` prüfen).
2. `POST /api/cards/backfill-scryfall` **einmal ohne `max_cards`** — mit ~137 Requests bei 0,5 s
   Pacing ein Lauf von wenigen Minuten. Alternativ passiert es über die nächsten ~4 Nächte von
   selbst (3000 Printings je Sync).
3. `GET /api/cards/enrichment` gegenlesen: `pending` fällt auf 0, `with_legalities` ≈ `total_cards`,
   `game_changers` plausibel (Erwartung: eine niedrige zweistellige Zahl über alle Printings —
   die 12 Wunschlisten-Treffer aus B27 sind **nicht** besessen und zählen hier nicht mit).
4. Migration-21-Zeile im Log lesen: „canonicalised the type line of N of N comma-form cards" — N
   sollte der Größenordnung des Bestands entsprechen, nicht 0.
