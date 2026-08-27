# Sprint 09 — Display & Fehlerzustände

**Ziel:** Die drei Systemklassen hinter der Darstellungs-Bug-Serie beheben: Stacking/Overlays,
Ingress-Pfadauflösung, fehlende Fehlerzustände — plus Render-Tests, damit die Klasse geschlossen
bleibt. Unabhängig von anderen Sprints.

**Warum:** B3b, W1, W5, W12, B18, B19 in [review-befunde.md](review-befunde.md); die
Release-Historie (0.34.1, 0.22.0, 0.17.3) ist eine Serie genau dieser Klassen.

## Arbeitspakete

1. **B3b — Portal-Utility:** ein `<OverlayPortal>` (createPortal nach `document.body`), durch das
   **alle** Overlays laufen. `PriceTrendHover` portalen (trägt heute exakt den 0.34.1-Bug
   weiter); `TriageDecisionDialog` bekommt `maxHeight`/`overflow` (zweiter, ungefixter
   Unreachable-Confirm-Fall in kurzen Ingress-iframes). Konvention im Code dokumentieren:
   kein `position: fixed` innerhalb eines `Panel` ohne Portal (`backdrop-filter` macht jedes
   Panel zum Containing Block).
2. **W1 — Ingress-Basis endgültig:** `static_files.py` injiziert beim Ausliefern von
   `index.html` ein `<base href="{X-Ingress-Path}/">` (Header kommt vom Supervisor); damit lösen
   `./assets/…` auf jeder Routen-Tiefe korrekt auf. Reload/Bookmark von `/decks/5` funktioniert.
   ⚠️ Dabei die 2 fehlschlagenden `test_static_files.py`-Tests klären (schlagen auf Windows auch
   auf unverändertem Stand fehl — erst Ursache, dann Fix, siehe README).
3. **Fehlerzustände:** ErrorBoundary am App-Root (Komponente existiert); Catch-all-Route („Seite
   nicht gefunden" statt leerer Content-Fläche); `isError`-Pattern auf allen Seiten-Queries —
   Fehler rendert Banner, nie „leere Sammlung"/„keine Duplikate".
4. **W5 — Duplicates-Zahl:** `queries.py` `with_extras`: `extras` auf das bereits berechnete
   `extras_global` (`MAX(total_global − in_decks, 0)`) umstellen statt `total_copies`;
   `listed_quantity` auf `card_id` (+ Set/Foil wie die MCP-Schwester) matchen statt Namen.
   ⚠️ Vorher klären, ob `total_copies` Absicht war (Kommentar/Autor); die sichtbaren Zahlen
   (heute 2526 Karten / 1073 €) **sinken** danach — im CHANGELOG erklären. Der Sell-Dialog darf
   keine deck-gebundenen Kopien mehr anbieten.
5. **B18 — Render-Tests einführen:** vitest auf `environment: 'jsdom'` für Komponenten-Tests +
   Testing Library; `api.ts`-`window`-Zugriff beim Modul-Load entkoppeln (lazy/injizierbar —
   der eigene Testkommentar in Inbox.test.tsx benennt genau das als Blocker). Mindestbestand:
   Inbox-Entscheidung (Karte verschwindet, kein Fehler verschluckt), Dialog-Overlay über
   Folgekarten (Regression 0.34.1), Dashboard-Fehlerzustand (Banner statt €0.00).
6. **B19 — Code-Splitting:** Routen per `React.lazy` (10 Seiten) → der 1,15-MB-Chunk zerfällt;
   Erstaufruf über den cloudflared-Tunnel wird spürbar leichter.

## Akzeptanz

- Reload auf `/decks/5` über Ingress lädt die App (kein weißer Schirm).
- Hover über einen Preis-Trend in einer mittleren Inbox-Karte liegt **über** den Folgekarten.
- Abgezogenes Backend: jede Seite zeigt Banner, keine „leer"-Lüge.
- `npm test` enthält ≥3 echte Komponenten-Tests (jsdom) und läuft grün.
- Duplicates-Sell-Dialog: maxQty ≤ (global − in Decks − gelistet).

## Verifikation

- Vorher/Nachher der Duplicates-Kennzahlen dokumentieren (Karten/€) und im CHANGELOG erklären.
- 375-px- und 768-px-Smoke über die Hauptseiten (Screenshots im PR).
