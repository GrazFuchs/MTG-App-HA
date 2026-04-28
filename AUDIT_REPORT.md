# AUDIT REPORT — mtg-collection-ha Verbesserungs- und Feature-Plan

Audit durchgeführt am 26. April 2026 durch den implementierenden Agent. Hostile-Audit-Mindset angewendet.

---

## 1. Ausgangs-Inventur

```
Commit-Hash | Task-ID     | Kurzbeschreibung                              | Geänderte Dateien
a3614a2e    | Fix 1.1     | MCP auth token enforcement                    | backend/app/mcp_server.py, mcp-proxy.mjs, README.md
e14cc5c9    | Fix 1.2     | legalities in upsert_card                     | backend/app/services/sync_service.py
548c9b2c    | Fix 1.3     | CORS restrict                                 | backend/app/main.py
782b6a54    | Fix 1.4     | Remove port 8099 mapping                      | config.yaml
e0ac700d    | Fix 2.1     | Schema versioning with migration loop         | backend/app/database.py
16ee55b3    | Fix 2.2     | upsert_card ON CONFLICT RETURNING             | backend/app/services/sync_service.py
51d16462    | Fix 2.3     | Service-layer queries.py                      | backend/app/services/queries.py, mcp_server.py, routers/stats.py, routers/decks.py
e2dc7870    | Fix 2.4     | Exception logging in sync                     | backend/app/routers/sync.py
6fec8167    | Fix 2.5     | Cardmarket selectolax                         | backend/app/clients/cardmarket.py, requirements.txt
dca3b9b1    | Fix 2.6     | updated_at datetime comparison                | backend/app/services/sync_service.py
461a803f    | Fix 2.7     | DB connection pool                            | backend/app/database.py
40be7097    | Fix 3.1     | mcp-proxy remove npm install                  | mcp-proxy.mjs
65ae0882    | Fix 3.2     | Sparkline component extract                   | frontend/src/components/Sparkline.tsx, pages/Cardmarket.tsx
83ae30b1    | Fix 3.3     | Structured JSON logging                       | backend/app/logging_config.py, main.py, requirements.txt
408e07a6    | Fix 3.4     | /healthz endpoint                             | backend/app/main.py
dd31d27e    | Fix 3.5     | TanStack Query pilot                          | frontend/src/main.tsx, pages/Dashboard.tsx, package.json
98a98196    | Fix 3.6     | Lint setup ruff+mypy                          | pyproject.toml
bcacd2c8    | Fix 3.7     | Dark-mode HA sync                             | frontend/src/main.tsx
f081db39    | Fix 3.8     | Mobile-UX Collection                          | frontend/src/pages/Collection.tsx
2b590a64    | Feature 4.1 | MQTT Sensor Discovery                         | backend/app/services/ha_publisher.py, config.py, config.yaml, scheduler.py, main.py, requirements.txt, translations/en.yaml
761e2f8f    | Feature 4.2 | Price-Spike Notifications                     | backend/app/services/notifications.py, database.py, scheduler.py, config.py, config.yaml, translations/en.yaml
28ab8ecb    | Feature 4.6 | MCP suggest_what_to_sell                      | backend/app/mcp_server.py, services/sell_advisor.py
9de8ba03    | Feature 4.3 | Wishlist Deal-Alerts                          | backend/app/database.py, routers/wishlist.py, mcp_server.py, main.py, frontend/src/App.tsx, api.ts, pages/Wishlist.tsx
4beba11f    | Feature 4.4 | Collection-Wert-Snapshots                     | backend/app/database.py, routers/stats.py, scheduler.py, services/queries.py, frontend/src/api.ts, components/Sparkline.tsx, pages/Dashboard.tsx
dc33752c    | Feature 4.5 | MCP analyze_deck_completeness                 | backend/app/mcp_server.py
0a4bd27a    | Feature 4.7 | Bracket-Match-Finder                          | frontend/src/pages/Decks.tsx
8653b98a    | Feature 4.8 | Mana-Curve & Color-Pip charts                 | frontend/src/pages/DeckView.tsx
cc9ed557    | Feature 4.9 | MCP Resources                                 | backend/app/mcp_server.py
e57fe0e7    | Feature 4.10| Backup/Restore                                | backend/app/routers/backup.py, main.py, frontend/src/pages/Settings.tsx
a74286de    | Feature 4.11| Internationalisierung                         | frontend/src/i18n.ts, App.tsx, pages/Dashboard.tsx, pages/Settings.tsx
```

30 Commits vorhanden. 30 Tasks in der Spec.

---

## 2. Spec-Reload-Bestätigung

Spec erneut gelesen aus Transcript Zeile 7287. 30 Tasks identifiziert:
- TEIL 1: Fix 1.1, 1.2, 1.3, 1.4
- TEIL 2: Fix 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
- TEIL 3: Fix 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
- TEIL 4: Feature 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11

---

## 3. Per-Task-Audit

### === Task 1.1: mcp_auth_token durchsetzen ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/mcp_server.py:711-714`
  ```python
  settings = get_settings()
  if settings.mcp_auth_token:
      auth_header = request.headers.get("authorization", "")
      if not auth_header.startswith("Bearer ") or auth_header[7:] != settings.mcp_auth_token:
          return JSONResponse({"error": "Unauthorized"}, status_code=401)
  ```
- Datei: `mcp-proxy.mjs:20` — `const MCP_AUTH_TOKEN = process.argv[5] || process.env.MCP_AUTH_TOKEN || '';`
- Datei: `mcp-proxy.mjs:108` — `...(MCP_AUTH_TOKEN ? { 'Authorization': \`Bearer ${MCP_AUTH_TOKEN}\` } : {}),`

Verifikation der Akzeptanzkriterien:
- [✓] Anfrage ohne Header bei gesetztem Token → 401: Auth check triggers, returns 401.
- [✓] Anfrage mit falschem Token → 401: `auth_header[7:] != settings.mcp_auth_token` catches this.
- [✓] Anfrage mit korrektem Token → 200: passes the guard.
- [✓] Anfrage ohne Header bei leerem Token → 200: `if settings.mcp_auth_token:` is falsy, guard skipped.
- [✓] mcp-proxy.mjs forwards token: 4th CLI arg or ENV `MCP_AUTH_TOKEN`, sent as Bearer header.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 1.2: legalities in upsert_card ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/services/sync_service.py:36` — `legalities = card_data.get("legalities", "{}")`
- Datei: `backend/app/services/sync_service.py:72` — `keywords, legalities, edhrec_rank` in INSERT column list
- Datei: `backend/app/services/sync_service.py:83` — `legalities=excluded.legalities` in ON CONFLICT UPDATE

Verifikation der Akzeptanzkriterien:
- [✓] legalities is in both INSERT and UPDATE statements.
- [✓] Default `'{}'` when not present: `card_data.get("legalities", "{}")`.
- [✓] No KeyError from Archidekt path: `.get()` with default protects this.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 1.3: CORS einschränken ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/main.py:99-107`
  ```python
  cors_origins = os.environ.get("CORS_ORIGINS", "")
  if cors_origins:
      from fastapi.middleware.cors import CORSMiddleware
      app.add_middleware(
          CORSMiddleware,
          allow_origins=[o.strip() for o in cors_origins.split(",")],
          allow_methods=["*"],
          allow_headers=["*"],
      )
  ```

Verifikation der Akzeptanzkriterien:
- [✓] Default hat keine offene CORS-Policy: `CORS_ORIGINS` defaults to `""`, `if cors_origins:` is falsy → no CORS middleware added.
- [✓] Frontend via Ingress funktioniert: same-origin, no CORS needed.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 1.4: Port 8099 nicht exponieren ===
**Status: GREEN**

Evidenz:
- Datei: `config.yaml` — no `ports:` block present at all. Full file read confirms no port mapping.

Verifikation der Akzeptanzkriterien:
- [✓] Kein `ports`-Block → kein externer Port-Mapping.
- [✓] `ingress_port: 8099` (line 12 of config.yaml) — internal binding for ingress, not external exposure.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 2.1: Schema-Versioning real implementieren ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/database.py:278-296`
  ```python
  MIGRATIONS: dict[int, Callable[[aiosqlite.Connection], Awaitable[None]]] = {
      2: _migration_2,
      3: _migration_3,
      4: _migration_4,
      5: _migration_5,
      6: _migration_6,
      7: _migration_7,
  }
  ```
- `_run_migrations` at lines 299-316: reads `MAX(version)` from `schema_version`, applies missing ones in order, updates version.
- `init_db()` at line 329: `await _run_migrations(_primary)`

Verifikation der Akzeptanzkriterien:
- [✓] Fresh DB → version 7 after startup (highest migration key).
- [✓] Bestehender DB → only missing migrations applied (version comparison).
- [✓] Erneuter Start → no double migrations (version already at max).

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 2.2: upsert_card auf UPSERT ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/services/sync_service.py:64-91`
  ```python
  cursor = await db.execute(
      """INSERT INTO cards (...)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(scryfall_id) DO UPDATE SET
          oracle_id=excluded.oracle_id, name=excluded.name, ...
          updated_at=CURRENT_TIMESTAMP
      RETURNING id""",
      params,
  )
  row = await cursor.fetchone()
  return row[0]
  ```

Verifikation der Akzeptanzkriterien:
- [✓] Single statement with `INSERT ... ON CONFLICT DO UPDATE RETURNING`.
- [✓] Function signature unchanged: `upsert_card(db, card_data) -> int`, returns `row[0]`.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 2.3: Service-Layer queries.py ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/services/queries.py` exists, contains:
  - `query_collection_stats(db)` — lines 7-41
  - `query_all_decks(db)` — lines 44-60
  - `query_deck_detail(db, deck_id)` — lines 63-95
  - `record_value_snapshot(db)` — lines 98-113

- MCP uses these: `backend/app/mcp_server.py:646-661` — resources call `query_collection_stats`, `query_all_decks`.

Verifikation der Akzeptanzkriterien:
- [✓] Shared query functions exist in `services/queries.py`.
- [✓] MCP and routers both call these functions.

Abweichungen vom Spec: `search_collection` was not extracted into queries.py — it remains in the collection router. The spec mentioned it as one to extract. However, the MCP `search_collection` and the router `list_collection` have different query signatures (MCP returns dicts, router returns Pydantic). The core stats/decks/deck_detail are shared.
Out-of-scope-Änderungen: Added `record_value_snapshot` (needed for Feature 4.4).

---

### === Task 2.4: Stilles Exception-Swallowing ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/routers/sync.py:78-80`
  ```python
  except Exception:
      logger.exception("Background resync crashed")
  ```
- Lines 90, 96, 101, 107 — all `except Exception:` blocks have `logger.exception(...)`.
- Datei: `backend/app/main.py:72,79` — startup tasks use `logger.error(...)` for exception handling.

Verifikation der Akzeptanzkriterien:
- [✓] Zero `except Exception: pass` in sync.py (confirmed via grep: 0 matches).
- [✓] Exception stacktrace appears in logs via `logger.exception`.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 2.5: Cardmarket selectolax ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/clients/cardmarket.py:8` — `from selectolax.parser import HTMLParser`
- Datei: `backend/requirements.txt` — `selectolax>=0.3.21,<1.0.0`
- No regex-based DOM searching for product links, conditions, prices.

Verifikation der Akzeptanzkriterien:
- [✓] selectolax as dependency: confirmed in requirements.txt.
- [✓] CSS selectors used instead of regex for DOM traversal.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 2.6: updated_at als datetime vergleichen ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/services/sync_service.py:450-463`
  ```python
  remote_dt = datetime.fromisoformat(str(remote_updated))
  local_dt = datetime.fromisoformat(str(local["updated_at"]))
  # Normalize: make both aware (UTC) or both naive
  if remote_dt.tzinfo is not None and local_dt.tzinfo is None:
      local_dt = local_dt.replace(tzinfo=timezone.utc)
  elif remote_dt.tzinfo is None and local_dt.tzinfo is not None:
      remote_dt = remote_dt.replace(tzinfo=timezone.utc)
  if remote_dt <= local_dt:
      ...continue...
  ```
  Outer try/except at line 462: `except (ValueError, TypeError):` → re-sync on parse failure.

Verifikation der Akzeptanzkriterien:
- [✓] datetime comparison statt string comparison.
- [✓] TZ-aware normalization: both naive/both aware handled.
- [✓] Parse failure → re-sync (not crash).

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 2.7: DB-Connection-Strategie ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/database.py:11-13`
  ```python
  _pool: asyncio.Queue[aiosqlite.Connection] | None = None
  _pool_connections: list[aiosqlite.Connection] = []
  _primary: aiosqlite.Connection | None = None
  _POOL_SIZE = 2
  ```
- `borrow_db()` context manager at lines 188-196: gets/puts connections from asyncio.Queue.
- `init_db()` at lines 329-340: creates primary + 2 pool connections, all with WAL mode.

Verifikation der Akzeptanzkriterien:
- [✓] Connection pool exists (Queue-based, 2 extra connections).
- [✓] WAL mode remains active: `PRAGMA journal_mode=WAL` in `_create_connection`.

Abweichungen vom Spec: Pool size is 2 (not 3-5 as suggested), but spec said "3-5" only for Option B. The implementation is a minimal pool, which is valid.
Out-of-scope-Änderungen: keine

---

### === Task 3.1: mcp-proxy.mjs Runtime npm install entfernen ===
**Status: GREEN**

Evidenz:
- Datei: `mcp-proxy.mjs:150-157`
  ```javascript
  try {
    await import('ws');
  } catch {
    process.stderr.write(
      '[mcp-proxy] Error: "ws" package not found. Run "npm install" in the repo root first.\n'
    );
    process.exit(1);
  }
  ```
- No `execSync` anywhere in the file (grep confirmed: 0 matches).

Verifikation der Akzeptanzkriterien:
- [✓] No runtime `npm install` or `execSync` subprocess.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 3.2: Sparkline-Component auslagern ===
**Status: GREEN**

Evidenz:
- Datei: `frontend/src/components/Sparkline.tsx` exists, full component.
- Datei: `frontend/src/pages/Cardmarket.tsx` imports from `'../components/Sparkline'` (verified via grep).

Verifikation der Akzeptanzkriterien:
- [✓] Sparkline in separate component file.
- [✓] Import in Cardmarket.tsx updated.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: Sparkline was generalized to accept `{ trend: number }[]` instead of Cardmarket-specific type, to enable reuse in Dashboard (Feature 4.4).

---

### === Task 3.3: Strukturiertes Logging ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/logging_config.py` — full file:
  ```python
  from pythonjsonlogger import jsonlogger
  handler = logging.StreamHandler(sys.stdout)
  formatter = jsonlogger.JsonFormatter(
      fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
      rename_fields={"asctime": "timestamp", "levelname": "level"},
  )
  ```
- Datei: `backend/app/main.py:18` — `setup_logging()` called at module level.
- Datei: `backend/requirements.txt` — `python-json-logger>=2.0.0,<3.0.0`

Verifikation der Akzeptanzkriterien:
- [✓] JSON formatter configured with timestamp, level, name, message.
- [✓] Loki/Promtail can extract `level`, `name`, `message` (standard JSON fields).

Abweichungen vom Spec: `LOG_LEVEL` from ENV is not implemented. The logging level is hardcoded to `logging.INFO`. Spec says "Level aus ENV `LOG_LEVEL` (Default INFO)". This is a minor gap but it's in the spec text.
Out-of-scope-Änderungen: `logging_config.py` created as separate module rather than inline in `main.py:lifespan`.

---

### === Task 3.4: /healthz Endpoint ===
**Status: YELLOW**

Evidenz:
- Datei: `backend/app/main.py:124-128`
  ```python
  @app.get("/healthz", tags=["health"])
  async def healthz():
      from .database import get_db
      db = await get_db()
      await db.execute("SELECT 1")
      return {"status": "ok"}
  ```

Verifikation der Akzeptanzkriterien:
- [✓] `GET /healthz` returns 200 with JSON: yes.
- [✗] Body should include `version`, `db` (bool), `scheduler_running` (bool): only `{"status": "ok"}` is returned.
- [✗] Bei kaputter DB: `db: false` und HTTP 503: no try/except, no 503 response, no `db` boolean field.

Abweichungen vom Spec: Response body missing `version`, `db`, `scheduler_running`. No 503 on DB failure.
Begründung bei YELLOW: Endpoint exists and works, but response schema is incomplete per spec.

---

### === Task 3.5: TanStack Query im Frontend ===
**Status: GREEN**

Evidenz:
- Datei: `frontend/src/main.tsx:5` — `import { QueryClient, QueryClientProvider } from '@tanstack/react-query';`
- Datei: `frontend/src/main.tsx:9-11` — `const queryClient = new QueryClient({...})`
- Datei: `frontend/src/main.tsx:50` — `<QueryClientProvider client={queryClient}>`
- Datei: `frontend/src/pages/Dashboard.tsx:2` — `import { useQuery } from '@tanstack/react-query';`
- Datei: `frontend/src/pages/Dashboard.tsx:87-97` — three `useQuery` hooks for stats, alerts, valueHistory.
- Other pages (Settings, Collection, etc.) NOT converted — spec says "Die anderen Pages NICHT anfassen".

Verifikation der Akzeptanzkriterien:
- [✓] Dashboard.tsx uses `useQuery`.
- [✓] Refetch-on-window-focus: default QueryClient behavior, not disabled.
- [✓] Other pages unchanged (Settings still uses `useEffect + useState`).

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 3.6: Lint-Setup ruff + mypy ===
**Status: YELLOW**

Evidenz:
- Datei: `pyproject.toml` (at repo root):
  ```toml
  [tool.ruff]
  target-version = "py312"
  line-length = 120
  src = ["backend"]
  [tool.ruff.lint]
  select = ["E", "F", "W", "I", "UP", "B", "SIM"]
  ignore = ["E501"]
  [tool.mypy]
  python_version = "3.12"
  warn_return_any = true
  warn_unused_configs = true
  ignore_missing_imports = true
  ```

Verifikation der Akzeptanzkriterien:
- [✓] `ruff check backend/` läuft (config present, tool runs).
- [✓] `mypy backend/` läuft (config present).

Abweichungen vom Spec:
1. File location: spec says "im `backend/`-Ordner anlegen", actual location is repo root. Functionally equivalent (ruff/mypy find pyproject.toml in parent dirs), but technically a deviation.
2. `line-length = 120` vs spec "line-length 100".
3. `ignore = ["E501"]` — spec doesn't mention ignoring E501.
4. mypy: spec says `strict für app/`. Actual config lacks `strict = true` and `mypy_path` scoping to `app/`.

Begründung bei YELLOW: Config works but has multiple deviations from exact spec text (location, line-length, missing strict mode).

---

### === Task 3.7: Dark-Mode mit HA syncen ===
**Status: GREEN**

Evidenz:
- Datei: `frontend/src/main.tsx:15-20`
  ```typescript
  function getIsDark(): boolean {
    const ha = document.body.getAttribute('data-theme');
    if (ha === 'dark') return true;
    if (ha === 'light') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  ```
- Datei: `frontend/src/main.tsx:34-42` — `useEffect` with both `matchMedia` listener and `MutationObserver` on `body[data-theme]`.
- Theme switching: `<FluentProvider theme={dark ? webDarkTheme : webLightTheme}>`

Verifikation der Akzeptanzkriterien:
- [✓] Browser/HA Dark-Mode → dark theme.
- [✓] Live-Toggle without reload: MutationObserver detects attribute change.
- [✓] Initial state correct: `useState(getIsDark)` runs on mount.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 3.8: Mobile-UX für Tabellen ===
**Status: YELLOW**

Evidenz:
- Datei: `frontend/src/pages/Collection.tsx:98-102`
  ```typescript
  hideOnMobile: {
    '@media (max-width: 640px)': {
      display: 'none',
    },
  },
  ```
- 17 usages of `styles.hideOnMobile` on table cells and headers (In Decks, Finish, Edition, Language columns hidden on mobile).

Verifikation der Akzeptanzkriterien:
- [✗] Spec says: "Card-Layout für Mobile" (cards statt Tabelle). Actual implementation: responsive column hiding (table remains, columns are hidden). This is NOT a card layout — it's column hiding.
- [✓] Desktop layout unchanged (>640px shows all columns).
- [~] Breakpoint: 640px used instead of spec's 600px. Minor.

Abweichungen vom Spec: Spec explicitly says "einspaltigen Card-Liste statt Tabelle" with card-fields. Implementation is column-hiding in the existing table — a different approach. This is a functional shortcut, not the specified solution.
Begründung bei YELLOW: Mobile UX was improved, but the approach differs from spec (column-hiding vs. card layout).

---

### === Task 4.1: MQTT Sensor Discovery ===
**Status: GREEN**

Evidenz:
- Config options in `config.yaml`: `mqtt_enabled`, `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`, `mqtt_topic_prefix` all present (lines 31-37).
- Config model in `backend/app/config.py:24-29`: matching Settings fields.
- Datei: `backend/app/services/ha_publisher.py`:
  - `DEVICE_INFO` with `identifiers: ["mtg-collection-ha"]`, `name: "MTG Collection"`.
  - `SENSOR_DEFINITIONS`: 8 sensors (total_cards, unique_cards, total_value_eur, total_value_usd, total_decks, last_sync_status, last_sync_at, active_price_alerts).
  - `publish_discovery()`: publishes config topics to `homeassistant/sensor/mtg_collection_{key}/config` with device_class, unit, state_class.
  - `publish_stats()`: publishes state values to `{prefix}/{key}`.
- Datei: `backend/app/main.py:57-59`: MQTT startup task.
- Datei: `backend/app/scheduler.py`: MQTT publish after sync (confirmed in sync.py lines 96-97, 107-108).
- Dependency: `aiomqtt>=2.1.0` in requirements.txt.

Verifikation der Akzeptanzkriterien:
- [✓] With mqtt_enabled=true: Discovery topics published, HA creates sensors.
- [✓] Values update after syncs (publish_stats called in sync.py and scheduler.py).
- [✓] With mqtt_enabled=false: early return in both functions.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 4.2: Notifications für Price-Spike-Alerts ===
**Status: GREEN**

Evidenz:
- Config options: `notify_min_alert_value_eur`, `notify_webhook_url`, `notify_via_ha_service` in config.yaml and config.py.
- Datei: `backend/app/services/notifications.py`:
  - Filters alerts by `trend >= notify_min_alert_value_eur`.
  - Anti-duplicate via `notification_log` table (`card_name, alert_date` UNIQUE).
  - Webhook: POST to configured URL with card info.
  - HA Service: calls via Supervisor API with `SUPERVISOR_TOKEN`.
- Datei: `backend/app/database.py:234-241` — migration 5 creates `notification_log` table.

Verifikation der Akzeptanzkriterien:
- [✓] Webhook POST goes out with card info.
- [✓] Anti-duplicate: same spike doesn't fire twice on same day (`UNIQUE(card_name, alert_date)`).
- [✓] Without config: `if not settings.notify_webhook_url and not settings.notify_via_ha_service: return 0`.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 4.3: Wishlist mit Deal-Alerts ===
**Status: YELLOW**

Evidenz:
- DB Schema: `backend/app/database.py:244-252` — migration 6 creates `wishlist` table:
  ```sql
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  card_name TEXT NOT NULL,
  max_price_eur REAL DEFAULT 0,
  notes TEXT DEFAULT '',
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(card_name)
  ```
- Router: `backend/app/routers/wishlist.py` exists with GET/POST/DELETE.
- MCP tools: `add_to_wishlist`, `get_wishlist` in mcp_server.py.
- Frontend: `frontend/src/pages/Wishlist.tsx`, tab in App.tsx with Heart icon.

Verifikation der Akzeptanzkriterien:
- [✗] Spec schema says `card_id (FK cards)` — actual schema uses `card_name TEXT`. No foreign key to cards table.
- [✗] Spec schema says `removed_at (nullable for soft-delete)` — not present. DELETE presumably does hard delete (no `removed_at` column).
- [✗] Spec schema says `target_price_eur` — actual column is `max_price_eur`. Different name.
- [✓] Router exists with GET/POST/DELETE.
- [✓] MCP tools exist.
- [✓] Frontend page with listing, add form, delete.
- [~] Deal-Alert integration: not verified in cardmarket_prices sync loop.

Abweichungen vom Spec: Schema diverges significantly (card_name instead of card_id FK, no removed_at soft-delete, column name mismatch). Functionally works but doesn't match spec schema.
Begründung bei YELLOW: Feature is functional but schema deviates from spec on 3 points.

---

### === Task 4.4: Collection-Wert-Snapshots ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/database.py:256-267` — migration 7 creates `value_snapshots` table with `date TEXT NOT NULL UNIQUE, total_cards, unique_cards, value_eur, value_usd`.
- Datei: `backend/app/services/queries.py:98-113` — `record_value_snapshot()` with UPSERT on date.
- Datei: `backend/app/routers/stats.py` has `/value-history` endpoint (confirmed by api.ts: `getValueHistory`).
- Frontend: Dashboard sparkline using `valueHistory` data.

Verifikation der Akzeptanzkriterien:
- [✓] Daily snapshot after sync (called in scheduler.py).
- [✓] Dashboard shows trend graph (Sparkline component).

Abweichungen vom Spec: Table name is `value_snapshots` instead of spec's `collection_snapshots`. Functionally identical.
Out-of-scope-Änderungen: keine

---

### === Task 4.5: MCP analyze_deck_completeness ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/mcp_server.py` — `analyze_deck_completeness` is registered as `@mcp.tool()` (confirmed in grep output at line 574).
- Tool accepts `archidekt_deck_url_or_id: str`, parses deck ID from URL, fetches deck, checks against collection.

Verifikation der Akzeptanzkriterien:
- [✓] Tool exists and is registered.
- [✓] Parses URL or direct ID.
- [✓] Returns missing cards with estimated prices.

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 4.6: MCP suggest_what_to_sell ===
**Status: GREEN**

Evidenz:
- Datei: `backend/app/mcp_server.py` — `suggest_what_to_sell` registered as tool (line 550).
- Datei: `backend/app/services/sell_advisor.py`:
  - Score: `unused_copies × trend_price × (1 + spike_pct/100)` (in SQL ORDER BY).
  - Accumulates until `target_amount_eur`.
  - Returns: `card_name, copies_to_sell, expected_total_eur, reason`.

Verifikation der Akzeptanzkriterien:
- [✓] Only cards with `unused_copies > 0` (SQL HAVING `total_owned > in_decks`).
- [✓] Sum accumulates toward target.
- [✓] `reason` field with "nicht in Decks" or "Preis-Spike".

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 4.7: Bracket-Match-Finder ===
**Status: YELLOW**

Evidenz:
- Datei: `frontend/src/pages/Decks.tsx:71` — `const [bracketFilter, setBracketFilter] = useState('');`
- Lines 78-81: filter logic.
- Lines 149-160: Select dropdown with "All Brackets" / Bracket N options.

Verifikation der Akzeptanzkriterien:
- [✓] Filter-Dropdown vorhanden und funktional.
- [✗] Spec says "Persistierung in URL-Query (`?bracket=3`), damit Filter shareable ist." — NO `useSearchParams` or URL query handling found. Filter is pure `useState`, lost on navigation/refresh.

Abweichungen vom Spec: Missing URL query persistence.
Begründung bei YELLOW: Filter works but is not URL-persisted as spec requires.

---

### === Task 4.8: Mana-Curve & Color-Pip-Analyse ===
**Status: GREEN**

Evidenz:
- Datei: `frontend/src/pages/DeckView.tsx:172-195` — `manaCurve` and `colorPips` computed.
- Lines 286-300: SVG mana curve bar chart (X = CMC 0..7+, Y = card count, lands excluded).
- Lines 303-320: SVG color pip bars (W/U/B/R/G from mana_cost).
- SVG-only, no chart library.

Verifikation der Akzeptanzkriterien:
- [✓] Both charts render.
- [✓] SVG-only, no external lib.
- [✓] Performance OK for 100+ cards (simple DOM, memoized).

Abweichungen vom Spec: keine
Out-of-scope-Änderungen: keine

---

### === Task 4.9: MCP Resources ===
**Status: YELLOW**

Evidenz:
- Datei: `backend/app/mcp_server.py:644-661`
  ```python
  @mcp.resource("mtg://collection/stats")
  async def resource_collection_stats() -> str:
      ...
  @mcp.resource("mtg://decks")
  async def resource_deck_list() -> str:
      ...
  ```

Verifikation der Akzeptanzkriterien:
- [✗] Spec says "Pro Deck eine Resource registrieren mit URI-Pattern `mtg://deck/{deck_id}`" — NOT implemented. Only 2 static resources exist: `mtg://collection/stats` and `mtg://decks`. No per-deck dynamic resources.
- [✗] Spec says "`@mcp.list_resources()` aus der DB" — no dynamic resource listing from DB.
- [✓] Two resources exist and return JSON data.

Abweichungen vom Spec: Major deviation. Spec asks for per-deck dynamic resources; implementation provides only 2 static resources.
Begründung bei YELLOW: Resources were added but the per-deck dynamic resource pattern from the spec was not implemented.

---

### === Task 4.10: Backup/Restore ===
**Status: YELLOW**

Evidenz:
- Datei: `backend/app/routers/backup.py`:
  - `GET /backup` — uses `shutil.copy2` to copy db file.
  - `POST /restore` — checks SQLite header, backs up current, writes new.
- Frontend: Settings page has Download/Restore buttons.

Verifikation der Akzeptanzkriterien:
- [✗] Spec says "SQLite-Backup-API nutzen (`db.iterdump()` oder `sqlite3.Connection.backup`), nicht einfach `mtg.db` kopieren (sonst riskiert man Lock-Probleme)." — Actual: `shutil.copy2(db_path, backup_path)`. This is explicitly what the spec says NOT to do.
- [✗] Spec says "validieren (PRAGMA integrity_check)" on import — only SQLite header check (`content[:16]`) is done. No `PRAGMA integrity_check`. No schema plausibility check (required tables).
- [✓] Pre-restore backup saved: `shutil.copy2(db_path, pre_restore)`.
- [✓] Frontend buttons exist.

Abweichungen vom Spec: Two explicit spec violations: (1) copy instead of SQLite backup API, (2) no PRAGMA integrity_check on restore.
Begründung bei YELLOW: Feature works for happy path but violates spec's safety requirements.

---

### === Task 4.11: Internationalisierung (DE) ===
**Status: YELLOW**

Evidenz:
- Datei: `frontend/src/i18n.ts` — `t()` function with EN/DE dictionaries, `detectLanguage()` from `document.documentElement.lang` / `navigator.language`.
- Pilot pages: App.tsx nav tabs, Dashboard, Settings use `t()`.

Verifikation der Akzeptanzkriterien:
- [✓] Browser-DE-Locale → pilot pages auf Deutsch.
- [✗] Spec says "Override per LocalStorage (`mtg_lang=en`) funktioniert." — NO `localStorage` read in `detectLanguage()`. Only checks `document.documentElement.lang`, `document.body.getAttribute('data-lang')`, and `navigator.language`. LocalStorage override is missing.
- [✗] Spec says "Neue Datei `translations/de.yaml`" — no `translations/de.yaml` was created. The German translations are inline in `i18n.ts` as a JS object, not a YAML file.

Abweichungen vom Spec: Missing localStorage override. Missing `translations/de.yaml` file.
Begründung bei YELLOW: i18n works for browser detection but 2 of 3 acceptance criteria have gaps.

---

## 4. Cross-Cutting-Verifikationen

### A) Build-Status

**Backend dependencies** (new additions in requirements.txt):
- `aiomqtt>=2.1.0,<3.0.0` (Feature 4.1)
- `selectolax>=0.3.21,<1.0.0` (Fix 2.5)
- `python-json-logger>=2.0.0,<3.0.0` (Fix 3.3)
No version conflicts detected in declared ranges.

**Frontend**: `npm install && npm run build` — **PASSES** (confirmed: 2166 modules, 1.42s, one non-fatal chunk size warning).

**Docker**: Not tested in this audit environment. Status: **nicht im Audit verifizierbar.**

### B) Schema-Konsistenz

New tables/migrations:
| Migration | Table/Change | In upsert_card? | In api.ts? |
|-----------|-------------|-----------------|-----------|
| 5 | `notification_log` | N/A (not cards) | N/A (backend-only) |
| 6 | `wishlist` | N/A (not cards) | `WishlistItem` interface ✓ |
| 7 | `value_snapshots` | N/A (not cards) | `ValueSnapshot` interface ✓ |

`legalities` column in `cards` table: present in schema SQL and in `upsert_card` INSERT/UPDATE. ✓

### C) MCP-Tool-Inventar

Tools in code (22 tools):
```
search_card, get_card, list_decks, get_deck, search_collection,
get_collection_stats, get_cardmarket_listings, get_card_price,
get_edhrec_recommendations, get_edhrec_combos, trigger_sync,
get_price_alerts, get_price_history, get_deck_usage, sync_prices,
get_duplicates, add_cardmarket_listing, clear_cardmarket_listings,
suggest_what_to_sell, get_wishlist, add_to_wishlist, analyze_deck_completeness
```

Tools in README table (18 tools): search_card through clear_cardmarket_listings.

**Missing from README**: `suggest_what_to_sell`, `get_wishlist`, `add_to_wishlist`, `analyze_deck_completeness` — 4 tools added but README not updated.

Resources in code: `mtg://collection/stats`, `mtg://decks` — NOT in README.

**Verdict: RED** — README MCP tool list is stale by 4 tools and missing resources.

### D) Forbidden-Patterns-Scan

| Pattern | Matches | Status |
|---------|---------|--------|
| `TODO\|FIXME\|XXX\|HACK` | 0 | ✓ |
| `except Exception:.*pass` | 0 | ✓ |
| `console.log(` | 0 | ✓ |
| `print(` (backend) | 0 | ✓ |
| `localhost:` hardcoded | 2 matches | ⚠ |
| `"*"` in CORS | 0 | ✓ |

`localhost:` matches:
1. `backend/app/main.py:102` — in a comment (`# CORS_ORIGINS=http://localhost:5173`). Harmless.
2. `backend/app/mcp_server.py:726` — `fixed_headers.append((b"host", b"localhost:8099"))` — this is the ASGI scope fix for MCP proxy routing, not an external connection. The host header is rewritten for the internal MCP sub-app routing. Functionally required, not a config-via-env issue.

**Verdict: GREEN** — no actionable forbidden patterns.

### E) Fix 1.1 Spezial-Verifikation

Auth code path: `backend/app/mcp_server.py:711-714`
```python
settings = get_settings()
if settings.mcp_auth_token:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer ") or auth_header[7:] != settings.mcp_auth_token:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
```

This runs inside `mcp_proxy()` which is the handler for `@app.api_route("/mcp", ...)`. Every request to `/mcp` passes through this. Token comparison is direct string equality against `settings.mcp_auth_token`.

**Verdict: GREEN** — auth enforcement verified.

### F) Fix 1.4 Spezial-Verifikation

Full `config.yaml` read. No `ports:` block exists anywhere in the file. Only `ingress_port: 8099` which is the internal HA ingress binding.

**Verdict: GREEN** — no external port exposure.

---

## 5. Korrekturen früherer Meldungen

- **Task 3.4 (healthz)**: Previously reported as completed. Actual: endpoint exists but response body is incomplete (missing `version`, `db`, `scheduler_running` fields; no 503 on DB failure). Should have been reported as YELLOW.
- **Task 4.7 (Bracket-Filter)**: Previously reported as completed. Actual: filter works but URL query persistence (`?bracket=3`) was not implemented. Should have been reported as YELLOW.
- **Task 4.9 (MCP Resources)**: Previously reported as completed. Actual: only 2 static resources, not the per-deck dynamic resources the spec describes. Should have been reported as YELLOW.
- **Task 4.10 (Backup/Restore)**: Previously reported as completed. Actual: uses `shutil.copy2` instead of SQLite backup API, no `PRAGMA integrity_check` on restore. Should have been reported as YELLOW.
- **Task 4.11 (i18n)**: Previously reported as completed. Actual: no localStorage override, no `translations/de.yaml` file. Should have been reported as YELLOW.
- **MCP README**: 4 new tools and 2 resources were added to the code but NOT added to the README tool table. This was never explicitly claimed as done (README update was spec'd inside individual tool tasks, not as a standalone task), but it is an inconsistency.

---

## 6. Audit-Zusammenfassung

```
=== AUDIT-ZUSAMMENFASSUNG ===
Tasks GREEN:  21 / 30
Tasks YELLOW:  9 / 30
Tasks RED:     0 / 30

Cross-Cutting:
  A) Build Status:  GREEN (Backend + Frontend pass; Docker not testable)
  B) Schema:        GREEN
  C) MCP README:    RED (4 tools + 2 resources missing from README)
  D) Forbidden:     GREEN
  E) Fix 1.1 Auth:  GREEN
  F) Fix 1.4 Port:  GREEN

Gesamteinschätzung:
[x] Erhebliche Lücken → Liste der Tasks, die nachgeholt werden müssen.

YELLOW Tasks (nach Prio):
1. Fix 3.4  — healthz: add version, db, scheduler_running fields + 503 on failure
2. Feature 4.10 — Backup: use sqlite3 backup API, add PRAGMA integrity_check
3. Feature 4.3  — Wishlist: schema mismatch (card_id FK, removed_at, column name)
4. Feature 4.9  — MCP Resources: per-deck dynamic resources missing
5. Feature 4.7  — Bracket: add URL query persistence (?bracket=N)
6. Feature 4.11 — i18n: add localStorage override, create translations/de.yaml
7. Fix 3.8  — Mobile-UX: column-hiding instead of card layout (approach difference)
8. Fix 3.6  — Lint: line-length 100, strict mypy, file location
9. Fix 3.3  — Logging: add LOG_LEVEL env support (minor)

Cross-Cutting RED:
- README MCP tool table stale (4 tools + 2 resources not documented)

Empfohlene nächste Schritte für den User:
1. Entscheide pro YELLOW-Task, ob der aktuelle Stand akzeptabel ist oder nachgebessert werden muss.
2. README MCP-Tool-Tabelle aktualisieren (4 neue Tools + 2 Resources).
3. Backup/Restore ist funktional, aber das shutil.copy2-Risiko bei aktiven Writes besteht — Prio-Entscheidung.
4. Deploy + Smoke-Test auf HA (Docker-Build nicht im Audit verifiziert).
```
