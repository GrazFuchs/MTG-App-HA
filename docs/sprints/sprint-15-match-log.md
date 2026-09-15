# Sprint 15 — Spielprotokoll für 1v1 und Best-of-3

**Status: ✅ umgesetzt in 0.50.0 am 2026-09-15, gegen die echte DB gemessen.**
Ist-Protokoll am Ende.

**Ziel:** Eine Standard-Partie ist mit denselben Taps erfasst wie eine Commander-Partie — ohne jedes
Mal „4 Spieler" zu korrigieren — und **drei Partien lassen sich zu einem Match zusammenfassen**, mit
der Sideboard-Entscheidung je Partie.

**Warum:** Befund 13 des Plans. `pod_size` stand hart auf **4**, das Label hieß „Opponents /
commanders", der Hint nannte „Atraxa, Krenko". Für ein 60-Karten-Deck ist jede dieser drei Angaben
falsch, und eine Erfassung, die man jedes Mal korrigieren muss, wird irgendwann nicht mehr
korrigiert — dann steht eine Standard-Partie mit vier Spielern im Log.

**Braucht:** Sprint 12 (`formats.py`, `default_pod_size`).

## Arbeitspakete

| # | Was | Ergebnis |
|---|---|---|
| 1 | **Ein Einfügepfad** für Partien statt zwei | `game_log.insert_game()` + Wächter-Test |
| 2 | `pod_size` folgt dem Format des Decks | `DeckGameBase.pod_size: int \| None` |
| 3 | Das HA-Formular folgt der Deckauswahl | `_follow_deck()` |
| 4 | **Migration 30**: `match_id` · `game_in_match` · `sideboard_notes` | keine Match-Tabelle |
| 5 | Gruppierung über ein **Zeitfenster**, kein Pflichtfeld | `MATCH_WINDOW_MINUTES = 90` |
| 6 | Statistik: Matches + `game_2_3_win_rate` | `_match_stats()` |
| 7 | Frontend: Partien eines Matches gruppiert, „lösen"-Knopf | `DeckPerformanceSection` |
| 8 | HA: **ein** neues Feld, Match in der Statuszeile | `text.mtg_log_sideboard` |

## Zwei Einfügepfade waren schon einer zu viel

Der Web-Weg (`routers/decks.add_deck_game`) und der HA-Weg (`services/game_log.log_game`) schrieben
je ihr eigenes `INSERT INTO deck_games`. Solange beide nur Felder durchreichten, fiel das nicht auf.
Sobald etwas **entschieden** wird — die Podgröße aus dem Format, die Zugehörigkeit zu einem Match —
ist es die Bauform, an der dieses Projekt schon dreimal bezahlt hat: zwei Buchungspfade in 0.45.0,
zwei Überschuss-Lesarten vor 0.42.0, drei Bracket-Leser in 0.47.0.

Deshalb gibt es jetzt **`insert_game()` und sonst nichts**, plus einen Test, der die Quellen scannt
und bei einem zweiten `INSERT INTO deck_games` anschlägt. Gegenprobe gemacht: ein eingefügtes
zweites INSERT lässt ihn fallen.

## Die Podgröße ist ein Default, keine Zahl

`pod_size` ist im Schema **optional** geworden (`int | None`), und `insert_game` füllt sie aus
`formats.spec(...).rules.default_pod_size`. Das ist der Unterschied zwischen „niemand hat es gesagt"
und „jemand wollte vier" — dieselbe Unterscheidung, die `binds_copies` zwei Spalten gekostet hat.

Betroffen ist vor allem der **unsichtbare** Weg: `script.mtg_log_game`, eine Sprachbuchung, eine
Automation. Keiner davon schickt eine Podgröße mit, alle landeten auf 4. Das Skript schickt sie
weiterhin bewusst nicht — jetzt ist das die richtige Entscheidung statt einer stillen Falle.

Im HA-Formular zieht die Zahl bei der **Deckauswahl** nach, nicht bei jeder Veröffentlichung: ein
von Hand gesetzter Wert muss bis zum nächsten Deckwechsel stehen bleiben, sonst ist das Feld
unbenutzbar. Beim Wechsel auf ein Format ohne Sideboard wird zusätzlich die Sideboard-Notiz geleert
— eine Notiz aus dem letzten Standard-Match darf nicht in eine Commander-Partie mitfahren.

## Das Match ist die Gruppe seiner Partien

**Keine Match-Tabelle.** Ein gespeichertes Matchergebnis könnte den Partien widersprechen, aus denen
es stammt, und dann gäbe es zwei Antworten und keine Möglichkeit zu sagen, welche die echte ist.
Matchsieger ist, wer mehr Partien gewonnen hat; gleich ist unentschieden — was ein abgebrochenes 1-1
tatsächlich war.

**Der Einstieg ist der Zeitstempel, kein Formular.** Eine Partie, die binnen **90 Minuten** mit
demselben Deck gegen denselben Gegner gebucht wird, setzt dessen Match fort. Drei Buchungen
hintereinander sind ein Match — **null zusätzliche Eingaben**.

Zwei Feinheiten, die daraus folgen und beide Absicht sind:

* **Die zweite Partie erzeugt das Match und adoptiert die erste.** Eine einzelne Partie bleibt NULL,
  weil es bis zur zweiten nichts zu gruppieren gibt. Bei der ersten zu entscheiden hieße, vor der
  Information zu entscheiden.
* **Ohne Gegnernamen keine Gruppierung.** Nur aus der Uhr zu schließen würde zwei unabhängige,
  hintereinander gebuchte Partien verschmelzen — der eine Fehler, den man hinterher nicht sieht.

> ⚠️ **Das Fenster ist ein Urteil, keine Regel.** Zwei getrennte Bo1-Partien gegen dieselbe Person an
> einem Abend werden zusammengezogen. Das ist der bewusst gewählte Fehler: eine falsche Gruppierung
> kostet einen Klick („lösen"), ein zusätzliches Pflichtfeld kostet die Erfassung. Die Messung
> dahinter ist die von fetchlog — **8 Gassirunden in 7 Tagen über einen Ein-Tap-Tag gegen 1
> Trainingseinheit und 0 Mahlzeiten über ein Webformular in drei Monaten.** Was einen Knopf hat, wird
> benutzt.

`game_in_match` wird **nie hochgezählt, sondern aus der Gruppe gerechnet** (`renumber_match`) — und
ein Match, das nur noch eine Partie hält, löst sich wieder in eine Einzelpartie auf. „Match" ist eine
Aussage über eine Gruppe, und eine Gruppe von eins ist einfach eine Partie.

## `game_2_3_win_rate` — die eine Zahl, die nur Bo3 liefern kann

Die Siegquote **nach** dem Sideboarding. Sie ist der Grund, warum die Sideboard-Notiz überhaupt wert
ist, geschrieben zu werden: **ein Deck, das Partie eins gewinnt und das Match verliert, hat ein
Sideboard-Problem, kein Deckproblem.** Ohne die Trennung sieht man nur eine mittelmäßige Gesamtquote
und weiß nicht, an welcher Hälfte es liegt.

Eine ungruppierte Partie zählt in der Statistik als **Match von eins** — in einem Bo3-Format *ist*
eine einzelne Partie ein Bo1-Match, und sie wegzulassen würde den größten Teil der Tabelle stumm
verschwinden lassen. Wo nichts gruppiert ist, ist `match_win_rate` gleich `win_rate`; das ist die
Wahrheit, nicht ein Fehler.

**Commander sieht den ganzen Block nicht** (`format_rules.matches`). Ein Pod spielt eine Partie und
geht nach Hause, und es gibt kein Sideboard, mit dem sich etwas ändern ließe — „1 Match, 100 %" wäre
dieselbe Zahl unter einem zweiten Namen.

---

# Ist-Protokoll — 2026-09-15

Gemessen gegen den echten Bestand: **352 MB, 24 Decks**, Schema 29 → 30.
Migration **0,03 s**, zweiter Lauf idempotent (0,02 s), `deck_demand` unverändert bei 1490 Zeilen /
1797 Karten.

## Ausgangslage

| | |
|---|---|
| Partien im Log | **1** (Deck 1 „Sharknado", 2026-07-16, `pod_size` 2 von Hand) |
| Partien mit `match_id` nach der Migration | **0** — alle bisherigen bleiben Einzelpartien |
| Nicht-Commander-Decks | 61 „The Rock", 62 „Sligh" (beide Premodern) |

Die eine gespielte Partie ist zugleich die ehrlichste Zahl dieses Sprints: **Bo3 wird erst dann
etwas zeigen, wenn gespielt und gebucht wird.** Genau deshalb steht die Bauform „Zeitfenster statt
Pflichtfeld" im Zentrum — die Entscheidung des Auftraggebers vom 2026-09-14 lief gegen die
Empfehlung, und die Gegenleistung dafür ist, dass der Weg nichts kostet.

## Trockenlauf gegen Deck 61 „The Rock" (Premodern)

| Buchung | `pod_size` | `match_id` | Partie | Stand |
|---|---|---|---|---|
| 1 `win` vs „Testgegner" | **2** | — | — | — |
| 2 `loss` vs „Testgegner" | 2 | `d8511a4d` | **2** | 1-1 |
| 3 `win` vs „Testgegner" | 2 | `d8511a4d` | **3** | **2-1** |

Die zweite Buchung hat das Match erzeugt **und die erste adoptiert** — nach Buchung 3 tragen alle
drei Partien dieselbe `match_id` und die Nummern 1, 2, 3.

Statistik daraus: **3 Partien, 1 Match, 1-0, Match-Quote 100 %, nach dem Boarden 50 % aus 2
Partien.** Die Gesamtsiegquote liegt bei 67 % — die zwei Zahlen sagen Verschiedenes, und das ist der
ganze Punkt.

**Commander-Gegenprobe (Deck 1):** `pod_size` **4**, `match_id` **None**. Die 22 Commander-Decks
merken von diesem Sprint nichts.

Der Trockenlauf wurde in der Kopie wieder abgeräumt (1 Partie vorher, 1 Partie nachher).

## Tests

**417 grün** (403 vorher + 14 neue in `test_match_log.py`). Zwei Gegenproben gefahren, beide haben
angeschlagen und wurden zurückgenommen:

* `pod_size` fest auf 4 → `test_a_standard_game_seats_two_and_a_commander_game_four` fällt.
* Ein zweites `INSERT INTO deck_games` in `ha_form.py` →
  `test_nothing_writes_a_game_except_the_one_insert` fällt und nennt die Datei.

## Nachtrag 0.50.1 — der Abnahmetest hat etwas gefunden

Die Abnahme aus dem Plan lautet: „Standard-Deck wählen → `number.mtg_log_pod_size` springt auf 2".
Gegen das laufende Add-on ausgeführt sprang sie **nicht**. Die Datenbank sagte 2, die Karte zeigte 4.

`set_field` meldet **das kommandierte Feld** an MQTT zurück. Die Deckauswahl bewegt zusätzlich die
Podgröße, und die veröffentlichte niemand. HA behielt die alte Zahl, und der nächste Submit hätte den
Wert genommen, den niemand sehen konnte.

`apply_command()` meldet jetzt jedes Feld, das ein Kommando bewegt hat, und der MQTT-Handler
veröffentlicht alle. **Ein Wert, den das Add-on ändert und nicht veröffentlicht, ist ein Wert, den HA
nicht hat** — dieselbe Klasse wie die `json_attributes`-Falle in den HA-Packages.

⚠️ **Zweimal fast durchgerutscht.** Die Unit-Tests waren grün, weil sie die Datenbank lesen. Der
erste Wächter dafür war ebenfalls grün, weil er `apply_command` isoliert prüfte, während der Fehler
an der **Aufrufstelle** saß: den Publisher auf ein einzelnes Feld zurückzudrehen ließ ihn nicht
fallen. Der Test, der zählt, prüft `_on_form_message` gegen einen falschen MQTT-Client — und ist
gegen den wiederhergestellten Fehler verifiziert.

**Die Lehre für diese Sprint-Reihe:** ein Abnahmetest gegen das laufende System ist kein Ritual. Er
hat hier genau das gefunden, was die Testsuite strukturell nicht finden konnte.

## Offen

* **Der erste echte Bo3-Abend.** Alles oben ist gemessen, aber an einem Trockenlauf; ob 90 Minuten
  die richtige Zahl sind, sagt erst die erste falsche Gruppierung.
* **Der MCP-Trockenlauf gegen ein Nicht-Commander-Deck** (offen seit Sprint 12) — unabhängig von
  diesem Sprint, aber weiter offen.
