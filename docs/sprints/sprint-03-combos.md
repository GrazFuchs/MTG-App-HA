# Sprint 03 — Combo-Abdeckung reparieren

**Status: ✅ umgesetzt in 0.37.0 (2026-08-28). Deploy + Nachzieh-Lauf stehen aus** — siehe
„Offen (Deployment)" am Ende.

**Ziel:** Der Combo-Cache (`deck_combos`) wird vollständig und ehrlich: alle Decks erfasst,
`missing_cards` befüllt, Fehler sichtbar. **Voraussetzung für Sprint 04 (Bracket) und die
Wishlist-Brücke in Sprint 06.**

**Warum (Befunde):** B24 in [review-befunde.md](review-befunde.md).

## Befund zuerst — die Messung vor dem Umbau (2026-08-28, Live-Stand)

| ID | Deck | Combos | vollständig | teilweise | mit `missing_cards` |
|---|---|---:|---:|---:|---:|
| 1 | Sharknado | 27 | 0 | 27 | 0 |
| 2 | You f\*\*\*\*\* with Squirrels, Morty | 235 | 12 | 223 | 0 |
| 3 | They don't scurry… | 29 | 0 | 29 | 0 |
| 5 | Emerald Hill Zone, Fast! | 142 | 3 | 139 | 0 |
| 4, 6–21 | **17 weitere Decks** | **0** | 0 | 0 | 0 |
| | **Summe** | **433** | **15** | **418** | **0** |

Deckt sich mit B24 (dort 484 über 19 Decks — inzwischen sind es 21 Decks und ein Bestand hat sich
verschoben). **Zwei unabhängige Ursachen, beide am Code und an der Live-API belegt:**

**(a) Die 17 leeren Decks wurden nie gefragt.** Der Combo-Aufruf steht in `_do_full_sync` **hinter**
dem `continue` des inkrementellen Syncs: ein Deck, das sich seit Einführung des Features nicht
geändert hat, erreicht ihn nie. Im Live-Log desselben Tages nachweisbar — 20 Zeilen
„Deck … unchanged since last sync, skipping". Die Hypothese aus dem Sprint-Text ist damit
bestätigt.

**(b) ⚠️ Der Audit-Hinweis zu `missing_cards` war FALSCH.** Er lautete, der Client verwerfe die
`almostIncluded`-Buckets. Tut er nicht — er liest sie (`results.almostIncluded`), deshalb liegen ja
418 Teil-Combos im Cache. Die echte Ursache steht in der Live-Antwort:

```
results-Schlüssel: identity · included · includedByChangingCommanders · almostIncluded ·
                   almostIncludedByAddingColors · almostIncludedByChangingCommanders ·
                   almostIncludedByAddingColorsAndChangingCommanders
Combo-Schlüssel:   id · of · uses · notes · prices · status · spoiler · identity · includes ·
                   produces · requires · legalities · popularity · bracketTag · description ·
                   manaNeeded · variantCount · manaValueNeeded · easyPrerequisites ·
                   notablePrerequisites
```

**Es gibt kein `missingCards`.** `_extract_combo_fields` suchte ein Feld, das die API nicht kennt —
also blieb die Liste auf allen 418 Einträgen leer. Was fehlt, muss abgeleitet werden: `uses` minus
Deckliste. Gegenprobe an Deck 1: **alle 27 Teil-Combos sind exakt eine Karte entfernt**, und
*Breath of Fury* (zu *Anger* im Deck) ist darunter — genau das Akzeptanzbeispiel des Sprints.

💡 Nebenbefund für Sprint 04: jede Combo führt `bracketTag`, `popularity`, `manaValueNeeded` und
`legalities` mit. Das ist der Input, den die Bracket-Rechnung ohnehin braucht.

## Umgesetzt

| # | Paket | Datei |
|---|---|---|
| 1 | **Migration 22**: `decks.combos_synced_at` — der Stempel, der „gefragt, nichts gefunden" von „nie gefragt" trennt (beide hinterlassen 0 Zeilen in `deck_combos`). Decks mit Bestand erben das Datum ihrer neuesten Zeile | `database.py` |
| 2 | **`missing_cards` ableiten**: `uses` minus Deckliste, DFC unter beiden Gesichtern gematcht, Commander zählt als vorhanden; wenn nichts *Benanntes* fehlt, wird das fehlende **Template** genannt statt einer leeren Liste | `services/combo_sync.py` |
| 3 | **Nachzieh-Lauf** `sync_combos_for_stale_decks()`: fragt jedes fällige Deck (nie gefragt oder älter als 14 Tage), 1 s Pause je Deck, ein Fehlschlag stoppt die anderen nicht. Läuft nach **jedem** Sync — nach einem normalen also nur für die übersprungenen Decks | `services/combo_sync.py`, `services/sync_service.py` |
| 4 | **Fehler benennen statt schlucken**: `sync_combos_for_deck` wirft jetzt, statt 0 zurückzugeben; `POST /{deck_id}/combos/sync` antwortet **502** statt `{"count": 0}`; je Deck wird das Ergebnis geloggt, auch die 0 | `services/combo_sync.py`, `routers/decks.py` |
| 5 | **`POST /api/decks/combos/sync-all`** (`max_decks`, `force`) — vor den `/{deck_id}`-Routen deklariert, sonst läse FastAPI „combos" als Deck-ID | `routers/decks.py` |
| 6 | **UI ehrlich**: Kopfzeile „Combos · n IN DECK · m ONE CARD AWAY" statt „Combos in this Deck · m PARTIAL"; Spalten „Complete — every card in the deck" / „One card away — not in the deck yet"; fehlende Karte als „Missing: …" | `components/deck/DeckCombosSection.tsx` |
| 7 | Ignorierte Buckets werden gezählt und geloggt — die Entscheidung, Combos mit fremder Farbidentität wegzulassen, bleibt sichtbar. Nebenbei der eingefrorene `USER_AGENT` 0.9.0 auf `VERSION` gezogen | `clients/spellbook.py` |
| 8 | Version 0.37.0 an allen drei Stellen + CHANGELOG | — |

### Eine Entscheidung, die beim Bauen dazukam

**Der API-Aufruf steht jetzt vor dem `DELETE`.** `sync_combos_for_deck` löscht den Bestand des
Decks, bevor es neu schreibt. Käme der Spellbook-Aufruf danach, ließe ein Ausfall das Deck **leer**
zurück — schlimmer als der veraltete Stand. Jetzt wirft der Fehler, bevor irgendetwas angefasst
ist; eigener Test (`test_the_cached_combos_survive_until_the_replacement_is_in`).

## Akzeptanz

- [x] Jedes Deck hat nach dem Nachzieh-Lauf einen Bestand **oder** einen benannten Log-Eintrag mit
  Ursache — Tests `test_the_topup_asks_about_every_deck_that_was_never_asked`,
  `test_one_failing_deck_does_not_stop_the_others`.
- [x] Deck 1: `Breath of Fury` erscheint als fehlende Karte — an der Live-Antwort abgeleitet und
  als Einheitentest festgehalten.
- [x] Vollständige und Teil-Combos sind in der UI klar getrennt beschriftet.
- [ ] **Live:** Vorher/Nachher-Zählung je Deck nach dem Deploy (die Tabelle oben ist das „Vorher").

## Verifikation

- [x] 13 neue Tests in `tests/test_combo_sync.py` + Migrationstest auf einer Alt-Datenbank
  (Schema 21, ohne `combos_synced_at`) in `tests/test_schema_upgrade.py`.
- [x] Backend: **256/258 grün** (die 2 Fehlschläge sind der Altbestand `test_static_files.py` —
  siehe [README](README.md)).
- [x] Frontend: `tsc -b && vite build` grün.
- [ ] Stichprobe gegen die Live-API nach dem Deploy: `included` muss den `is_partial=0`-Einträgen
  entsprechen, `almostIncluded` den Teil-Combos mit gefüllter `missing_cards`.

## Offen (Deployment)

1. Deploy 0.37.0 (Build auf dem Pi 5; danach `state: started` **und** `healthz` prüfen).
2. `POST /api/decks/combos/sync-all` — 21 Decks à ~1 s plus Antwortzeit, also gut eine Minute.
   Alternativ erledigt es der nächste Sync von selbst.
3. Zählung wiederholen und der „Vorher"-Tabelle gegenüberstellen; erwartet werden Bestände für
   **alle 21** Decks und `missing_cards` auf jeder Teil-Combo.
