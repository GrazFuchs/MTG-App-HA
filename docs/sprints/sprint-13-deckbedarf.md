# Sprint 13 — Was ein Deck wirklich bindet

**Status: ✅ umgesetzt in 0.49.0 am 2026-09-15, gegen die echte DB gemessen.**
Ist-Protokoll am Ende.

**Ziel:** Eine Frage — „wieviele Kopien brauchen meine Decks?" — hat **eine** Antwort.

**Warum:** Sie wurde an **sieben** Stellen gestellt, jede mit eigenem SQL, und jede zählte jede
Zeile in `deck_cards`: Maybeboard, Token, und die vier Decks in „Disassembled" und „Older
Versions". Bei Commander verzählt man sich damit um eine Karte hier und da. **Bei Playsets um vier
auf einmal** — und Überschuss, Verkaufsberater und Einkaufsliste stehen alle darauf.

**Braucht:** Sprint 12 (`board`), Sprint 14 (`token_exclusion_sql`).

## Arbeitspakete

| # | Was | Ergebnis |
|---|---|---|
| 1 | **Eine VIEW statt sieben Abfragen** — `deck_demand` | 7 Konsumenten umgestellt |
| 2 | **Wächter-Test**, der eine achte Abfrage gegen `deck_cards` findet | `test_no_demand_query_reads_deck_cards_directly` |
| 3 | **Zwei Spalten**: `binds_copies` (abgeleitet) / `binds_copies_override` (Entscheidung) | Migration 28 |
| 4 | **Board-Filter in den Power-Score** — in Sprint 12 bewusst zurückgehalten | 11 von 22 Decks bewegt |
| 5 | **Completeness trennt zwei Fragen** — kaufen vs. umräumen | `blocked_by_other_decks` |
| 6 | **Frontend**: Toggle, Kachel-Marker, Spaltensemantik | 3 Stellen |

## Warum eine VIEW und kein gemeinsamer SQL-String

Ein geteilter String hätte dasselbe geleistet und wäre der naheliegende Weg gewesen. Die VIEW ist
der bessere, weil ein Aufrufer sie **benennen muss**, statt sich an eine Regel zu erinnern. Dazu
der Wächter-Test: er scannt die Quellen nach `deck_usage AS`, `as in_decks` und Verwandten und
schlägt an, wenn im Umfeld `deck_cards` statt `deck_demand` steht.

Gegenprobe gemacht: mit einer zurückgedrehten `queries.py` schlägt er an, mit der aktuellen nicht.

## Zwei Spalten, weil ein Sync keine Entscheidung zurücknehmen darf

Der erste Entwurf hatte **eine** Spalte mit `DEFAULT 1`. Damit war „noch niemand hat entschieden"
nicht von „jemand hat ja gesagt" zu unterscheiden — und `binds_copies IS NULL` war deshalb **nie
wahr**. Jetzt:

* `binds_copies` — aus dem Archidekt-Ordner abgeleitet, bei **jedem** Sync neu geschrieben.
* `binds_copies_override` — was jemand auf der Deckseite gesetzt hat. Ein Sync fasst sie nie an.

Exakt das Paar, das `computed_bracket` und `user_bracket` schon sind, aus exakt demselben Grund.
Die Ableitung heißt seit diesem Sprint `apply_binding_from_folder()` statt elf Zeilen mitten in
einer 600-Zeilen-Sync-Funktion zu sein — **eine Regel, die man nicht aufrufen kann, kann man auch
nicht testen.**

Gelesen wird die Kombination an **einer** Stelle (`binds_effective()`), und die VIEW trägt dieselbe
`COALESCE`. Deckliste und Deckseite fragen denselben Helfer — beim Bracket sind genau diese beiden
einen ganzen Deploy lang auseinandergelaufen (0.47.0 → 0.47.1).

## „Habe ich genug?" und „ist genug davon frei?" sind zwei Fragen

Die Completeness-Prüfung hat sie vermengt. Eine Karte, von der man vier besitzt, **fehlt** nicht,
weil alle vier in einem anderen Deck stecken — verfügbar ist sie trotzdem nicht.

* `missing_cards` behält seine Bedeutung: die **Einkaufsliste**.
* `blocked_by_other_decks` ist neu: die **Kiste, die man aufmacht**.

Jede fehlende Zeile sagt zusätzlich, wieviele Kopien andere Decks halten. Ohne das schickt die
Liste einen los, eine Karte zu kaufen, die eine Deckbox weiter liegt.

Aufgefallen ist die Lücke an einem `KeyError` im Test: eine Karte, die man 4× besitzt und 4×
braucht, ist nicht „missing", also hatte `bound_elsewhere` gar keinen Ort, an dem es erscheinen
konnte. Ein Testfehler, der auf eine echte Bedeutungslücke zeigte.

---

# Ist-Protokoll — 2026-09-15

Gemessen gegen den echten Bestand: **352 MB, 24 Decks, 8580 Karten**, Schema 27 → 28.
Migration **0,06 s**, zweiter Lauf idempotent (0,02 s, gleiche Zeilenzahl).

## Bedarf

| | vorher | nachher | Δ |
|---|---|---|---|
| Bedarf gesamt | 2349 Karten / 1320 Namen | 1797 / 1079 | **−552** |
| „mehr in Decks als besessen" | 268 Namen / 360 Karten | 95 / 173 | **−173 Namen** |
| Überschuss | 5172 Namen / 8578 Karten | 5376 / 8943 | **+365 Karten** |

Die −552 gehen exakt auf: **Maybeboard 152 · Token in Main/Side 0 · nicht-bindende Decks 400.**
(2349 − 152 − 0 − 400 = 1797.)

Die Token-Zeile ist eine **0**, und das ist keine Enttäuschung: die vier Token-Zeilen liegen im
Maybeboard und fallen schon über das Board heraus. Der Filter bleibt trotzdem nötig — vor
Migration 26 lagen sie im Main, und genau daran ist der erste Legalitätslauf gescheitert.

Die 173 Namen, die aufgehört haben, überbucht auszusehen, **waren nie überbucht**. Sie waren ein
Artefakt des mitgezählten Maybeboards.

## Die drei Verkaufszahlen — sie steigen, und das ist die Korrektur

Vorher = Live-Sensoren des laufenden Add-ons, nachher = neuer Code gegen die migrierte DB.

| Sensor | vorher | nachher | Δ |
|---|---|---|---|
| `sell_potential_eur` | 1953,21 € | 2075,50 € | +122,29 |
| `duplicates_surplus_cards` | 2878 | 3049 | +171 |
| `duplicates_surplus_value_eur` | 1161,67 € | 1293,37 € | +131,70 |
| `unlisted_value_eur` | 1046,22 € | 1177,54 € | +131,32 |
| `sell_candidates` | 200 | 200 | 0 (gekappt) |

Karten im Maybeboard, in zerlegten Decks und Token wurden aus dem Überschuss herausgehalten, als
bräuchte ein Deck sie. **Das ist die W5-Lehre aus Sprint 06 ein zweites Mal:** die Zahl ändert
sich, und die Änderung ist die Korrektur, kein Rückfall.

`mtg_verkauf_wochenreport` schwellt auf `unlisted_value_eur > 50` — vorher darüber, nachher
darüber. Kein Verhaltenssprung, nur eine ehrlichere Zahl.

## Power-Score: 11 von 22 Decks, alle nach unten

Der Board-Filter erreicht `power_level.py` (in Sprint 12 bewusst zurückgehalten, damit sich das
Format-Gate allein messen ließ).

| Deck | alt | neu | Δ |
|---|---|---|---|
| 8 General Humphrey… [WIP] | 561,78 | 212,20 | −349,58 |
| 10 Sharknado [Older Versions] | 826,81 | 607,56 | −219,25 |
| 3 They don't scurry… | 791,77 | 654,25 | −137,52 |
| 53 The guy who transforms… | 659,90 | 573,46 | −86,44 |
| 6 Intergalactic planetary | 723,55 | 648,92 | −74,63 |
| 14 Entchantment DECK [WIP] | 58,31 | 15,36 | −42,95 |
| 9 No fox ever walks alone | 654,45 | 629,14 | −25,31 |
| 21 Allons-y! | 553,70 | 537,00 | −16,70 |
| 20 Eternal Might for Varina | 527,96 | 518,81 | −9,15 |
| 1 Sharknado | 647,03 | 639,04 | −7,99 |
| 7 Something is fishy here | 576,59 | 571,16 | −5,43 |
| 61 The Rock / 62 Sligh | — | — | Format ohne Power-Score |

**Deck 10 war bis heute das höchstbewertete Deck der Sammlung** — auf der Kraft von 32 Karten, die
nicht darin sind. Deck 8 hat 43 Main-Karten, sein alter Score war fast reines Backlog.

## Nicht-bindende Decks: 4 aus 2 Ordnern

| Deck | Ordner | Karten |
|---|---|---|
| 10 Sharknado | Older Versions | 132 |
| 11 Squirreled Away – Upgrade | Disassembled | 100 |
| 12 Deeper Clue Sea | Disassembled | 100 |
| 17 Counter Intelligence | Disassembled | 100 |

## Nebenbefunde aus derselben Messung

**Sprint 12 ist live belegt:** Deck 61 „The Rock" und 62 „Sligh" lesen **60 + 15**. Die übrigen 22
sind Commander, davon 19 auf genau 100.

**Die früher notierten „Decks 2 und 4 mit 99 Karten" waren ein Artefakt vor dem Board-Fix** — beide
lesen jetzt 100, ebenso 9 und 10. Der echte Fall ist ein anderer (siehe unten).

**Drei Legalitätsbefunde von 24 Decks** (Sprint-14-Check, erster vollständiger Lauf nach dem
Re-Sync):

| Deck | Ordner | Main | Befund |
|---|---|---|---|
| 6 Intergalactic planetary | **Maxi** | 98 | **Echter Befund** — aktives Deck, 2 Karten fehlen |
| 8 General Humphrey… | Work in Progress | 43 | Entwurf |
| 14 Entchantment DECK | Work in Progress | 2 | Entwurf |

## Offen — eine Entscheidung, keine Arbeit

**Soll „Work in Progress" den Legalitäts-PUSH unterdrücken?** Ein Deck, das gerade gebaut wird, ist
nicht *illegal* — die Frage gilt für es noch gar nicht, und das ist genau die Hausregel „nicht
anwendbar heißt NULL plus Begründung, nie eine Zahl". Zwei der drei Befunde sind Entwürfe, und ein
Prüfer, der bei jeder Änderung an einem 2-Karten-Entwurf pusht, wird abgeschaltet statt repariert
(die Lehre aus Sprint 14).

Bewusst **nicht** eigenmächtig gebaut: `non_binding_folders` regelt den *Bedarf*, nicht die
*Legalität*, und daraus eine zweite Ordnerregel abzuleiten wäre eine erfundene Politik.
Entscheidung für Max.
