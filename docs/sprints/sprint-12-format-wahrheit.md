# Sprint 12 — Format-Wahrheit

**Status: ✅ umgesetzt in 0.47.0 am 2026-09-15, gegen die echte DB verifiziert.**
Deploy-Protokoll am Ende.

**Ziel:** Ein Deck, das kein Commander ist, wird korrekt beschrieben — kein Bracket, kein
Power-Score, Boards getrennt, Format sichtbar — und die 22 Commander-Decks ändern sich nicht.

**Warum:** Befunde 1–9, 14–17 in [plan-60-karten-decks.md](plan-60-karten-decks.md).

## Der Anlass war schon da, bevor der Sprint begann

Max hat am **2026-09-12**, am Tag der Planübergabe, zwei Premodern-Decks auf Archidekt angelegt
(„The Rock" und „Sligh", je 60 + 15). Der nächtliche Sync hat sie am 13.09. um 01:14 geholt —
**kein Codepfad hat sie abgelehnt**, die Auto-Discovery filtert nicht nach Format. Am Morgen
standen beide mit **Bracket 2**, einem edhpowerlevel-Score (365,1 / 314,9) und einem
Spellbook-Label `E` in der Datenbank.

Damit war die Kernannahme des Plans nicht mehr Theorie, sondern ein Befund: **kein Feature fehlt,
vier Analysen behaupten Dinge, die für das Format nicht definiert sind.**

## Drei Befunde aus der Vorbereitung, die den Bau geändert haben

### 1. Die Formattabelle war zwei Jahre lang falsch

`clients/archidekt.py` bildete Archidekts `deckFormat`-Nummer auf einen Namen ab. Die Tabelle war
aus dem Gedächtnis geschrieben, als nur Commander zählte, und **ab Nummer 7 um genau eins
verschoben**. Gemessen am 2026-09-15 über Archidekts eigene `/formats/<slug>`-Seiten (erstes Deck
der Seite holen, `deckFormat` aus `/api/decks/<id>/small/` lesen):

| Nummer | tatsächlich | wir sagten |
|---:|---|---|
| 1–6 | Standard · Modern · Commander · Legacy · Vintage · Pauper | ✓ richtig |
| 8 | Frontier | Future Standard |
| 13 · 14 · 15 | Brawl · Oathbreaker · Pioneer | Oathbreaker · Pioneer · Historic |
| 16 · 18 · 21 | Historic · Alchemy · Gladiator | Pauper Commander · Explorer · Premodern |
| 22 · 23 · 24 | **Premodern** · Predh · Timeless | **Predh** · Timeless · Standard Brawl |

**Warum es nie aufgefallen ist:** Commander ist in beiden Fassungen die 3, und alle 22 Decks waren
Commander. Dasselbe Muster wie beim Farbfehler in 0.34.0 — Weiß, Schwarz und Rot enthalten je
genau einen Farbbuchstaben und funktionierten aus Zufall.

**Konsequenz im Bau:** 16 Nummern sind gemessen. Die neun unbestätigten (7, 9–12, 17, 19, 20, 25)
liefern **`Unknown`**, nicht den Namen, den das Versatzmuster nahelegt. Das Muster stimmt fast
sicher — und genau deshalb darf es nicht als Tatsache dastehen: ein plausibler falscher Name ist
schlimmer als eine sichtbare Lücke, weil niemand ihn je wieder ansieht. Archidekts Rohnummer wird
seit 0.47.0 in `decks.archidekt_format_id` mitgespeichert, damit die nächste Korrektur ein
Nachschlagen ist und kein Voll-Sync.

### 2. `includedInDeck` reicht nicht — gemessen, nicht vermutet

Der Plan hatte offengelassen, ob Archidekts deck-weites `includedInDeck` das Sideboard erkennt.
Gemessen an Deck 26328851:

```
Maybeboard   includedInDeck: false
Sideboard    includedInDeck: TRUE     ← Archidekt zählt es zum Deck
Land         includedInDeck: true
```

Das Flag trennt also **nicht** Main von Side. Die Regel ist deshalb zweistufig: `includedInDeck ==
false` → `maybe`, sonst Name `Sideboard` → `side`, sonst `main`. Genau **eine** Namensregel, für
den einen Namen, den Archidekt selbst definiert — alles andere (`Slot In`, `Backlog`,
`Considering`) entscheidet der Besitzer über das Flag, und das ist besser als jede Liste, die wir
pflegen könnten.

**Gegenprobe über die Kartenzahlen:** rechnet man die Kategorien mit `includedInDeck: false`
heraus, landen **17 von 24 Decks exakt auf ihrer Sollgröße** (Deck 3: 115 − 15 = 100 · Deck 10:
132 − 32 = 100 · Deck 53: 125 − 25 = 100). Ohne die Herausrechnung wären es 11.

### 3. Karten verschmelzen über Board-Grenzen — ein echter Datenverlust

Deck 61, live gegen Archidekt verglichen:

| | Archidekt | unsere DB |
|---|---|---|
| Ravenous Baloth | 3× Lifegain **+** 1× Sideboard | 4× Sideboard |

`UNIQUE(deck_id, card_id, modifier)` sieht beide Zeilen als denselben Eintrag: die Mengen addieren
sich, die zuletzt geschriebene Kategorie gewinnt. Das Deck liest sich dadurch als **57 Hauptkarten
statt 60**. Genau die drei, die in der Größenrechnung oben fehlten.

⚠️ `Genesis` steht im selben Deck zweimal und ist *nicht* verschmolzen — dort sind es zwei
verschiedene Printings, also zwei `card_id`. Der Fehler trifft nur dasselbe Printing in zwei Piles.

## Umgesetzt

| # | Paket | Datei(en) |
|---|---|---|
| 1 | **`services/formats.py`** — 16 gemessene Archidekt-Nummern, 25 Format-Specs, Gates (`bracket_applies` · `power_applies` · `has_commander` · `legality_key` · `deck_rules`), `check_shape` als Gegenprobe | neu |
| 2 | **Migration 26** — `deck_cards.board`, UNIQUE um `board` erweitert (Tabellen-Neubau), `decks.archidekt_format_id`, Korrektur der falschen Formatnamen + Markierung für Voll-Re-Sync | `database.py` |
| 3 | **Parser** liest Archidekts deck-weite Kategorien (`deck_boards`, `board_of`), liefert `board` und `archidekt_format_id`; die alte Formattabelle ist raus | `clients/archidekt.py` |
| 4 | **Gates** in Bracket, Power und Combo-Klassifikation; gespeicherte Werte werden beim Nicht-Zutreffen **genullt**, Spellbook-Label mit | `services/bracket.py`, `power_level.py`, `combo_sync.py` |
| 5 | `card_count` = Hauptdeck, dazu `sideboard_count`/`maybeboard_count` und `format_rules` an jedem Deck | `services/queries.py`, `models/schemas.py`, `routers/decks.py` |
| 6 | **Frontend**: Format-Filter, Kachelfuß „60 + 15", Hero fällt auf `featured_image` zurück, Kopfzeile format-bewusst, Bracket-/Power-Sektion nur wo anwendbar, `board` statt Namensliste, Mismatch-Hinweis. i18n EN + DE | `Decks.tsx`, `DeckView.tsx`, `api.ts`, `i18n.ts` |
| 7 | **MCP**: Prompt verzweigt über `format_rules`, drei Tools dokumentieren `not_applicable`, `analyze_deck` zählt nur das Hauptdeck, `suggest_bracket_safe_upgrades` sagt `bracket_checked` | `mcp_server.py` |
| 8 | **HA**: Attribut `format` am Deck-Sensor, `bracket`/`power_*` sind `null` statt Zahl | `ha_metrics.py`, `ha_publisher.py` |
| 9 | **26 neue Tests**, `insert_deck` mit Format-Default | `tests/test_formats.py`, `tests/_helpers.py` |
| 10 | Version 0.47.0 + CHANGELOG | — |

### Zwei Entscheidungen, die bewusst gegen den ersten Reflex gingen

**Der `board`-Filter bleibt aus dem Power-Score draußen.** Er ist seit dieser Version eine Zeile
entfernt und gehört dorthin — Deck 10 rechnet 824,7 mit 32 Backlog-Karten, die nicht im Deck sind.
Aber Gate und Arithmetik in derselben Release zu ändern macht den Vorher/Nachher-Vergleich wertlos,
und dieser Vergleich ist der **einzige Beleg**, dass die 22 Commander-Decks unangetastet blieben.
Sprint 13 zieht ihn nach, mit eigener Messung.

**`user_bracket` gewinnt hier ausnahmsweise nicht.** Sonst schlägt ein handgesetzter Bracket alles.
Bei einem Format ohne Bracket ist eine gesetzte 3 aber kein Urteil, sondern ein Rest aus der Zeit,
als das Format falsch gelesen wurde. Die Anzeige unterdrückt sie; der Wert bleibt in der DB stehen.

## Akzeptanz

- [x] **Beide Premodern-Decks**: `computed_bracket NULL`, `power_score NULL`,
  `spellbook_bracket_tag ''`. Kachel ohne BR/PWR, Deck-Seite ohne Bracket- und Power-Sektion.
- [x] **Die 22 Commander-Decks byteidentisch** — Bracket und Power-Score unverändert, gemessen
  Deck für Deck gegen die Ist-Messung.
- [x] **Bracket-Verteilung 7× 2 · 6× 3 · 9× 4** — dieselbe Tabelle wie Sprint 04.
- [x] Dieselbe Karte in Main und Side bleibt **zwei Zeilen** (Test + neues UNIQUE).
- [x] **Migration 26 gegen die echte 352-MB-DB**: 0,1 s, 2005 Zeilen und 2347 Karten unverändert,
  idempotent (zweiter Lauf ändert nichts).
- [x] Format-Wechsel nullt Bracket, Detail, Power und Spellbook-Label (Test).
- [x] Backend **360 Tests grün** (334 + 26 neue), Frontend **46 grün**, `tsc -b` sauber.
- [ ] **MCP-Prompt am lebenden Assistenten** — der Prompt verzweigt jetzt über `format_rules`;
  ein Trockenlauf mit Claude gegen ein Premodern-Deck steht aus.

## Ist-Protokoll (2026-09-15)

| Schritt | Ergebnis |
|---|---|
| 0.46.2 committen + deployen | `state: started`, `version 0.46.2`, `healthz` 200 · ⚠️ der erste `healthz` kam als `000`, weil der Container gerade neu startete — nicht als Crash-Loop lesen (Memory-Rezept) |
| Ist-Messung | DB-Kopie 352 MB über den Backup-Endpunkt; **24 Decks, nicht 22** — der erste Befund |
| Formattabelle gemessen | 16 Nummern über `/formats/<slug>` + `/small/`; Archidekt blockt den direkten Seitenabruf, der `r.jina.ai`-Umweg liefert sie (dasselbe Rezept wie beim Anycubic-Wiki) |
| Kategorie-Flags gemessen | `Sideboard` = `includedInDeck: true` — die offene Frage des Plans, gegen die Vermutung entschieden |
| Migration gegen die echte DB | 0,1 s · 2005/2005 Zeilen · 2347/2347 Karten · idempotent |
| Gegenprobe Bracket + Power | 22 unverändert, 2 auf `null` |

⚠️ **Die zwei Premodern-Decks sind für einen Voll-Re-Sync markiert** (`updated_at = NULL`). Bis der
nächtliche Sync um 03:00 läuft, trägt Deck 61 weiter 57 statt 60 Hauptkarten — die verschmolzenen
Zeilen kann die Migration nicht auftrennen, nur die Quelle. **Danach prüfen:** Deck 61 muss 60 + 15
zeigen, und beide Decks brauchen ein `archidekt_format_id` (22).

## Offen

- **Der Re-Sync-Nachweis** (siehe oben) — braucht den nächtlichen Lauf.
- **Der MCP-Trockenlauf** gegen ein Nicht-Commander-Deck.
- **Nummer 7 und die acht anderen unbestätigten** bleiben `Unknown`, bis jemand ein Deck dieses
  Formats anlegt oder Archidekt eine Formatliste herausgibt. Der Such-Endpunkt
  `/api/decks/cards/?formats=` existiert nicht mehr (`Unknown API route`).
- **Der `board`-Filter im Power-Score und im Deckbedarf** — Sprint 13.
