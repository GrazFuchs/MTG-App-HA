# Sprint 04 — Bracket: pflegbar + berechnet

**Status: ✅ umgesetzt in 0.38.0–0.38.2, deployed + über alle 22 Decks verifiziert am 2026-08-28.**
Ist-Protokoll am Ende.

**Ziel (Entscheidung Auftraggeber):** Das WotC-Bracket-System bleibt und wird **in der App
pflegbar** — plus eine lokal **berechnete** Einstufung nach den offiziellen Regeln, mit
Begründung.

**Warum (Befunde):** B1, B26, B24/B28, B27, R5 in [review-befunde.md](review-befunde.md).

## Feld-Semantik — vier Werte, klar getrennt

| Feld | Quelle | Rolle |
|---|---|---|
| `bracket` | Archidekt-Import (`edhBracket`) | reiner Spiegel; auf **allen** Decks leer |
| `user_bracket` | Hand | **gewinnt immer** |
| `computed_bracket` (neu) | lokale Berechnung | Vorschlag **mit Begründung** |
| `spellbook_bracket_tag` (neu) | Commander Spellbook | ⚠️ **andere Skala**, nur Vergleichslabel |

Anzeigekette `user_bracket → computed_bracket → bracket` steckt in `effective_bracket()` und treibt
Badge, Deck-Liste, Filter und die HA-Attribute.

## Vor dem Code: zwei Dinge belegt statt geraten

**1. `bracketTag` ist NICHT die WotC-Skala.** Der Sprint verlangte, das Mapping über `/schema/`
zu klären. Ergebnis: `BracketTagEnum = R·S·P·O·C·E·B` = *Ruthless · Spicy · Powerful · Oddball ·
Core · Exhibition · Banned*. Zwei Namen ähneln WotC (Exhibition, Core), die anderen fünf haben
dort keine Entsprechung, und **eine Abbildung ist nirgends dokumentiert**. Konsequenz: Spellbooks
Urteil wird als **Label neben** unserer Zahl geführt, nie als die Zahl.

**2. `/estimate-bracket` klassifiziert je Karte** — `gameChanger`, `massLandDenial`, `extraTurn`,
`banned` — und je Combo `definitelyTwoCard`, `speed`, `lock`, `skipTurns`. Damit war die
Kartenliste aus R2 (33 MLD-Namen aus einem Bundle von 2024) **nicht nötig**: eine abgeschriebene
Liste ist genau die Stelle, die zuerst veraltet — dieselbe Lehre wie „Game Changers nicht
abschreiben, sondern abfragen" (R5). Gemessen an Deck 2: Death Cloud korrekt als MLD erkannt.
⚠️ Preis: Spellbook kennt nur Karten aus der eigenen Combo-Datenbank (**49 von 88** bei Deck 2),
deshalb bleibt Unbekanntes **NULL = unklassifiziert**, nicht „sauber", und die Zahl steht im Detail.

## Umgesetzt

| # | Paket | Datei |
|---|---|---|
| 1 | **Migration 23**: `decks.computed_bracket` / `_detail` / `_at` / `spellbook_bracket_tag`, `cards.mass_land_denial` / `extra_turn`, `deck_combos.mana_value_needed` | `database.py` |
| 2 | **`services/bracket.py`**: Game Changers · Zwei-Karten-Infinites (früh/spät) · MLD · Extra Turns; Ergebnis = höchste Untergrenze, `detail`-JSON nennt **welche** Karten jede Grenze ausgelöst haben | neu |
| 3 | **Klassifikation cachen**: `/estimate-bracket` je Deck im Combo-Sync, schreibt `mass_land_denial`/`extra_turn` je Karte + Spellbooks Deck-Tag. Eigener `try` — ein Ausfall dort darf die gerade gespeicherten Combos nicht kosten | `clients/spellbook.py`, `services/combo_sync.py` |
| 4 | **Recompute**: nach Combo-Sync je Deck, nach jedem Voll-Sync für alle; `POST /decks/{id}/bracket/recompute` + `POST /decks/bracket/recompute-all` | `services/sync_service.py`, `routers/decks.py` |
| 5 | **UI**: Badge zeigt den effektiven Bracket mit Quelle im Tooltip, 1–5-Picker, „—" zum Zurückfallen auf die Rechnung, und ein **„why?"** mit den Regeln, den auslösenden Karten, dem Abdeckungsvorbehalt und Spellbooks Label | `UserBracketBadge.tsx` |
| 6 | **Decks-Liste**: Kachel und Filter auf den effektiven Bracket; `BR.n?` markiert einen gerechneten gegen einen gesetzten Wert | `pages/Decks.tsx` |
| 7 | **HA**: `bracket` + `bracket_source` als Attribute am Deck-Sensor ⚠️ nur für Decks, die in 90 Tagen gespielt wurden — sonst existiert der Sensor nicht | `ha_metrics.py`, `ha_publisher.py` |
| 8 | Version 0.38.0–0.38.2 + CHANGELOG | — |

### 🐞 Nebenbefund, verifiziert: der Compare-Einstieg war unsichtbar

Der Knopf „⌬ Compare Decks" stand **innerhalb** von `{availableBrackets.length > 0 && …}`, und
`availableBrackets` kam aus `d.bracket > 0` — was auf jedem Deck 0 ist. Der einzige Einstieg zur
Deck-Vergleichsseite war damit nie erreichbar. Der ungeprüfte Audit-Hinweis ist bestätigt und
behoben: der Knopf steht jetzt eigenständig.

### Die drei Zahlen, die Urteile sind — und woran sie hängen

Die Bracket-Regeln sind Prosa. Drei Schwellen mussten gesetzt werden; alle drei sind **benannte
Konstanten** mit ihrer Begründung im Code:

| Konstante | Wert | Status |
|---|---|---|
| `GAME_CHANGERS_ALLOWED_AT_B3` | 3 | **steht so in den Regeln** |
| `EARLY_COMBO_MANA_CEILING` | 8 | **Urteil.** Kiki-Jiki (5) + Deceiver Exarch (3) = 8 gilt überall als frühe Combo, Mikaeus (6) + Triskelion (6) = 12 nicht |
| `GENERIC_INFINITE_MAX_CARDS` | 3 | **Urteil, an zwei echten Decks kalibriert** — siehe unten |

**Tutoren werden bewusst nicht gezählt** — WotC hat die Limits im Oktober 2025 gestrichen (R2/R5).

**Die Rechnung antwortet nur 2, 3 oder 4 — und sagt das im `detail`.** Bracket 1 (Exhibition) und
5 (cEDH) beschreiben *Absicht*: ein Deck um einen Gag herum, ein Deck für ein Turnier. Nichts an
einer Deckliste trennt sie von ihren Nachbarn. Sie zu behaupten wäre erfunden — dafür ist
`user_bracket` da.

## Akzeptanz

- [x] **Deck 5 „Emerald Hill Zone, Fast!" → Bracket 4**, Begründung: `two_card_combo_early` mit
  *Kiki-Jiki, Mirror Breaker + Deceiver Exarch* und *+ Sea-Dasher Octopus*; *+ Restoration Angel*
  (5+4=9) landet korrekt als `two_card_combo_late`.
- [x] **Deck 13 „Turtle Power!" (Precon) → Bracket 2**, keine Regel ausgelöst.
- [x] **Deck 2 → Bracket 4**, Begründung nennt *Chatterfang + Pitiless Plunderer* **und**
  *Death Cloud* (MLD) — genau die zwei aus B28.
- [x] **Ein gesetzter `user_bracket` gewinnt und übersteht den Sync.** Test
  `test_a_hand_set_bracket_wins_over_the_computed_one`; die Sync-Festigkeit ist strukturell —
  `sync_deck`s Deck-Upsert kommt in 0 Zeilen an `user_bracket` vorbei (gegengeprüft).

## Ist-Protokoll (2026-08-28) — alle 22 Decks

Berechneter Bracket neben Spellbooks unabhängigem Urteil, wie im Sprint verlangt:

| ID | Deck | berechnet | Spellbook | ausgelöste Regeln | unklassifiziert |
|---|---|---:|---|---|---:|
| 2 | You f\*\*\*\*\* with Squirrels, Morty! | **4** | Ruthless | `two_card_combo_early · mass_land_denial` | 40/89 |
| 3 | They don't scurry when something bigge | **4** | Ruthless | `mass_land_denial` | 32/72 |
| 5 | Emerald Hill Zone, Fast! | **4** | Ruthless | `two_card_combo_early · two_card_combo_late` | 53/87 |
| 7 | Something is fishy here | **4** | Ruthless | `mass_land_denial` | 66/94 |
| 9 | No fox ever walks alone | **4** | Powerful | `game_changers · two_card_combo_early` | 52/98 |
| 10 | Sharknado | **4** | Ruthless | `game_changers · two_card_combo_early` | 77/128 |
| 12 | Deeper Clue Sea | **4** | Spicy | `game_changers · two_card_combo_early` | 52/89 |
| 18 | World Shaper - Edge of Eternities | **4** | Spicy | `two_card_combo_early` | 41/87 |
| 21 | Allons-y! | **4** | Ruthless | `game_changers · two_card_combo_late · mass_land_denial` | 65/100 |
| 4 | Surf n Turf | **3** | Ruthless | `infinite_combo` | 50/96 |
| 6 | Intergalactic planetary | **3** | Powerful | `game_changers` | 53/102 |
| 8 | General Humphrey vom Hirschenschlag | **3** | Powerful | `game_changers` | 37/73 |
| 15 | Ms. Bumleflower unleashed | **3** | Spicy | `two_card_combo_late` | 59/94 |
| 16 | Living Full Energy | **3** | Ruthless | `game_changers · two_card_combo_late` | 58/88 |
| 20 | Eternal Might for Varina | **3** | Powerful | `game_changers` | 54/93 |
| 1 | Sharknado | **2** | Exhibition | `—` | 61/98 |
| 11 | Squirreled Away - Upgrade | **2** | Exhibition | `—` | 36/85 |
| 13 | Turtle Power! (Precon) | **2** | Exhibition | `—` | 60/93 |
| 14 | Entchantment DECK | **2** | Exhibition | `—` | 4/8 |
| 17 | Counter Intelligence - Edge of Etern. | **2** | Exhibition | `—` | 42/94 |
| 19 | Forth Eorlingas | **2** | Exhibition | `—` | 60/87 |
| 53 | The guy who transforms all the cute bu | **2** | Exhibition | `—` | 69/111 |

**Verteilung: 7× Bracket 2 · 6× Bracket 3 · 9× Bracket 4.** Vorher: 22× „0".

**Die beiden Skalen laufen in dieselbe Richtung, ohne dass eine aus der anderen abgeleitet wäre:**
alle 7 Decks, die Spellbook „Exhibition" nennt, rechnen sich zu 2; kein „Ruthless"- oder
„Spicy"-Deck landet unter 3. Das ist die stärkste verfügbare Gegenprobe — zwei unabhängige
Klassifikationen auf denselben 22 Decklisten.

### Zwei Korrekturen, die erst der Lauf über echte Decks gefunden hat

**0.38.1 — ein Deck, das auf der Stelle gewinnt, war „Core".** Die Regeln nennen *Zwei-Karten*-Combos,
weil das die Grenze zwischen 3 und 4 ist. Deck 4 „Surf n Turf" hält **zwei vollständige
Drei-Karten-Infinites** und löste damit gar nichts aus — Bracket 2, während Spellbook dieselbe
Liste unabhängig „Ruthless" nennt. Seither hebt ein Infinite überhaupt auf 3.

**0.38.2 — und dann hob dieselbe Regel zu viel.** Deck 11 „Squirreled Away" hat als einzige
vollständige Combo eine **Vier-Karten**-Schleife für unendlich Food-Token; die gewinnt nichts, und
Spellbook nennt das Deck „Exhibition". Die generische Regel ist deshalb auf **drei Teile**
begrenzt. Beide Fälle stehen als Beleg im Kommentar der Konstante — die Grenze ist an genau diesen
zwei Decks kalibriert und nicht aus einer Quelle zitiert.

⚠️ **Eigener Messfehler, vermerkt:** die erste Auswertung fasste 20 statt 22 Decks, weil zwei große
Decks in einen 30-s-Timeout liefen und mein Sammelskript die leeren Antworten **still übersprang**.
Die Endtabelle bricht jetzt ab, wenn nicht alle 22 Zeilen vorliegen.

### Offen / bewusst nicht gemacht

- **Der HA-Bracket erreicht nur bespielte Decks** — das Deck-Sensor-Objekt existiert nur für Decks
  mit einer Partie in 90 Tagen, aktuell **eines**. Ein eigener Aggregatsensor „Brackets aller
  Decks" wäre der nächste Schritt, gehört aber zu Sprint 07.
- **Die Abdeckungslücke bleibt bestehen:** 32–77 Karten je Deck sind bei Spellbook unklassifiziert.
  MLD und Extra Turns können dadurch untererkannt sein; der Oracle-Text-Fallback fängt nur die
  klarsten Formulierungen. Die Zahl steht in jedem `detail` und im „why?"-Popup.
- **`speed` je Combo** (Spellbook, undokumentierte Ganzzahl) wird **nicht** benutzt — früh/spät
  rechnen wir selbst aus `manaValueNeeded` + CMC, weil eine undokumentierte Skala zu raten genau
  das ist, was der Sprint bei `bracketTag` untersagt hat.
