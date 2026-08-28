# Sprint 05 — Power-Level (edhpowerlevel-Port)

**Status: ✅ umgesetzt in 0.39.0, deployed + über alle 22 Decks gerechnet am 2026-08-28.**
⚠️ **Ein Akzeptanzpunkt bleibt offen** — der Referenz-Diff gegen edhpowerlevel.com braucht einen
Browser; die Werkzeuge dafür sind gebaut, siehe „Offen" am Ende.

**Ziel:** Ein kontinuierlicher Power-Score je Deck (0–1000) + Power-Level (0–10) nach dem
extrahierten edhpowerlevel-Algorithmus (R2) — offline aus der eigenen `cards`-Tabelle,
**getrennt vom Bracket** (R3).

## Umgesetzt

| # | Paket | Datei |
|---|---|---|
| 1 | **Migration 24**: `decks.power_score` / `power_level` / `power_detail` / `power_computed_at` + `cards.layout` (nur für die MDFC-Regel; der Anreicherungs-Stempel wird geleert, damit `layout` nachkommt) | `database.py` |
| 2 | **`services/power_level.py`**: `de()`-Interpolator · `FACTORS` wörtlich · ~90 Karten-Overrides (Preis / Impact / commanderImpact / CMC) · Land-Faktor · Basics-Sockel · Tipping Point · Efficiency · Score · Level | neu |
| 3 | **Recompute** nach jedem Sync + `POST /decks/{id}/power/recompute` und `/decks/power/recompute-all` | `sync_service.py`, `routers/decks.py` |
| 4 | **Referenz-Link** `GET /decks/{id}/power/reference-url` im Format des dortigen Encoders — der einzige Weg, den Port gegen das Original zu prüfen | `power_level.py`, `routers/decks.py` |
| 5 | **UI**: Power-Panel in der DeckView (Score zuerst, Level als Übersetzung, Efficiency, Tipping Point, Impact je Manawert, die fünf tragenden Karten, der Vorbehalt) + `PWR`-Kachel in der Decks-Liste | `DeckPowerSection.tsx`, `Decks.tsx` |
| 6 | **HA**: `power_score` / `power_level` am Deck-Sensor (⚠️ nur für in 90 Tagen bespielte Decks) | `ha_metrics.py`, `ha_publisher.py` |
| 7 | Version 0.39.0 + CHANGELOG | — |

### Die fünf Stellen, die falsch aussehen und Absicht sind

Der Port ist nur so viel wert, wie er dem Original gleicht — deshalb hat **jede** dieser Fallen
einen Test, der bricht, sobald jemand sie „aufräumt":

1. **`de()` gewichtet den Dezil-Stop, nicht den Bruchteil.** Bei Gewicht 1.25 ist das Ergebnis
   also nicht sauber `1.25 × [0..10]`, sondern stückweise verschoben.
2. **`Ce` ist ungeklemmt.** Ein sehr billiges Deck bekommt Efficiency > 10, ein sehr teures
   negative Werte — die `efficiencyLimits` sind die Skala, keine Klammer.
3. **MDFC zählt als Land** und fällt **ganz** aus der Durchschnitts-CMC (weder 0 noch der Aufdruck).
4. **Basics bekommen ihren Sockel `2 × qty` NACH dem Land-Faktor**, nicht davor.
5. **`commanderImpact` gilt nur in der Kommandozone** — es ist keine Eigenschaft der Karte.

### Zwei Abweichungen vom Sprint-Text, beide begründet

**(a) `popCurve` bleibt bei der Fassung von 9/2024.** Der Sprint verlangte, den Deckel 27.000 auf
den heutigen Scryfall-Wert zu ziehen. Beim Umsetzen zeigte sich, dass das **keine Aktualisierung**
ist: die anderen zehn Stützstellen sind Dezilgrenzen **derselben** Verteilung von 2024. Nur den
obersten Wert zu heben ergibt eine Kurve, die weder das Original noch richtig neu kalibriert ist —
und verschiebt still jede Popularitätsbewertung. Eine echte Auffrischung heißt: alle elf
Stützstellen aus der heutigen Rangverteilung neu ableiten. Bis das jemand tut, bleibt die
2024er-Kurve stehen, **weil sie die einzige Fassung ist, gegen die sich ein Ergebnis prüfen lässt.**
Die Konstante `POP_CURVE_DERIVED` sagt das im Detail-JSON und in der UI.

**(b) `commanderImpact` matcht auf den Namensteil vor dem ersten Komma.** Die Quelle nennt die
Commander teilweise nur mit Rufnamen („Korvold", „Chulane"). Einen vollen Kartennamen zu ergänzen,
den die Quelle nicht hergibt, wäre geraten — der Präfix-Match ist genau so präzise wie die Quelle
und kann ohnehin nur zünden, wenn die Karte wirklich Commander ist.

## Akzeptanz

- [x] **Precon landet spürbar unter den getunten Decks:** Deck 13 „Turtle Power!" auf **404,6**
  (Platz 20 von 22), gegen 823,9 an der Spitze. Das 8-Karten-Fragment (Deck 14) fällt mit 63,4
  erwartungsgemäß aus der Reihe.
- [ ] **5 Referenzdecks ≤0,1 Power-Level Abweichung** — offen, siehe unten.

## Verifikation

- [x] 17 Tests in `tests/test_power_level.py`. Jeder Erwartungswert ist **von Hand aus der
  Spezifikation nachgerechnet** und die Rechnung steht im Kommentar — ein Test, der nur festhält,
  was der Code gerade ausgibt, würde bei einem Port nichts beweisen. Abgedeckt: `de()` an
  Stützstelle, im Dezil und am Deckel · der ungewichtete Bruchteil · Basics-Sockel · Land-Dämpfung ·
  Reserved-Dämpfung · MDFC · Free Spell · Commander-Multiplikator nur in der Kommandozone ·
  Preis-Override · ungeklemmte Efficiency · ein komplettes Zwei-Karten-Deck über die ganze Kette.
- [x] Backend **295/297 grün** (die 2 sind der Altbestand `test_static_files.py`), Frontend-Build grün.
- [x] Referenz-URL gegengeprüft: 1855 Zeichen für Deck 13, `[Commander]` erhalten, `~Z~`-Terminator
  gesetzt, Leerzeichen als `+`.

## Ist-Protokoll (2026-08-28) — alle 22 Decks

| ID | Deck | Score | Level | | ID | Deck | Score | Level |
|---|---|---:|---:|---|---|---|---:|---:|
| 10 | Sharknado (Altfassung) | 823,9 | 8,49 | | 8 | General Humphrey vom Hirschenschlag | 559,1 | 6,99 |
| 3 | They don't scurry… | 792,7 | 8,25 | | 21 | Allons-y! | 553,6 | 6,93 |
| 6 | Intergalactic planetary | 722,4 | 7,81 | | 11 | Squirreled Away - Upgrade | 530,1 | 6,67 |
| 2 | …Squirrels, Morty! | 704,1 | 7,72 | | 20 | Eternal Might for Varina | 525,7 | 6,62 |
| 53 | The guy who transforms… | 659,7 | 7,50 | | 17 | Counter Intelligence | 496,0 | 6,29 |
| 9 | No fox ever walks alone | 648,1 | 7,44 | | 18 | World Shaper | 474,2 | 6,05 |
| 1 | Sharknado | 646,0 | 7,43 | | 12 | Deeper Clue Sea | 466,7 | 5,93 |
| 5 | Emerald Hill Zone, Fast! | 643,4 | 7,42 | | 19 | Forth Eorlingas | 459,3 | 5,79 |
| 4 | Surf n Turf | 629,6 | 7,35 | | 13 | **Turtle Power! (Precon)** | **404,6** | **4,62** |
| 15 | Ms. Bumleflower unleashed | 587,0 | 7,13 | | 16 | Living Full Energy | 394,2 | 4,36 |
| 7 | Something is fishy here | 579,1 | 7,10 | | 14 | Entchantment DECK (8 Karten) | 63,4 | 0,25 |

**Score und Bracket sagen erwartungsgemäß Verschiedenes.** Deck 12 „Deeper Clue Sea" ist
**Bracket 4** (Game Changer + frühe Zwei-Karten-Combo) und liegt beim Score auf **Platz 18** — ein
günstiges Deck, das trotzdem auf der Stelle gewinnen kann. Umgekehrt ist Deck 6 „Intergalactic
planetary" Score-Dritter und nur **Bracket 3**: teure, beliebte Karten ohne Combo. Genau diese
Kreuzung ist der Grund, warum die zwei Werte getrennt geführt werden.

⚠️ **Der Backfill musste nach Migration 24 einmal komplett laufen** (7770 Printings, 218 s), weil
`cards.layout` neu ist und die Migration dafür alle Anreicherungs-Stempel geleert hat. Ohne diesen
Lauf hätte kein MDFC als Land gezählt.

## Offen

- **Der Referenz-Diff gegen edhpowerlevel.com.** Das Original rechnet **im Browser**; von hier aus
  gibt es keinen Weg, es auszuführen. Gebaut ist alles dafür: `GET /decks/{id}/power/reference-url`
  und der Knopf „Check against edhpowerlevel.com ↗" im Power-Panel erzeugen den Link, der genau
  diese Liste dort einwirft. **Zu tun bleibt:** fünf Decks öffnen, Score und Level notieren, die
  Differenz hier eintragen. Erwartete Restabweichung auch bei korrektem Port: unsere USD-Preise
  kommen von Archidekt, die des Originals von Scryfall.
- **Eine echte `popCurve`-Neuableitung** (alle elf Stützstellen aus der heutigen Rangverteilung) —
  bewusst nicht als Einzelwert-Änderung gemacht, Begründung oben.
- **HA sieht den Score nur für bespielte Decks**, wie beim Bracket — gehört zu Sprint 07.
