# Sprint 01 — Wahrheit & Quick-Fixes

**Status: ✅ umgesetzt in 0.35.0 (2026-08-23).** HA-seitige Pakete (unten, „Teil B") laufen in
Sprint 07 mit, weil sie dasselbe Repo (`ha-infrastructure`) betreffen wie dessen übrige Pakete.

**Ziel:** Jede Stelle, an der die UI etwas Falsches behauptet oder ein Knopf still nichts tut,
mit minimalem Eingriff auf Wahrheit bringen — bevor Neues gebaut wird.

## Teil A — Add-on (0.35.0), alles umgesetzt

| # | Paket | Befund | Datei |
|---|---|---|---|
| 1 | `last_sync_at` als UTC-ISO publizieren (`utc_iso()`-Helper, nie synchronisiert → `None` statt erfundener Jetzt-Zeit) + 3 Tests | B2/W4 | `services/ha_publisher.py`, `tests/test_ha_discovery.py` |
| 2 | Dashboard-Kopf: echter Sync-Zeitstempel + Status-Punkt aus `/api/sync/status` (SYNCED/SYNCING…/FAILED/NEVER); Delta aus `value_snapshots` berechnet; Fehlerbanner + Em-Dash statt €0.00 bei totem `/api/stats`; `t`-Shadowing beseitigt | W2/W3/W12 | `pages/Dashboard.tsx` |
| 3 | Archidekt-Bracket: `edhBracket` lesen (echter Feldname, verifiziert), Alt-Schlüssel als Fallback, Kommentar korrigiert | B26a | `clients/archidekt.py` |
| 4 | Completeness: Basisland-Ausschluss (bestehender Helper aus `queries.py`) | B25 | `routers/decks.py` |
| 5 | „Deals only": Param auf `is_deal_only` begradigt; dahinterliegenden Post-LIMIT-Filter gefixt (ungepaged filtern, dann paginieren) | W7 | `components/wishlist/WishlistFilterBar.tsx`, `routers/wishlist.py` |
| 6 | Status → „Gesucht": PATCH statt `restore`; PATCH räumt Terminal-Flags (`acquired_at`, `not_received_at`, `is_ordered`, `ordered_at`); UNIQUE-Kollision → 409 | W6 | `components/wishlist/WishlistEditDialog.tsx`, `routers/wishlist.py` |
| 7 | MCP-Wizard: echte Proxy-Invocation (Positionsargumente + realer Ingress-Pfad + optionales Auth-Token-Argument) statt nie gelesener `MTG_*`-Env-Vars und nicht existentem `/mcp/sse`; Settings-Badge nicht mehr hartcodiert grün | W8 | `routers/mcp_setup.py`, `components/settings/MCPSetupSection.tsx`, `api.ts` |
| 8 | `common.loading` in `en` ergänzt; `<html lang>` folgt zur Laufzeit der UI-Sprache | B22.1/B21 | `i18n.ts` |
| 9 | Version 0.35.0 an allen drei Stellen + CHANGELOG-Eintrag | — | `config.yaml`, `version.py`, `package.json` |

**Deployment-Schritt (außerhalb des Repos):** `mcp_auth_token` in den Add-on-Optionen setzen
(B17) — ganzes Options-Objekt schreiben, Add-on-Neustart. ⚠️ Ein bestehender
Claude-Desktop-Proxy-Aufruf braucht danach das Token als 4. Argument.

## Teil B — HA-Seite (Repo `ha-infrastructure`) → nach Sprint 07 verschoben

- `patch-mtg-gameroom.py`: `DASHBOARDS` um `dashboard` erweitern (B30).
- Veraltete `sell_potential`-Warnkarte ersetzen (B31 — erst Gegenprobe der drei Verkaufszahlen).
- „Tauschen"-Knopf: Preis mitgeben oder entfernen (W9).
- `last_sync_at`-Warnkarte entfernen, sobald 0.35.0 verifiziert läuft.

## Verifikation

- [x] Backend: 211/213 Tests grün (2 Fehlschläge = Altbestand `test_static_files.py`, auch auf
  unverändertem Stand — siehe README).
- [x] Frontend: `tsc -b && vite build` grün, 30 Vitest-Tests grün.
- [ ] Nach Deploy: `healthz` → 0.35.0; `sensor.mtg_last_sync_at` zeigt Zeitstempel (Publish läuft
  beim Start, wenn je ein Sync abgeschlossen wurde).
- [ ] Wishlist: alle 6 Statusübergänge durchklicken, insbesondere `not_received` → `wanted`.
- [ ] „Deals only" an: nur Einträge mit `current ≤ target` sichtbar.
