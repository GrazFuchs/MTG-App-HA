# Sprint 11 — AI über MCP

**Status: ✅ Add-on-Seite umgesetzt in 0.45.0, deployed + live geprüft am 2026-08-29.**
⚠️ **Die zwei Client-Pakete (4 und 5) sind bewusst NICHT gemacht** — beide sind
Entscheidungen des Auftraggebers, nicht Arbeit. Begründung unten.

**Ziel:** Die vorhandene AI-Anschlussfläche vom Einzelfall zum Arbeitsablauf machen.
**Bestätigte Randbedingung: es gibt kein LLM im Add-on und das bleibt so.**

**Warum:** B7, W11, plus die MCP-Hinweise des Audits (ungeprüft — beim Umsetzen verifiziert).

## Umgesetzt — Add-on

| # | Paket | Datei |
|---|---|---|
| 1 | **Drei neue Tools**: `compute_power_level`, `explain_bracket`, `suggest_bracket_safe_upgrades` | `mcp_server.py` |
| 2a | **Ein Buchungspfad** für REST und MCP | **neu:** `services/triage_decision.py`, `routers/acquisitions.py`, `mcp_server.py` |
| 2b | **`clear_cardmarket_listings` verlangt `confirm: true`** | `mcp_server.py` |
| 2c | **Sibling-Awareness im MCP-Vorschlag** | `mcp_server.py` |
| 3a | **`ai.stale`-Badge** an der `AIAssessmentBox` | `AIAssessmentBox.tsx`, `api.ts` |
| 3b | **`analyze_deck` schreibt zurück**, dazu `refresh_stale_assessments` und die zwei Tools, die der Prompt braucht | `mcp_server.py` |
| — | Voice-REST-Beispiel in der Doku korrigiert | `docs/ha-integration.md` |
| — | Version 0.45.0 + CHANGELOG | — |

**42 → 47 Tools, 2 → 3 Prompts.**

### Die Buchung gab es zweimal, und die zweite war stumm kaputt

Das MCP-`decide_triage` hatte eine eigene Kopie der Logik. Beide „funktionierten" — die Karte war
danach aus der Warteschlange —, aber die MCP-Fassung schrieb **weder `decision_snapshot` noch
Notizen** und stieß **den HA-Publish nicht an**. Eine über Claude entschiedene Karte stand damit
ohne Snapshot im Archiv, und die Sensoren meldeten den alten Stand weiter, bis zufällig etwas
anderes einen Publish auslöste.

Beide gehen jetzt durch `services/triage_decision.py`. **Die Form des Fehlers ist der Punkt, nicht
der Einzelfall:** zwei Aufrufstellen, die „dasselbe" tun, laufen leise auseinander, weil keine für
sich falsch ist.

### Dieselbe Klasse, direkt nebenan

`get_suggestion` ist sibling-aware — es zählt die *anderen* offenen Ereignisse derselben Karte als
bereits vorhanden — **aber nur, wenn der Aufrufer die `id` mitgibt.** Und es liest sie mit
`.get()`, das Weglassen ist also kein Fehler, sondern liefert stillschweigend eine andere
Empfehlung. Von vier Aufrufstellen ließ genau die MCP-Stelle sie weg.

**Praktische Folge:** bei einem Massenimport — dem Fall, für den es die Sibling-Logik überhaupt
gibt — empfahl ein Assistent etwas anderes, als die Web-UI für dieselbe Karte anzeigte. Ein Test
liest jetzt alle drei Module und prüft, dass jedes `event_row` eine `id` trägt.

### Ein Prompt, der Tools nannte, die es nicht gab

Der neu geschriebene `analyze_deck` verwies auf `set_deck_gameplan` und `set_deck_user_bracket` —
**beide existierten nicht.** Das ist schlimmer als kein Prompt: der Assistent merkt es mitten in
der Aufgabe und improvisiert, und die Improvisation sieht aus wie das gewollte Verhalten. Die
Tools gibt es jetzt, und ein Test läuft **jeden** Prompt durch und prüft jedes genannte Tool gegen
die Tool-Liste.

### Der Befund zu den Assessments — die Zahl stimmte nicht

B7 sagte „1 von 22 Decks hat ein Assessment, 11 Wochen alt". Live gemessen am 2026-08-29:

| | |
|---|---|
| Decks gesamt | 22 |
| ohne jedes Assessment | **18** |
| mit Assessment | **4** — und **alle vier älter als die letzte Deckänderung** |

Es sind also viermal so viele wie im Befund, und **keines davon ist aktuell**. Der alte Prompt bat
nur um eine Analyse; die stand dann im Chatfenster und das Add-on behielt nichts davon.

⚠️ Verglichen wird gegen **`updated_at`** (Archidekts Bearbeitungszeit), nicht `last_synced` —
letzteres sagt nur, wann wir zuletzt hingesehen haben.

### `suggest_bracket_safe_upgrades` — zwei bewusste Vorgaben

**`owned_only` ist standardmäßig `true`.** Ein Assistent, den man nach Upgrades fragt, schlägt
sonst bereitwillig vor, eine Karte zu kaufen, die in einer Kiste liegt. Erste Quelle ist deshalb
der eigene Überschuss (dieselbe Abfrage wie die Duplikate-Seite, seit Sprint 09 geteilt).

**Bracket-hebende Kandidaten werden getrennt ausgewiesen, nicht verworfen.** Eine Karte, die ein
Bracket-3-Deck auf 4 schiebt, ist eine legitime Wahl — solange sie eine bewusste ist. Jeder
Kandidat läuft dafür durch `bracket_impact_of_card`, also durch dieselben Regeln, als wäre er
schon im Deck.

## Akzeptanz

- [x] **Claude kann Power-Level erklären, Bracket begründen, Upgrades aus eigenem Bestand liefern**
  — live gegen 0.45.0 über den MCP-Endpunkt geprüft (Bearer-Token, `tools/call`):
  `explain_bracket(1)` → Bracket 2, keine Regel gefeuert ·
  `compute_power_level(1)` → Score 645,96 / Level 7,43, Effizienz 7,42, Kipppunkt 3,0, Treiber
  Sol Ring · Monument to Endurance · Untimely Malfunction, Referenz-URL vorhanden.
- [x] **Eine MCP-Triage-Entscheidung landet mit Snapshot im Archiv und aktualisiert die Sensoren**
  — durch den gemeinsamen Service strukturell erzwungen; ein Test bricht, sobald das MCP-Tool
  wieder eigenes `INSERT INTO cardmarket_listings` bekommt.
- [ ] **Nach einem geplanten Lauf haben alle Decks ein aktuelles Assessment** — nicht erfüllt, weil
  der geplante Lauf (Paket 4) bewusst nicht eingerichtet ist. Die Werkzeuge dafür stehen; die
  Ausgangslage ist gemessen und oben festgehalten.

## Verifikation

- [x] Backend **330/330** (5 neue in `tests/test_mcp_server.py`), Frontend **45/45**, Build grün.
- [x] **Der Sibling-Wächter ist gegengeprüft**: `id` wieder entfernt → Test fällt
  (`app.mcp_server: event_row without an id`), zurückgesetzt → grün.
- [x] Live: `healthz` meldet 0.45.0, `tools/list` liefert **47** Tools, alle fünf neuen dabei.
- [x] **`clear_cardmarket_listings` ohne `confirm`** antwortet live
  `{"status":"not_confirmed","would_delete":1223,...}` und löscht nichts. Die 1223 sind der
  Grund für die Sperre.

## Bewusst nicht gemacht — beides Entscheidungen, keine Arbeit

**Paket 4 — der wöchentliche Claude-Lauf.** Genau das würde aus 4 von 22 Assessments 22 von 22
machen, und die Werkzeuge dafür sind jetzt alle da (`refresh_stale_assessments` ist der Prompt).
Aber es heißt: **ein Agent schreibt planmäßig und unbeaufsichtigt in die Datenbank.** Das
einzurichten ist die Entscheidung des Auftraggebers, nicht meine.

**Paket 5 — Voice: installieren oder entfernen.** Der Ist-Zustand ist *genauer* als der
Sprint-Text sagt („end-to-end tot"):

| | gemessen 2026-08-29 |
|---|---|
| Add-on-Endpunkte `/api/voice/*` | **funktionieren** — `active-deals` antwortet 200 |
| `custom_sentences/` in HA | **existiert gar nicht** |
| die zwei REST-Sensoren | **nicht in der `configuration.yaml`** |
| Intents in `voice/sentences.yaml` | 7, davon 0 auslösbar |

Die Backend-Hälfte steht also, die HA-Hälfte fehlt vollständig. Beide Wege sind vertretbar; die
Wahl ist eine Produktentscheidung. **Was ohne Entscheidung falsch war und behoben ist:** das
REST-Beispiel in `docs/ha-integration.md` zeigte auf `http://localhost:8099` — das kann nicht
gehen, weil HA Core den Sensor auswertet und `localhost` dort Core selbst ist. Es nennt jetzt den
Container-Hostnamen, und der gemessene Ist-Zustand steht daneben.

## Offen

- **Der MCP-Smoke über den mcp-proxy** (statt direkt gegen den Container) ist nicht gelaufen —
  geprüft wurde gegen `http://0c11a0b9-mtg-collection:8099/mcp` mit Bearer-Token, was dieselbe
  Codepfad-Kette ist, aber nicht denselben Transportweg wie Claude Desktop.
- **`suggest_bracket_safe_upgrades` ist funktional geprüft, aber nicht an einem Deck bewertet.**
  Ob die Vorschläge *gut* sind, sagt erst der Gebrauch — das ist der nächste sinnvolle Schritt und
  kein Fehler.
