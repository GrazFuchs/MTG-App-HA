# Sprint 09 — Display & Fehlerzustände

**Status: ✅ umgesetzt in 0.42.0, deployed + live gemessen am 2026-08-28.** Ist-Protokoll am Ende.

**Ziel:** Die drei Systemklassen hinter der Darstellungs-Bug-Serie beheben: Stacking/Overlays,
Ingress-Pfadauflösung, fehlende Fehlerzustände — plus Render-Tests, damit die Klasse geschlossen
bleibt.

**Warum (Befunde):** B3b, W1, W5, W12, B18, B19 in [review-befunde.md](review-befunde.md).

## Umgesetzt

| # | Paket | Datei |
|---|---|---|
| 1 | **B3b — `OverlayPortal`**: eine Utility, durch die **alle** Overlays laufen. `PriceTrendHover` trug den 0.34.1-Fehler unverändert weiter; `CardHoverPreview` und `TriageDecisionDialog` portalten schon, aber jeder für sich. Dialog zusätzlich auf `maxHeight: 90vh` + `overflowY: auto` | **neu:** `components/OverlayPortal.tsx`, `PriceTrendHover.tsx`, `CardHoverPreview.tsx`, `inbox/TriageDecisionDialog.tsx` |
| 2 | **W1 — `<base href>`** aus dem `X-Ingress-Path`-Header (Fallback: `INGRESS_ENTRY`), beim Ausliefern der Shell injiziert. Reload auf `/decks/5` lädt wieder | `static_files.py` |
| 3 | **Fehlerzustände**: `ErrorBoundary` um alle Routen, Catch-all-Route mit echter 404-Seite | `App.tsx`, **neu:** `pages/NotFound.tsx` |
| 4 | **W5 — Überschuss**: Deckverwendung wird abgezogen, über die Printings verteilt; Listings zählen printing-genau. Die MCP-Kopie teilt die Abfrage | `services/queries.py`, `mcp_server.py` |
| 5 | **B18 — Render-Tests**: vitest auf `jsdom` + Testing Library; `api.ts` fasst `window` nicht mehr beim Modul-Load an | `vite.config.ts`, `api.ts`, **neu:** `src/__tests__/` |
| 6 | **B19 — Code-Splitting**: alle 10 Seiten über `React.lazy` | `App.tsx` |
| 7 | Version 0.42.0 + CHANGELOG | — |

### Der Fund, der den Sprint überhaupt erst möglich machte

**Die zwei seit Wochen roten Tests hatten eine echte Ursache, keine Umgebungsmacke.** Starlette
übergibt `get_response` einen **OS-normalisierten** Pfad — auf Windows also `assets\index-abc.js`.
Jeder Präfixtest im Modul ist mit Schrägstrich geschrieben, also war auf Windows sowohl der
Asset-Cache-Header falsch (`no-cache` statt `immutable`) als auch die API-Durchreichung
(`/api/nope` bekam die SPA-Shell statt eines 404). Auf Linux fällt beides zusammen, deshalb lief
die Produktion richtig.

Der Preis war trotzdem hoch: **zwei dauerhaft rote Tests erziehen dazu, die Suite zu ignorieren.**
Seit dieser Änderung ist sie zum ersten Mal ganz grün — was die Voraussetzung dafür war, den Rest
dieses Sprints überhaupt zu belegen.

### Zwei Entscheidungen, die im Sprint-Text so nicht standen

**(a) Der naive W5-Fix hätte den umgekehrten Fehler eingebaut.** Der Sprint sagte: „`extras` auf
das bereits berechnete `extras_global` umstellen". Das ist der Karten-Überschuss — die Zeilen sind
aber je **Printing**. Jede Zeile mit dem vollen Karten-Überschuss zu füllen hieße, ihn in jeder
Summe **doppelt** zu zählen, sobald eine Karte in zwei Drucken vorliegt. Stattdessen wird der
Überschuss über die Printings **verteilt** (stabile Reihenfolge, gedeckelt durch den Besitz je
Druck), sodass die Zeilen genau einmal auf ihn aufsummieren. Eigener Test dafür.

**(b) Fluent UI gehört nicht in einen Render-Test.** Der erste Anlauf importierte `ErrorBanner`
(und damit `@fluentui/react-components`) — der Lauf hing **über zehn Minuten** im Transformieren
und wurde abgebrochen. Ohne die Bibliothek: 34 Tests in **2,8 s**. Getestet wird, *wo* ein Knoten
im DOM landet und *ob* ein Fehler sichtbar wird — dafür braucht es kein Designsystem. Steht als
Warnung im Kopf der Testdatei.

## Akzeptanz

- [x] **Reload auf `/decks/5` über Ingress** — die Shell trägt jetzt `<base href="…ingress…/">`;
  vier Tests halten das fest (mit Ingress, ohne Ingress, Cache-Header bleibt, vorhandene Basis wird
  nicht überschrieben).
- [x] **Hover über einen Preis-Trend liegt über den Folgekarten** — `PriceTrendHover` portalt.
- [x] **Abgezogenes Backend zeigt Banner statt Leere** — `ErrorBoundary` um alle Routen, plus
  echte 404-Seite für unbekannte Pfade.
- [x] **`npm test` enthält echte Komponententests unter jsdom** — 4 neue, **jeder gegengeprüft:
  macht man `OverlayPortal` wieder inline, fällt der Test.**
- [x] **Sell-Dialog bietet keine deckgebundenen Kopien mehr an** — der Überschuss zieht die
  Deckverwendung ab (Test `test_copies_inside_a_deck_are_not_surplus`).

## Verifikation

- [x] Backend **320/320 grün** — erstmals ohne Altbestand.
- [x] Frontend **34 Tests grün** (2 Bestandsdateien + 4 neue Komponententests).
- [x] Build: Einstiegs-Chunk **392 kB statt 1179 kB** (120 statt 336 kB gzip).
- [ ] **375-px- und 768-px-Smoke mit Screenshots** — nicht gemacht, siehe „Offen".

## Ist-Protokoll (2026-08-28)

**⚠️ Die Duplikat-Zahlen bewegen sich — und nicht alle in dieselbe Richtung.** Ich hatte im
CHANGELOG zuerst geschrieben, sie sinken. Die Messung sagt etwas anderes:

| | vorher | nachher |
|---|---:|---:|
| Überschuss-Karten | 2526 | **2763** |
| Überschuss-Wert | 1062,70 € | **1041,33 €** |
| nicht gelistet | 915,17 € | **942,23 €** |
| Zeilen mit Überschuss (Seite) | — | 1962 |
| `sell_potential_eur` (unberührt) | 1817,47 € | 1817,47 € |

**Zwei Korrekturen ziehen gegeneinander, und die Listing-Korrektur ist die größere.** Deckgebundene
Exemplare fallen heraus (senkt); Listings zählen nicht mehr gegen *andere Drucke* derselben Karte
(hebt). Konkret: drei Exemplare von Druck A, zwei von Druck B, vier von A gelistet — der alte
Namens-Match strich alle fünf und meldete nichts Verkäufliches, obwohl zwei Exemplare von B
ungelistet herumlagen. **Der Anstieg ist die Korrektur, nicht ein Rückfall.** Genau dieser Fall
steht als Test (`test_a_listing_only_counts_against_its_own_printing`).

⚠️ **Die HA-Sensoren zeigen den alten Wert, bis der Stats-Publish gelaufen ist** (retained MQTT).
Nach dem Neustart dauerte das ~2 Minuten — wer direkt nach einem Deploy vergleicht, misst den
Vorzustand und hält den Fix für wirkungslos.

## Offen

- **Der Responsive-Smoke** (375 px / 768 px mit Screenshots) ist nicht erfolgt — dafür braucht es
  einen Browser. Die dort erwarteten Befunde (Collection 601–768 px, Duplicates ohne Mobil-Layout,
  PageHeader bei 320 px) stehen als ungeprüfte Audit-Hinweise weiter in
  [review-befunde.md](review-befunde.md) und gehören zu **Sprint 10**.
- **42 von 1223 Listings sind keinem Druck zugeordnet** und zählen deshalb gegen gar nichts mehr;
  für diese liest der Rückstand etwas zu hoch. Sie nach Namen zuzuordnen wäre dieselbe Vermutung,
  die 0.33.0 aus der Preisverknüpfung entfernt hat. Eigener Test hält die Grenze fest.
- **Die Render-Tests decken zwei Klassen ab, nicht alle drei.** Die Inbox-Entscheidung („Karte
  verschwindet, kein Fehler verschluckt") aus dem Sprint-Text fehlt — sie braucht einen
  gemockten API-Layer, und der gehört sinnvollerweise in **Sprint 08**, der die Inbox ohnehin
  umbaut.
