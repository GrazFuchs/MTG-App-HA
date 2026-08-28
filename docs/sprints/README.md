# Sprint-Plan aus der Begutachtung 2026-08-23

Ergebnis der kritischen Begutachtung der App + HA-Integration (Befunde, Messwerte und Belege:
[review-befunde.md](review-befunde.md)). Jeder Sprint ist einzeln abarbeitbar; Abhängigkeiten
stehen in der Tabelle. Konvention je Datei: **Ziel · Warum · Arbeitspakete · Akzeptanz · Verifikation**.

| # | Sprint | Braucht | Status |
|---|--------|---------|--------|
| 01 | [Wahrheit & Quick-Fixes](sprint-01-wahrheit.md) | — | ✅ umgesetzt (0.35.0) |
| 02 | [Scryfall-Datenfundament](sprint-02-scryfall-fundament.md) | — | ✅ umgesetzt (0.36.0), deployed |
| 03 | [Combo-Abdeckung reparieren](sprint-03-combos.md) | — | ✅ umgesetzt (0.37.0), deployed |
| 04 | [Bracket: pflegbar + berechnet](sprint-04-bracket.md) | 02, 03 | ✅ umgesetzt (0.38.2), deployed |
| 05 | [Power-Level (edhpowerlevel-Port)](sprint-05-powerlevel.md) | 02 | ✅ umgesetzt (0.39.0), Referenz-Diff offen |
| 06 | [Wishlist: Deals & Bracket-Brücke](sprint-06-wishlist-deals.md) | 01, 03, 04 | ✅ umgesetzt (0.40.0), deployed |
| 07 | [HA-Brücke begradigen](sprint-07-ha-bruecke.md) | — | ✅ umgesetzt (0.41.0 + HA-Seite), deployed |
| 08 | [Inbox/Triage entlasten](sprint-08-inbox-triage.md) | — | offen |
| 09 | [Display & Fehlerzustände](sprint-09-display-fehlerzustaende.md) | — | ✅ umgesetzt (0.42.0), deployed |
| 10 | [i18n, A11y, Responsive](sprint-10-i18n-a11y-responsive.md) | — | offen |
| 11 | [AI über MCP](sprint-11-ai-mcp.md) | am wertvollsten nach 04/05 | offen |
| — | [Backlog](backlog.md) (bewusst ohne Sprint) | — | — |

```
01 (frei) ──► 02 ──► 04 ──► 06(Teil 2)
                └──► 05
03 (frei) ──► 04, 06(Teil 3)
06(Teil 1) braucht nur 01
07, 08, 09, 10 unabhängig · 11 nach 04/05
```

## Entscheidungen des Auftraggebers (Feedback-Runde 2026-08-23)

- **Brackets bleiben** — offizielles WotC-System; Umbau, sodass der Bracket in der App
  **pflegbar** ist (Sprint 04).
- **Game Logger bleibt unangetastet** — wenig gespielt ist kein Defekt.
- AI-Assessment läuft bewusst **nur über MCP** (kein LLM im Add-on) — Ausbau clientseitig (Sprint 11).
- Wunschliste: Schwerpunkt „Karte fällt unter den Wunschpreis" (Sprint 06).

## Deploy-Erinnerungen (gelten für jeden Sprint)

- Version an **drei** Stellen bumpen: `config.yaml`, `backend/app/version.py`, `frontend/package.json`.
- Deploy: push → auf dem Pi 5 `POST /store/reload` + `POST /addons/<slug>/update` (Supervisor-API,
  nur vom Pi aus). Danach **immer** `state: started` **und**
  `curl http://0c11a0b9-mtg-collection:8099/healthz` prüfen — ein Crash-Loop zeigt sich im Panel
  nur als 502, während Supervisor schon die neue Version meldet.
- Add-on-Optionen schreiben = **ganzes Objekt** (ein weggelassenes Feld ist gelöscht) +
  Add-on-Neustart (`get_settings()` hat `@lru_cache`).
- HA-Dashboards: über `tools/patch-mtg-gameroom.py --apply` bzw. `ha_ws.py` (rohe Config, nie den
  `.storage`-Wrapper), danach Snapshots in `ha-infrastructure/pi-ha/dashboards/` neu ziehen.

## Bekannter Test-Altbestand — erledigt (0.42.0)

`backend/tests/test_static_files.py` schlug auf dem Windows-Checkout mit 2 Tests fehl. Die
Vermutung „Umgebungs-/Pfadproblem" stimmte, war aber kein Grund zum Wegsehen: Starlette übergibt
dem Handler einen **OS-normalisierten** Pfad, und jeder Präfixtest im Modul ist mit Schrägstrich
geschrieben — auf Windows waren dadurch der Asset-Cache-Header *und* die API-Durchreichung falsch.
Behoben in Sprint 09; die Suite ist seither **320/320 grün**.
