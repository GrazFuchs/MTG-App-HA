# Sprint 02 — Scryfall-Datenfundament

**Ziel:** Die Löcher in der `cards`-Tabelle schließen, die jede weitere Arbeit blockieren:
`legalities` (heute 0 % — Archidekt liefert hartcodiert `"{}"`), `game_changer`, `reserved`,
`cardmarket_id` (in Deck-1-Stichprobe 0/98), und `type_line` auf Scryfall-Form normalisieren.
**Voraussetzung für Sprints 04, 05, 06.**

**Warum (Befunde):** B4, B3, B23 in [review-befunde.md](review-befunde.md).

## Arbeitspakete

1. **Migration 21** (`backend/app/database.py`, Muster der 19 bestehenden Migrationen):
   `cards.game_changer INTEGER` (NULL = nie gefragt, 0/1 = Antwort) · `cards.reserved INTEGER` ·
   `legalities` bleibt als Spalte, wird aber befüllbar. Kein `NOT NULL` — der Backfill füllt.
2. **Backfill** nach dem bewährten Muster `backfill_cardmarket_ids()`
   (`services/cardmarket_prices.py`): Scryfall `POST /cards/collection`, 75er-Chunks,
   Pflicht-Header `User-Agent` + `Accept`, 100-ms-Pacing, 429 respektieren. Je Karte schreiben:
   `game_changer`, `reserved`, `legalities` (JSON), `edhrec_rank` (auffrischen),
   **`cardmarket_id`** (die bestehende Backfill-Logik hat viele Printings nie berührt — B4),
   **`type_line`** (kanonische Scryfall-Form) und `cmc`/`mana_cost`, wo leer.
   Unauflösbare Printings wie gehabt mit Sentinel markieren, damit sie nicht erneut gefragt werden.
3. **`parse_scryfall_card()`** (`clients/scryfall.py`): `game_changer` + `reserved` mitlesen.
4. **`parse_archidekt_card()`** (`clients/archidekt.py`): `type_line` ab sofort in Scryfall-Form
   zusammensetzen (Leerzeichen statt Kommas: `Legendary Creature — Pirate Shark`).
   ⚠️ Danach `type_line_head_sql` + Karten-Typfilter regressionstesten — das
   CHANGELOG-0.34.0-Verhalten (Filter matcht nur vor dem Halbgeviertstrich) muss erhalten bleiben.
   Bestehende Tests: `test_collection_filters.py`.
5. **Hook:** Backfill läuft nach jedem Sync für neue/geänderte Karten mit (an den bestehenden
   Post-Sync-Pfad hängen, best effort mit Logging — nicht still schlucken).
6. Manueller Trigger: `POST /api/cards/backfill-scryfall` (Vorbild: `backfill-colors`).

## Akzeptanz

- Deck-1-Stichprobe: `legalities` ≠ `{}`, `game_changer`/`reserved` gesetzt, `cardmarket_id`
  ≠ NULL für auflösbare Printings, `type_line` ohne Kommas zwischen Typwörtern.
- `SELECT COUNT(*) FROM cards WHERE game_changer = 1` ≈ Anzahl besessener Game Changers
  (Scryfall `is:gamechanger` = 53 gesamt; Stichprobe: Rhystic Study im Bestand → 1).

## Verifikation

- Migration-Test nach dem Muster `tests/test_schema_upgrade.py` (Alt-DB → Start → Spalten da).
- Typfilter-Regressionstests grün.
- Backfill-Lauf auf der Live-DB (10.214 Karten ÷ 75 ≈ 137 Requests ≈ 2–3 min) im Add-on-Log
  ohne 429-Sperren.
