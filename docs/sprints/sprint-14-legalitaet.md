# Sprint 14 — Legalität & Deck-Check

**Status: ✅ umgesetzt in 0.48.0 am 2026-09-15, gegen die echte DB verifiziert.**
Ist-Protokoll am Ende.

**Ziel:** Ein 60-Karten-Deck bekommt, was ihm statt Bracket und Power-Score zusteht: **Fakten** —
Größe, Sideboard, Kopienlimit, Legalität im eigenen Format. Und Standard ist das eine Format, das
sich **unter dem Deck wegbewegt** (Rotation, Bans).

**Warum:** Befunde 7 und 12 in [plan-60-karten-decks.md](plan-60-karten-decks.md).

**Braucht:** Sprint 12 (`formats.py`, `board`).

## Der Anlass: die Daten lagen seit Monaten vollständig da

**8022 von 8022 Karten** tragen Scryfalls `legalities`-Objekt mit 23 Formatschlüsseln, seit Sprint
02 wöchentlich aufgefrischt — und **kein einziger Konsument hat es gelesen**. Dieselbe Klasse wie
`next_due_days` am Hundesensor: *ein Fakt in der Datenbank ist kein Monitoring.*

## Was der erste Lauf gegen die echten Daten falsch gemacht hat

Drei Fehlalarme, jeder für sich hätte den Check unbrauchbar gemacht — **ein Prüfer, der
grundlos meckert, wird abgeschaltet statt repariert.**

### 1. Token sind keine Karten

Archidekt lässt Token in einer Deckliste stehen, als Erinnerung daran, was das Deck erzeugt.
Deck 7 las sich deshalb als **104 Karten in einem 100-Karten-Format**, und drei seiner „Karten"
galten als nicht Commander-legal:

```
Frog Lizard   layout=token  'Token Creature — Frog Lizard'
Copy          layout=token  'Token'
Myr           layout=token  'Token Artifact Creature — Myr'
```

Vier Token-Zeilen in zwei Decks, und sie erzeugten beide Fehlerarten gleichzeitig. Sie fliegen
jetzt **überall** raus, wo ein Deck gezählt wird (`token_exclusion_sql` in `queries.py`) — nicht
nur hier, damit Deckseite und Check nicht über die Deckgröße streiten können.

### 2. Ein Format ohne Sideboard hat auch keinen Sideboard-Stapel

Commander hat keins, Archidekt bietet die Kategorie trotzdem an, und Max nutzt sie als Notizblock
(Deck 20: drei Karten, Deck 21: eine). Das als Regelverstoß zu melden ist Lärm über eine
Gewohnheit. Bei `side_max == 0` zählen diese Karten jetzt wie ein Maybeboard: **außerhalb des
Decks, nicht gezählt, nicht geprüft.** Wo das Format ein Sideboard *hat*, gilt die Grenze.

### 3. Die Board-Zuordnung war noch geraten

Migration 26 hat `board` aus dem **Kategorienamen** befüllt, gegen eine Liste von fünf Namen — mehr
kann eine Migration ohne Netz nicht. Die Liste ist aber **konstruktionsbedingt unvollständig**:
„Backlog" steht nicht darauf, und Deck 10 hat 29 Karten dort. Das Deck las sich als 132
Hauptkarten.

**Migration 27 markiert deshalb jedes Deck für einen Voll-Re-Sync.** Das ist die zweite Hälfte von
Migration 26, nicht eine neue Idee: 26 markierte die zwei Decks, deren *Format* falsch war, 27 den
Rest, weil deren *Boards* genauso veraltet sind und der Check jetzt davon abhängt.

## Zwei Fallen, um die herum gebaut wurde

**20× Rat Colony ist legal.** Deck 3 hält zwanzig davon in einem Singleton-Format, weil die Karte
in ihrem eigenen Regeltext steht: *„A deck can have any number of cards named Rat Colony."* Ohne
diese Ausnahme meldet der Check **neunzehn Verstöße an einem korrekten Deck**. Die Ausnahme wird
aus dem Oracle-Text gelesen, nicht aus einer Namensliste — die Liste ist der Teil, der veraltet.

**Der Dedup-Schlüssel ist, *was* falsch war, nicht *wann* geschaut wurde.** Die naheliegende
Fassung — „zuletzt gemeldet" gegen „zuletzt geprüft" — liest sich plausibel und ist falsch: der
Check läuft jede Nacht, also ist der Prüfstempel jede Nacht neuer, und dieselbe gebannte Karte
würde für immer gemeldet. **Vom Test gefunden, nicht im Betrieb** — der einzige Grund, warum das
hier als Lehre steht und nicht als Incident.

## Umgesetzt

| # | Paket | Datei(en) |
|---|---|---|
| 1 | **`services/legality.py`** — `check_deck`, `check_and_store`, `check_all_decks`, `annotate_combos` | neu |
| 2 | **Migration 27** — `legality_json`, `_checked_at`, `_notified_at`, **`_notified_key`**; markiert alle Decks für den Re-Sync | `database.py` |
| 3 | `GET /decks/{id}/legality` (+ `?recheck`), `POST /decks/legality/recheck-all` | `routers/decks.py` |
| 4 | Check läuft **nach dem Sync** und **nach dem Scryfall-Refresh** — letzteres ist der Weg, auf dem Rotation und Bans hereinkommen | `sync_service.py`, `routers/cards.py` |
| 5 | **Token-Ausschluss** in Deckliste, Deckdetail, Router und Check | `queries.py` + drei Aufrufer |
| 6 | Partial-Combos tragen `missing_not_legal` + `completable` | `legality.py`, `routers/decks.py`, `schemas.py` |
| 7 | **MCP** `check_deck_legality`, im `analyze_deck`-Prompt als Schritt 3 | `mcp_server.py` |
| 8 | **HA**: `legal` / `violations` / `violation_detail` am Deck-Sensor; Störungskarte `stoerung_mtg_deck_illegal_<id>` im Nachtlauf | `ha_metrics.py`, `ha_publisher.py`, `notifications.py`, `scheduler.py` |
| 9 | **Frontend**: Sektion „Deck-Check" unter dem Bracket, i18n EN + DE | `DeckLegalitySection.tsx`, `DeckView.tsx`, `api.ts`, `i18n.ts` |
| 10 | **24 neue Tests**; Version 0.48.0 + CHANGELOG | — |

**`legal` ist `null`, wenn nichts geprüft wurde.** Ein unbekanntes Format ist kein Persilschein, und
eine HA-Vorlage muss das von `false` unterscheiden können. Gleiche Regel wie `bracket`.

## Akzeptanz

- [x] **Beide Premodern-Decks sauber**: 60 + 15, keine Verstöße.
- [x] Eine gebannte Karte wird **mit Status benannt** („X is banned in Modern").
- [x] **20× Rat Colony** erzeugt keinen Verstoß; **24× Mountain** auch nicht.
- [x] Vintage-`restricted` ist **kein eigener Verstoß**, sondern ein Kopienlimit von 1.
- [x] `unknown_legality` wird **gezählt und angezeigt**, nie als legal gewertet.
- [x] Der Nachtlauf meldet **eine** Störungskarte je Problem, nicht eine je Nacht — Test über drei
  Läufe, inklusive „anderes Problem kommt durch".
- [x] Migration 27 gegen die echte DB; Check über 24 Decks in **0,03 s**.
- [x] Backend **361 → 385 Tests grün**, Frontend **46 grün**, `tsc -b` sauber.
- [ ] **Ein echter Rotationsfall** — noch nicht eingetreten. Der Weg ist
  `POST /api/cards/backfill-scryfall?force=true`, danach läuft der Check von selbst.

## Ist-Protokoll (2026-09-15)

**Deck-Check über 24 Decks, 0,03 s, 6 mit Verstößen — und alle sechs sind echt:**

| Deck | Befund | Bewertung |
|---|---|---|
| 2 „You f\*\*\*\*\* with Squirrels" | 99 Karten statt 100 | ⚠️ **echter Fund** — eine Karte fehlt |
| 4 „Surf n Turf" | 99 Karten statt 100 | ⚠️ **echter Fund** |
| 8 „General Humphrey" | 89 Karten | Ordner „Work in Progress", stimmt |
| 14 „Entchantment DECK" | 2 Karten | Fragment, stimmt |
| 9, 10 | 112 / 132 Karten | Board-Daten von vor dem Re-Sync; nach Migration 27 erledigt |
| **61, 62 (Premodern)** | **keine** | 60 + 15, sauber |

Vor den drei Korrekturen oben waren es **11** Decks mit Verstößen — die fünf Differenz waren
Token (6, 7), Commander-Sideboards (20, 21) und das Board-Artefakt (10).

⚠️ **Deck 2 und 4 mit 99 Karten sind ein Fund für Max, keine Fehlfunktion.** Kein Token, ein
Commander, normale Kategorien: die Decks haben tatsächlich eine Karte zu wenig. Genau dafür ist
der Check da.

## Offen

- **Der Re-Sync von Migration 27** läuft beim ersten Sync nach dem Deploy (24 Decks, einige
  Minuten). Danach müssen Deck 9 und 10 auf 100 stehen.
- **Ein echter Rotations-/Ban-Fall** als End-to-End-Nachweis der Störungskarte.
- **Rotationsvorhersage** („rotiert in 3 Monaten") bleibt im Backlog: sie braucht eine gepflegte
  Set→Datum-Tabelle, und die veraltet, sobald WotC den Rhythmus ändert.
