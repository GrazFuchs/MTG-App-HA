# Sprint 11 — AI über MCP

**Ziel:** Die vorhandene AI-Anschlussfläche (42 MCP-Tools) vom Einzelfall zum Arbeitsablauf
machen. **Bestätigte Randbedingung (Auftraggeber + W11): es gibt kein LLM im Add-on und das
bleibt so** — die Intelligenz sitzt im externen Client (Claude via mcp-proxy), das Add-on liefert
Werkzeuge und Daten. Am wertvollsten nach Sprint 04/05.

**Warum:** B7 (1 von 22 Decks hat ein Assessment, 11 Wochen alt, kein UI-Trigger), W11, plus die
MCP-Hinweise des Audits (ungeprüft — beim Umsetzen verifizieren).

## Arbeitspakete — Add-on (MCP-Server)

1. **Neue Tools** (nach Sprint 04/05 trivial, weil die Services dann existieren):
   - `compute_power_level(deck)` → Score/Level/Detail aus `services/power_level.py`.
   - `explain_bracket(deck)` → `computed_bracket_detail` menschenlesbar.
   - `suggest_bracket_safe_upgrades(deck, budget, owned_only)` → Kandidaten aus Duplicates
     (eigener Bestand!) + EDHREC-Empfehlungen (`clients/edhrec.py` liegt fertig da und ist heute
     von nichts erreichbar), gefiltert gegen die Bracket-Grenze des Decks.
2. **MCP-Schreibpfade angleichen** (Audit-Hinweise verifizieren, dann fixen):
   `decide_triage` via MCP soll `decision_snapshot` schreiben und den HA-Publish anstoßen wie
   die REST-Route; der MCP-Triage-Vorschlag soll dieselbe Sibling-Awareness haben wie die UI.
   `clear_cardmarket_listings` bekommt einen Bestätigungs-Parameter (`confirm: true` Pflicht).
3. **Assessment operationalisieren:** `ai_assessment_updated_at` gegen `decks.updated_at`
   vergleichen → „Stand veraltet"-Badge an der `AIAssessmentBox`; MCP-Prompt `analyze_deck`
   aktualisieren, sodass er Gameplan + Assessment + `user_bracket`-Vorschlag in einem Durchgang
   schreibt.

## Arbeitspakete — Client-Seite (Repo `ha-infrastructure`)

4. **Geplanter Claude-Lauf:** wöchentlicher Scheduled-Agent/Cron, der über den MCP-Proxy alle
   22 Decks durchgeht: veraltete/fehlende Assessments erneuern (`set_deck_ai_assessment`),
   Bracket-Vorschläge gegen `computed_bracket` prüfen, Auffälligkeiten (Combo eine Karte
   entfernt, Bracket-Kipper auf der Wunschliste) als HA-Notification zusammenfassen.
   → So werden aus 1/22 Assessments 22/22, ohne ein LLM ins Add-on zu bauen.
5. **Voice: entscheiden statt halb lassen.** Ist-Zustand end-to-end tot (7 Intents definiert,
   0 auf HA installiert; Doku-REST-Snippet zeigt auf `localhost:8099`, von HA Core unerreichbar).
   Entweder die 2 sinnvollen Intents echt installieren (deutsche `custom_sentences` +
   `intent_script`, REST auf `http://0c11a0b9-mtg-collection:8099` — nur der Container-Hostname
   funktioniert) **oder** `voice/` + Doku-Abschnitt entfernen.

## Akzeptanz

- Claude Desktop (über den in Sprint 01 reparierten Wizard-Config) kann: Power-Level erklären,
  Bracket begründen, Upgrade-Vorschläge nur aus eigenem Bestand liefern.
- Nach einem geplanten Lauf haben alle Decks ein Assessment jünger als ihr letzter Deck-Edit.
- Eine MCP-Triage-Entscheidung erscheint im Inbox-Archiv mit Snapshot und aktualisiert die
  HA-Sensoren binnen Debounce-Fenster.

## Verifikation

- MCP-Smoke über den Proxy: initialize → tools/list → je ein Read- und Write-Tool mit Token.
- Vorher/Nachher: `SELECT COUNT(*) FROM decks WHERE ai_assessment != ''`.
