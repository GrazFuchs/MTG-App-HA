# Handoff: Sprint 32 — MTG Dashboard in Home Assistant

**For the agent working in the Home Assistant config repo.**

The add-on side is finished as of **v0.31.0**. Everything below already exists
and is published over MQTT Discovery — your job is the HA-side presentation
layer: dashboard views, a package with automations/scripts, and notifications.

Nothing in this document needs changes to the add-on. If you find you *do* need
one, note it rather than working around it.

---

## 1. What you are working with

The add-on `mtg-collection-ha` publishes everything via **MQTT Discovery** under
two devices:

- **MTG Collection** — all sensors (read-only)
- **MTG Game Logger** — the input form (read/write)

Plus dynamic per-item entities: one sensor per active wishlist item and one per
recently played deck.

### Availability

All entities reference `mtg-collection/status` (retained, `online` / `offline`,
with a Last Will). They go **unavailable** when the add-on is down — so guard
templates with `has_value()` / `states(...) not in ['unknown','unavailable']`
rather than assuming a number is always there.

### Entity inventory

| Entity | Unit | device_class | state_class | Attributes |
|---|---|---|---|---|
| `sensor.mtg_total_cards` | – | – | measurement | |
| `sensor.mtg_unique_cards` | – | – | measurement | |
| `sensor.mtg_total_value_eur` | EUR | monetary | total | |
| `sensor.mtg_total_value_usd` | USD | monetary | total | |
| `sensor.mtg_total_decks` | – | – | measurement | |
| `sensor.mtg_last_sync_status` | – | – | – | |
| `sensor.mtg_last_sync_at` | – | timestamp | – | |
| `sensor.mtg_ingress_url` | – | – | – | one link per UI route (see §2.3) |
| `sensor.mtg_active_price_alerts` | – | – | measurement | |
| `sensor.mtg_spending_30d` | EUR | monetary | total | |
| `sensor.mtg_spending_30d_value` | EUR | monetary | total | |
| `sensor.mtg_acquired_count_30d` | – | – | measurement | |
| `sensor.mtg_listings_underpriced` | – | – | measurement | |
| `sensor.mtg_listings_overpriced` | – | – | measurement | |
| `sensor.mtg_listings_fair` | – | – | measurement | |
| `sensor.mtg_inbox_pending` | – | – | measurement | `items`, `suggestions_scanned`, `suggestions_truncated` |
| `sensor.mtg_inbox_needs_sell` | – | – | measurement | |
| `sensor.mtg_inbox_needs_keep` | – | – | measurement | |
| `sensor.mtg_inbox_pending_value_eur` | EUR | monetary | total | |
| `sensor.mtg_inbox_oldest_age_days` | d | – | measurement | |
| `sensor.mtg_inbox_decided_30d` | – | – | measurement | `by_state` |
| `binary_sensor.mtg_inbox_has_pending` | – | – | – | |
| `sensor.mtg_sell_candidates` | – | – | measurement | `items` |
| `sensor.mtg_sell_potential_eur` | EUR | monetary | total | |
| `sensor.mtg_duplicates_surplus_cards` | – | – | measurement | |
| `sensor.mtg_duplicates_surplus_value_eur` | EUR | monetary | total | |
| `sensor.mtg_unlisted_value_eur` | EUR | monetary | total | `items` |
| `sensor.mtg_games_30d` | – | – | measurement | |
| `sensor.mtg_winrate_30d` | % | – | measurement | `wins`, `losses`, `draws`, `games` |
| `sensor.mtg_last_game_at` | – | timestamp | – | |
| `sensor.mtg_last_game_result` | – | – | – | `deck_name` |
| `sensor.mtg_signals_buy` * | – | – | measurement | `items` |
| `sensor.mtg_signals_sell` * | – | – | measurement | `items` |

\* only exist while the optional MTGStocks integration is enabled in the add-on
options. Build the view so it degrades gracefully when they are missing.

**Dynamic entities**

- `sensor.mtg_wishlist_<item_id>` — state = current price in EUR; attributes
  `card_name`, `set_code`, `is_foil`, `target_price_eur`, `current_price_eur`,
  `is_deal`, `delta_pct`, `priority`, `is_ordered`, `status`. Appear and
  disappear as items are added/acquired — do **not** hardcode ids; use an
  auto-entities-style filter or a template over the MQTT device.
- `sensor.mtg_deck_<deck_id>_winrate` — state = win rate in %; attributes
  `games`, `wins`, `losses`, `draws`, `last_played`, `deck_name`. Exists only
  for decks played in the last 90 days.

### Attribute list shapes

Every `items` attribute is a **list of at most 10** entries, already sorted by
relevance. The states are exact counts, so `sensor.mtg_inbox_pending` can read
`42` while `items` holds 10 — say "showing 10 of 42" in the UI rather than
implying the list is complete.

```yaml
# sensor.mtg_inbox_pending → items[]
event_id, card_name, set_code, quantity, is_foil, suggestion, reason, price_eur, age_days
# suggestion is one of: keep | sold_new | swap

# sensor.mtg_sell_candidates → items[]
card_name, set_name, copies_to_sell, trend_price_eur, expected_total_eur, spike_pct, reason

# sensor.mtg_unlisted_value_eur → items[]
card_name, set_code, is_foil, surplus_copies, value_eur

# sensor.mtg_inbox_decided_30d → by_state: {"keep": 12, "sold_new": 3, ...}
```

### The game-logger form

The add-on owns these entities — **do not build `input_*` helpers for this**,
and do not try to keep a separate deck list in sync. The dropdown is rebuilt
from the database on every sync.

| Entity | Type | Range |
|---|---|---|
| `select.mtg_log_deck` | select | deck names; `—` means "nothing selected" |
| `select.mtg_log_result` | select | `win` / `loss` / `draw` |
| `number.mtg_log_pod_size` | number | 1–8 |
| `switch.mtg_log_on_play` | switch | |
| `number.mtg_log_mulligans` | number | 0–10 |
| `number.mtg_log_missed_land_drops` | number | 0–50 |
| `number.mtg_log_turns` | number | 0–100 |
| `text.mtg_log_opponents` | text | ≤ 255 chars |
| `text.mtg_log_notes` | text | ≤ 255 chars |
| `button.mtg_log_submit` | button | writes the game |
| `sensor.mtg_log_status` | sensor | outcome of the last submit |

Pressing the button writes the game, clears the form, refreshes the deck
sensors and sets `sensor.mtg_log_status` to e.g.
`Logged win with Atraxa on 2026-07-22` or `Error: No deck selected`.

A plain `type: entities` card is enough — no templating needed.

### Callable services (MQTT)

Publish JSON to `mtg-collection/service/<cmd>`; the reply lands on
`mtg-collection/service/<cmd>/response`.

| Command | Payload |
|---|---|
| `trigger_sync` | `{}` |
| `sync_prices` | `{}` |
| `add_to_wishlist` | `{"card_name": "Sol Ring", "priority": 4}` |
| `mark_acquired` | `{"item_id": 42, "source": "whatnot", "paid_price_eur": 1.20}` |
| `log_game` | `{"deck": "Atraxa", "result": "win", "turns": 9, …}` |
| `triage` | `{"event_id": 42, "action": "keep"}` |
| `create_listing` | `{"card_name": "Sol Ring", "price": 1.5, "quantity": 2}` |

Notes:

- `log_game` takes `deck` (name, case-insensitive, exact then unique substring)
  or `deck_id`. An ambiguous name is **not** guessed at — the response carries
  `error` and `candidates`. Other fields: `played_at` (ISO date, default today),
  `pod_size`, `on_play`, `mulligans`, `missed_land_drops`, `turns`, `opponents`,
  `what_worked`, `what_didnt`, `notes`.
- `triage` actions: `keep`, `sold_new`, `swap`, `dismiss`. Selling requires
  `listing_price_eur`. `source` defaults to `other`.
- Responses are **not** retained. If you want the outcome visible in HA, either
  subscribe with an MQTT trigger or read `sensor.mtg_log_status` (form only).

### Update cadence

| Trigger | What refreshes |
|---|---|
| Daily scheduled sync + add-on start | everything |
| Manual sync via UI or `trigger_sync` | stats, sell, inbox, deck dropdown |
| Cardmarket price sync | wishlist sensors, stats |
| A triage decision | inbox sensors (debounced 5 s) |
| A game logged (UI, service or form) | deck performance sensors |

So the inbox and selling numbers are **not** live to the second; a dashboard
that implies real-time would be misleading.

---

## 2. What to build

### 2.1 Dashboard (`ui-lovelace` view or a dedicated dashboard)

Suggested structure — adapt to the conventions already used in this config
(card library, Mushroom vs core cards, theme, existing view layout):

1. **Overview row** — chips/tiles: total cards, collection value, inbox pending,
   sell potential, active price alerts, last sync. Badge the inbox chip off
   `binary_sensor.mtg_inbox_has_pending`.
2. **Inbox** — a list from `sensor.mtg_inbox_pending`'s `items`, showing card,
   set, suggestion and price, with per-row Keep/Sell actions calling the
   `triage` service (see 2.2). Include the "showing 10 of N" caveat.
3. **Selling** — `sensor.mtg_sell_potential_eur` prominently, the
   `sell_candidates` `items` as a table, and `sensor.mtg_unlisted_value_eur` as
   the "not yet listed" to-do with its own list. Listing health
   (`underpriced` / `overpriced` / `fair`) fits well as a small bar or gauge row.
4. **Log a game** — the entities card from the form above, plus
   `sensor.mtg_log_status` as feedback.
5. **Deck performance** — `sensor.mtg_winrate_30d` and `sensor.mtg_games_30d`,
   the last game, and an auto-populated list of `sensor.mtg_deck_*_winrate`.
6. **History** — a `statistics-graph` card over `sensor.mtg_total_value_eur` and
   `sensor.mtg_total_cards`. Both carry a `state_class`, so long-term statistics
   already exist; no template sensors or recorder tweaks needed.

### 2.2 Package (`packages/mtg.yaml` or wherever this config keeps them)

- **Script `mtg_triage`** — fields `event_id`, `action`, optional
  `listing_price_eur`; publishes to `mtg-collection/service/triage`. Used by the
  dashboard buttons and the notification actions.
- **Script `mtg_log_game`** — thin wrapper over `log_game` for voice/automations.
- **Automation: new inbox cards → actionable notification** with Keep / Sell
  buttons, handled by a second automation on `mobile_app_notification_action`
  that calls `mtg_triage`. A worked example is in
  [`docs/ha-integration.md`](ha-integration.md) — treat it as a starting point,
  not as house style.
- **Automation: weekly selling report** — Sunday evening, only when
  `sensor.mtg_sell_potential_eur` is above a threshold.
- **Automation: inbox left unattended** — `sensor.mtg_inbox_oldest_age_days`
  above ~14.
- **Automation: add-on offline** — `mtg-collection/status` reads `offline` for
  more than a few minutes. Nothing else will tell you the sensors are stale.
- **Voice**: `mtg-collection/voice/sentences.yaml` in the add-on repo ships
  intents including `HassMTGLogWin` / `HassMTGLogLoss` with a `{deck}` slot.
  Copy it to `custom_sentences/en/mtg_collection.yaml` and add the matching
  `intent_script` entries that publish to `log_game`.

### 2.3 Deep links into the add-on UI

The add-on publishes its own ingress link, so **no slug has to be hardcoded**:

| Entity | State | Attributes |
|---|---|---|
| `sensor.mtg_ingress_url` | `/api/hassio_ingress/<token>` | one link per UI route |

Attribute keys: `dashboard`, `decks`, `collection`, `inbox`, `duplicates`,
`cardmarket`, `wishlist`, `settings` — each already a complete path.

```yaml
tap_action:
  action: url
  url_path: "{{ state_attr('sensor.mtg_ingress_url', 'inbox') }}"
```

The sensor is `unknown` when the add-on runs outside a Supervisor environment
(standalone Docker), so guard cards with `has_value()` if that is a possibility
here. The ingress token changes when the add-on is reinstalled — reading it
from the sensor rather than copying it keeps the dashboard working.

---

## 3. Constraints worth knowing before you start

- **Entity ids are pinned via `object_id`** in the discovery payload, so the ids
  above hold for a fresh install. If this HA instance already had the older
  sensors registered, HA keeps the ids from its registry — verify in
  Settings → Devices & Services → MQTT before writing them into cards.
- **HA state limit is 255 characters.** All lists live in attributes, never in
  states. Don't build template sensors that concatenate `items` into a state.
- **`sensor.mtg_last_game_at` has no state before the first logged game** — the
  add-on deliberately publishes nothing instead of an empty payload, so it reads
  `unknown`. Handle that in cards.
- **MTGStocks sensors may not exist.** Conditional cards, not hardcoded rows.
- **The per-deck sensors come and go** with the 90-day activity window. Use
  filtered/auto-populated cards, not a fixed entity list.
- **Do not re-implement add-on logic in templates.** Sell candidates, surplus
  values and triage suggestions are computed in the add-on and exposed ready to
  render; a second definition in Jinja will drift.

---

## 4. Reference

- Full integration guide, all topics and worked examples:
  [`docs/ha-integration.md`](ha-integration.md) in the add-on repo.
- Sprint history and the reasoning behind the entity design:
  [`docs/ha-dashboard-sprints.md`](ha-dashboard-sprints.md).
- Verify what is actually on the broker:

  ```bash
  mosquitto_sub -h <broker> -t 'homeassistant/+/mtg_+/config' -v
  mosquitto_sub -h <broker> -t 'mtg-collection/#' -v
  ```
