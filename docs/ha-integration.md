# Home Assistant Integration Guide

This guide covers all the ways **MTG Collection Manager** integrates deeply with Home Assistant:

- [Availability](#availability)
- [Game Logger Form](#game-logger-form)
- [Wishlist Item Sensors](#wishlist-item-sensors)
- [Aggregate Sensors (Spending, Listing Health)](#aggregate-sensors)
- [MQTT-Based Service Registry](#mqtt-based-service-registry)
- [Persistent Notifications with Deep Links](#persistent-notifications-with-deep-links)
- [Voice Integration (HA Assist)](#voice-integration-ha-assist)
- [Example Automations](#example-automations)
- [Example Dashboard Cards](#example-dashboard-cards)
- [Troubleshooting](#troubleshooting)

---

## Availability

The add-on keeps one MQTT connection open and reports its state on
`mtg-collection/status` (retained):

| Payload | Meaning |
|---------|---------|
| `online` | Published on every (re)connect |
| `offline` | Published on a graceful stop, or by the broker via Last Will if the add-on dies |

Every entity below references this topic, so all MTG entities show as
**unavailable** in HA while the add-on is down instead of keeping their last value.

```bash
mosquitto_sub -h <mqtt_host> -t 'mtg-collection/status' -C 1
```

---

## Game Logger Form

The add-on publishes its own input entities under a separate **MTG Game Logger**
device, so logging a game needs no HA helpers, no `input_*` entities and no
templating in the dashboard:

| Entity | Type | Notes |
|--------|------|-------|
| `select.mtg_log_deck` | select | Options come from the database and follow every sync |
| `select.mtg_log_result` | select | `win` / `loss` / `draw` |
| `number.mtg_log_pod_size` | number | 1–8 |
| `switch.mtg_log_on_play` | switch | |
| `number.mtg_log_mulligans` | number | 0–10 |
| `number.mtg_log_missed_land_drops` | number | 0–50 |
| `number.mtg_log_turns` | number | 0–100 |
| `text.mtg_log_opponents` | text | max 255 characters |
| `text.mtg_log_notes` | text | max 255 characters |
| `button.mtg_log_submit` | button | Writes the game |
| `sensor.mtg_log_status` | sensor | Outcome of the last submit |

Pressing the button makes the add-on read the values it is already holding,
write the game, clear the form and update the deck performance sensors.
`sensor.mtg_log_status` then reads e.g. *"Logged win with Atraxa on 2026-07-22"*
— or why it did not work.

Field values are stored in the database, so a half-filled form survives an
add-on restart. Numbers outside their range are clamped; a value HA cannot
send meaningfully (a select option that no longer exists) is rejected, and the
entity keeps its previous value with a note on the status sensor.

"What worked" / "what didn't" are deliberately not part of the form — long
free text belongs in the web UI. `text` entities are capped at 255 characters
by HA, below what the API accepts for opponents (300) and notes (1000).

### Dashboard card

```yaml
type: entities
title: Log a game
entities:
  - entity: select.mtg_log_deck
  - entity: select.mtg_log_result
  - entity: number.mtg_log_pod_size
  - entity: switch.mtg_log_on_play
  - entity: number.mtg_log_mulligans
  - entity: number.mtg_log_turns
  - entity: text.mtg_log_opponents
  - entity: text.mtg_log_notes
  - entity: button.mtg_log_submit
  - entity: sensor.mtg_log_status
```

For scripts and voice, the `log_game` MQTT service is usually the better fit —
see [MQTT-Based Service Registry](#mqtt-based-service-registry).

---

## Wishlist Item Sensors

Every active wishlist item (status `wanted` or `not_received`) is published as an individual HA sensor via MQTT Discovery.

### Topic structure

| Purpose | Topic |
|---------|-------|
| Discovery config | `homeassistant/sensor/mtg_wishlist_{id}/config` |
| State JSON | `mtg-collection/wishlist/{id}/state` |

### State JSON fields

```json
{
  "card_name": "Sol Ring",
  "set_code": "C21",
  "is_foil": false,
  "target_price_eur": 1.20,
  "current_price_eur": 0.95,
  "is_deal": true,
  "delta_pct": -20.83,
  "priority": 4,
  "is_ordered": false,
  "status": "wanted"
}
```

The sensor **state** is `current_price_eur` (EUR). All other fields are available as **entity attributes** (`json_attributes_topic` points to the same state topic).

### When sensors are published

| Event | Action |
|-------|--------|
| Wishlist item added | New Discovery + State published |
| Wishlist item updated (PATCH) | State re-published |
| Daily Cardmarket price sync | All active item states re-published |
| Item acquired / deleted / dropped | Discovery topic cleared (entity removed from HA) |

### Verify via mosquitto

```bash
mosquitto_sub -h <mqtt_host> -t 'homeassistant/sensor/mtg_wishlist_+/config' -C 5
mosquitto_sub -h <mqtt_host> -t 'mtg-collection/wishlist/+/state' -C 5
```

---

## Aggregate Sensors

These sensors are published once daily after the scheduled sync (and on startup):

| Sensor entity | Description | Unit |
|---------------|-------------|------|
| `sensor.mtg_total_cards` | Total physical card count | – |
| `sensor.mtg_unique_cards` | Distinct Scryfall cards | – |
| `sensor.mtg_total_value_eur` | Collection market value | EUR |
| `sensor.mtg_active_price_alerts` | Cards with >30 % price spike | – |
| `sensor.mtg_spending_30d` | Amount paid for acquisitions (last 30 days) | EUR |
| `sensor.mtg_spending_30d_value` | Current market value of those acquisitions | EUR |
| `sensor.mtg_acquired_count_30d` | Number of cards acquired (last 30 days) | – |
| `sensor.mtg_listings_underpriced` | Cardmarket listings below trend (−15 %) | – |
| `sensor.mtg_listings_overpriced` | Cardmarket listings above trend (+15 %) | – |
| `sensor.mtg_listings_fair` | Cardmarket listings within the fair band | – |

### Inbox / acquisition triage

| Sensor entity | Description | Unit |
|---------------|-------------|------|
| `sensor.mtg_inbox_pending` | Cards waiting for a triage decision | – |
| `sensor.mtg_inbox_needs_sell` | Of those, ones the advisor suggests selling (`sold_new`/`swap`) | – |
| `sensor.mtg_inbox_needs_keep` | Of those, ones the advisor suggests keeping | – |
| `sensor.mtg_inbox_pending_value_eur` | Market value of everything still pending | EUR |
| `sensor.mtg_inbox_oldest_age_days` | Age of the oldest pending card | d |
| `sensor.mtg_inbox_decided_30d` | Triage decisions in the last 30 days | – |
| `binary_sensor.mtg_inbox_has_pending` | `on` while anything is pending | – |

`sensor.mtg_inbox_pending` carries the 10 newest pending cards in its `items`
attribute (name, set, quantity, suggestion, reason, price, age).
`sensor.mtg_inbox_decided_30d` carries a `by_state` breakdown.

Basic lands are excluded everywhere, matching the Inbox UI.

### Selling

| Sensor entity | Description | Unit |
|---------------|-------------|------|
| `sensor.mtg_sell_candidates` | Cards the sell advisor recommends selling | – |
| `sensor.mtg_sell_potential_eur` | Expected proceeds if you sold all unused copies | EUR |
| `sensor.mtg_duplicates_surplus_cards` | Surplus copies beyond deck usage and existing listings | – |
| `sensor.mtg_duplicates_surplus_value_eur` | Value of that surplus | EUR |
| `sensor.mtg_unlisted_value_eur` | Value of surplus **not yet listed** on Cardmarket — your to-do number | EUR |

`sensor.mtg_sell_candidates` and `sensor.mtg_unlisted_value_eur` carry their top
10 rows in the `items` attribute.

### Deep links into the add-on UI

| Sensor entity | Description |
|---------------|-------------|
| `sensor.mtg_ingress_url` | The add-on's own ingress path, e.g. `/api/hassio_ingress/<token>` |

Its attributes carry a ready-made link per UI route — `dashboard`, `decks`,
`collection`, `inbox`, `duplicates`, `cardmarket`, `wishlist`, `settings` — so
dashboard cards never need a hardcoded slug:

```yaml
tap_action:
  action: url
  url_path: "{{ state_attr('sensor.mtg_ingress_url', 'inbox') }}"
```

The sensor stays *unknown* when the add-on runs outside Home Assistant
(standalone Docker), where no absolute link exists.

### Deck performance

| Sensor entity | Description | Unit |
|---------------|-------------|------|
| `sensor.mtg_games_30d` | Games logged in the last 30 days | – |
| `sensor.mtg_winrate_30d` | Win rate over that window (attributes: W/L/D) | % |
| `sensor.mtg_last_game_at` | When the last game was played | timestamp |
| `sensor.mtg_last_game_result` | `win` / `loss` / `draw` (attribute: `deck_name`) | – |
| `sensor.mtg_deck_<deck_id>_winrate` | Win rate per deck played in the last 90 days | % |

Per-deck sensors carry `games`, `wins`, `losses`, `draws`, `last_played` and
`deck_name` as attributes. They are keyed by deck **id**, so renaming a deck in
Archidekt keeps the sensor and its history. A deck that has not been played for
90 days is removed from HA again; logging a game brings it straight back.

### MTGStocks signals

Published only while `mtgstocks_enabled` is on; switching the option off clears
the entities from HA.

| Sensor entity | Description |
|---------------|-------------|
| `sensor.mtg_signals_buy` | Wishlist cards trading near their all-time low |
| `sensor.mtg_signals_sell` | Owned, unused copies trading near their all-time high |

All sensors are registered via MQTT Discovery under the `MTG Collection` device.
The discovery payload pins `object_id`, so a fresh install gets exactly the
entity ids listed above. Entities that already exist keep the id they have —
check Settings → Devices & Services → MQTT if yours differ.

The count sensors declare `state_class: measurement` and the monetary ones
`state_class: total`, so HA records long-term statistics for them — you can chart
the collection value or card count over time with a `statistics-graph` card
without any template sensors.

---

## MQTT-Based Service Registry

The add-on subscribes to `mtg-collection/service/+` and exposes these callable services:

| Command topic | Payload | Description |
|---------------|---------|-------------|
| `mtg-collection/service/trigger_sync` | `{}` | Kick off a full Archidekt sync |
| `mtg-collection/service/sync_prices` | `{}` | Sync Cardmarket prices immediately |
| `mtg-collection/service/add_to_wishlist` | `{"card_name": "Sol Ring", "priority": 4}` | Add a card to the wishlist |
| `mtg-collection/service/mark_acquired` | `{"item_id": 42, "source": "whatnot", "paid_price_eur": 1.20}` | Mark a wishlist item as acquired |
| `mtg-collection/service/log_game` | see below | Log a played game |
| `mtg-collection/service/triage` | `{"event_id": 42, "action": "keep"}` | Decide one inbox item |
| `mtg-collection/service/create_listing` | `{"card_name": "Sol Ring", "price": 1.5, "quantity": 2}` | Create a Cardmarket listing |

Every command publishes a response to `mtg-collection/service/{cmd}/response`.

### Logging a game

```json
{
  "deck": "Atraxa",
  "result": "win",
  "played_at": "2026-07-22",
  "pod_size": 4,
  "on_play": true,
  "mulligans": 1,
  "missed_land_drops": 0,
  "turns": 9,
  "opponents": "Krenko, Edgar",
  "what_worked": "...",
  "what_didnt": "...",
  "notes": "..."
}
```

Only `deck` (or `deck_id`) and `result` matter; everything else has a default,
and `played_at` defaults to today. The deck is matched by id or by name —
case-insensitively, exact match first, then a unique substring:

```json
{"status": "logged", "game_id": 17, "deck_id": 3, "deck_name": "Atraxa", "result": "win", "played_at": "2026-07-22"}
```

An ambiguous or unknown name is never guessed at; the response names the
candidates so you can retry:

```json
{"error": "'Krenko' matches 2 decks — be more specific", "candidates": ["Krenko Goblins", "Krenko Mob Boss"], "cmd": "log_game"}
```

### Triage from a notification

`action` is `keep`, `sold_new`, `swap` or `dismiss`. Selling requires
`listing_price_eur`; `source` defaults to `other` for decisions made from HA.
Combined with `sensor.mtg_inbox_pending` this gives actionable notifications:

```yaml
automation:
  - alias: "MTG Inbox: actionable triage"
    trigger:
      - platform: state
        entity_id: sensor.mtg_inbox_pending
    condition: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      - variables:
          card: "{{ state_attr('sensor.mtg_inbox_pending', 'items')[0] }}"
      - service: notify.mobile_app_yourphone
        data:
          title: "New: {{ card.card_name }}"
          message: "Suggestion: {{ card.suggestion }} — {{ card.reason }}"
          data:
            actions:
              - action: "MTG_KEEP_{{ card.event_id }}"
                title: "Keep"
              - action: "MTG_SELL_{{ card.event_id }}"
                title: "Sell (€{{ card.price_eur }})"

  - alias: "MTG Inbox: handle notification action"
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
    action:
      - variables:
          parts: "{{ trigger.event.data.action.split('_') }}"
      - condition: "{{ parts[0] == 'MTG' }}"
      - service: mqtt.publish
        data:
          topic: "mtg-collection/service/triage"
          payload: >
            {"event_id": {{ parts[2] }},
             "action": "{{ 'keep' if parts[1] == 'KEEP' else 'sold_new' }}"
             {%- if parts[1] == 'SELL' %}, "listing_price_eur": 1.0{% endif %}}
```

### Logging a game by voice

Copy [voice/sentences.yaml](../mtg-collection/voice/sentences.yaml) as described
under [Voice Integration](#voice-integration-ha-assist); it ships
`HassMTGLogWin` / `HassMTGLogLoss` with a `{deck}` slot. Wire the intent to a
script:

```yaml
intent_script:
  HassMTGLogWin:
    speech:
      text: "Logged a win with {{ deck }}."
    action:
      - service: mqtt.publish
        data:
          topic: "mtg-collection/service/log_game"
          payload: '{"deck": "{{ deck }}", "result": "win"}'
```

### Example: trigger sync from an automation

```yaml
automation:
  - alias: "Trigger MTG Sync at 04:00"
    trigger:
      - platform: time
        at: "04:00:00"
    action:
      - service: mqtt.publish
        data:
          topic: "mtg-collection/service/trigger_sync"
          payload: "{}"
```

### Example: add a card via MQTT Developer Tools

In HA → Developer Tools → MQTT:

- **Topic**: `mtg-collection/service/add_to_wishlist`
- **Payload**: `{"card_name": "Rhystic Study", "priority": 5}`

Response appears on `mtg-collection/service/add_to_wishlist/response`.

### Monitor sync responses

```bash
mosquitto_pub -h <mqtt_host> -t 'mtg-collection/service/trigger_sync' -m '{}'
mosquitto_sub -h <mqtt_host> -t 'mtg-collection/service/trigger_sync/response' -C 1
# Expected: {"status": "started", "cmd": "trigger_sync"}
```

---

## Persistent Notifications with Deep Links

When the add-on is running inside HA (Supervisor token available), it creates **persistent notifications** in HA's notification panel instead of — or in addition to — webhook/service calls.

Notifications include a clickable **"Open in MTG Collection"** link that jumps directly to the relevant tab in the add-on UI.

| Alert type | Deep link |
|------------|-----------|
| Price spike | `/cardmarket` |
| Sync error | `/settings` |

The link is resolved to a full Ingress URL from the path the Supervisor hands
the add-on at startup. Outside a Supervisor environment there is no absolute
link, and the notification is sent without one rather than with a path that
would resolve against Home Assistant itself.

You can also trigger persistent notifications from your own Python services or scripts via the `send_persistent_notification` helper in `backend/app/services/notifications.py`.

---

## Voice Integration (HA Assist)

### REST endpoints

The add-on exposes two endpoints for voice queries:

```
GET /api/voice/card-count?name=Sol+Ring
# → {"card_name": "Sol Ring", "quantity": 3, "found": true}

GET /api/voice/active-deals
# → {"deals_count": 2, "items": [...]}
```

### Setting up REST sensors in HA

> ⚠️ **The host is the container name, not `localhost`.** This example said
> `http://localhost:8099` until 2026-08-29, which cannot work: the sensor is
> evaluated by Home Assistant Core, and from Core's container `localhost` is
> Core itself. The add-on answers on `http://0c11a0b9-mtg-collection:8099`.

Add to your `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: "MTG Card Count Query"
    resource_template: "http://0c11a0b9-mtg-collection:8099/api/voice/card-count?name={{ states('input_text.mtg_card_query') }}"
    value_template: "{{ value_json.quantity }}"
    json_attributes:
      - card_name
      - found
    scan_interval: 3600  # Only refresh on demand

  - platform: rest
    name: "MTG Active Deals Count"
    resource: "http://0c11a0b9-mtg-collection:8099/api/voice/active-deals"
    value_template: "{{ value_json.deals_count }}"
    json_attributes:
      - items
    scan_interval: 3600
```

### Voice sentences (HA Assist)

Copy [voice/sentences.yaml](../mtg-collection/voice/sentences.yaml) into your HA config as
`custom_sentences/en/mtg_collection.yaml` and restart HA.

Then configure response scripts/automations to call the REST sensors above.

> **Status, measured 2026-08-29 — this is set up on neither side.** The
> add-on's `/api/voice/*` endpoints **do** work (`active-deals` answers 200),
> but there is no `custom_sentences/` directory in this Home Assistant at all,
> and the two REST sensors above are not in `configuration.yaml`. So none of
> the seven intents can fire. Whether to finish it or drop `voice/` is a
> product decision, not a bug — see `docs/sprints/sprint-11-ai-mcp.md`.

---

## Example Automations

### Price spike → Telegram + Sonos announcement

```yaml
automation:
  - alias: "MTG Price Spike Alert"
    trigger:
      - platform: state
        entity_id: sensor.mtg_active_price_alerts
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      - service: telegram_bot.send_message
        data:
          message: >
            💸 MTG price spike detected!
            {{ state_attr('sensor.mtg_active_price_alerts', 'friendly_name') }}
            → check the MTG Collection dashboard.
      - service: tts.speak
        target:
          entity_id: media_player.sonos_living_room
        data:
          message: "MTG price spike alert. Check your collection manager."
          cache: false
```

### New cards in the inbox → mobile notification

```yaml
automation:
  - alias: "MTG Inbox: new cards to triage"
    trigger:
      - platform: numeric_state
        entity_id: sensor.mtg_inbox_pending
        above: 0
    action:
      - service: notify.mobile_app_yourphone
        data:
          title: "MTG Inbox: {{ states('sensor.mtg_inbox_pending') }} cards"
          message: >
            {{ state_attr('sensor.mtg_inbox_pending', 'items')
               | map(attribute='card_name') | join(', ') }}
            — {{ states('sensor.mtg_inbox_needs_sell') }} suggested for selling.
```

### Weekly selling report

```yaml
automation:
  - alias: "MTG: weekly sell report"
    trigger:
      - platform: time
        at: "18:00:00"
    condition:
      - condition: time
        weekday: [sun]
      - condition: numeric_state
        entity_id: sensor.mtg_sell_potential_eur
        above: 20
    action:
      - service: notify.mobile_app_yourphone
        data:
          title: "MTG: €{{ states('sensor.mtg_sell_potential_eur') }} sellable"
          message: >
            {{ states('sensor.mtg_sell_candidates') }} candidates,
            €{{ states('sensor.mtg_unlisted_value_eur') }} not yet listed.
            Top: {% for c in state_attr('sensor.mtg_sell_candidates', 'items')[:3] %}
            {{ c.card_name }} ({{ c.copies_to_sell }}× €{{ c.trend_price_eur }}){% endfor %}
```

### Inbox left unattended

```yaml
automation:
  - alias: "MTG Inbox: cards waiting too long"
    trigger:
      - platform: numeric_state
        entity_id: sensor.mtg_inbox_oldest_age_days
        above: 14
    action:
      - service: persistent_notification.create
        data:
          title: "MTG Inbox"
          message: >
            The oldest card has been waiting
            {{ states('sensor.mtg_inbox_oldest_age_days') }} days.
```

### Wishlist deal alert

```yaml
automation:
  - alias: "MTG Wishlist Deal Alert"
    trigger:
      - platform: mqtt
        topic: "mtg-collection/wishlist/+/state"
    condition:
      - condition: template
        value_template: "{{ trigger.payload_json.is_deal == true }}"
    action:
      - service: notify.mobile_app_yourphone
        data:
          title: "MTG Deal: {{ trigger.payload_json.card_name }}"
          message: >
            {{ trigger.payload_json.card_name }} is €{{ trigger.payload_json.current_price_eur }}
            (target: €{{ trigger.payload_json.target_price_eur }},
            {{ trigger.payload_json.delta_pct }}%)
```

### Confirm acquisition via UI button

```yaml
script:
  mtg_mark_acquired:
    alias: "MTG: Mark wishlist item acquired"
    fields:
      item_id:
        description: "Wishlist item ID"
        example: 42
      paid_price_eur:
        description: "Price paid in EUR"
        example: 1.20
    sequence:
      - service: mqtt.publish
        data:
          topic: "mtg-collection/service/mark_acquired"
          payload: >
            {"item_id": {{ item_id }}, "source": "manual", "paid_price_eur": {{ paid_price_eur }}}
```

---

## Example Dashboard Cards

### Mushroom template card for a wishlist item

```yaml
type: custom:mushroom-template-card
primary: "{{ state_attr('sensor.mtg_wishlist_42', 'card_name') }}"
secondary: >
  €{{ states('sensor.mtg_wishlist_42') }}
  (target: €{{ state_attr('sensor.mtg_wishlist_42', 'target_price_eur') }})
icon: mdi:cards
icon_color: >
  {% if state_attr('sensor.mtg_wishlist_42', 'is_deal') %}green{% else %}orange{% endif %}
tap_action:
  action: url
  url_path: /api/hassio_ingress/<your-ingress-slug>/wishlist
```

### Stats overview (Mushroom chips)

```yaml
type: custom:mushroom-chips-card
chips:
  - type: entity
    entity: sensor.mtg_total_cards
    icon: mdi:cards
  - type: entity
    entity: sensor.mtg_total_value_eur
    icon: mdi:currency-eur
  - type: entity
    entity: sensor.mtg_active_price_alerts
    icon: mdi:alert-decagram
  - type: entity
    entity: sensor.mtg_acquired_count_30d
    icon: mdi:cards-playing-heart-multiple
```

---

## Troubleshooting

### MQTT sensors don't appear in HA

1. Check that `mqtt_enabled: true` is set in add-on options.
2. Verify the broker credentials (`mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`).
3. Check add-on logs for `"MQTT manager connected"` and `"MQTT discovery configs published"`.
4. In HA → Developer Tools → MQTT, subscribe to `homeassistant/sensor/mtg_#` and restart the add-on.

### All MTG entities show "unavailable"

The add-on is not connected to the broker. Check `mtg-collection/status` — if it
reads `offline`, look for `"MQTT manager disconnected, reconnecting in 30s"` in
the add-on log; the connection is retried automatically every 30 seconds.

### Service commands are not processed

1. Check add-on logs for `"MQTT service subscriber listening on"`.
2. Make sure you are publishing to the correct prefix (`mtg-collection/service/…` by default).
3. Confirm the MQTT broker allows retained messages.

### Wishlist sensors not showing updated prices

The state is re-published after each daily Cardmarket price sync. You can trigger an immediate re-sync via:

```bash
mosquitto_pub -h <mqtt_host> -t 'mtg-collection/service/sync_prices' -m '{}'
```

### Persistent notifications not appearing

The add-on must be running as a **Home Assistant Add-on** (not standalone Docker). The `SUPERVISOR_TOKEN` environment variable must be set — this is injected automatically by the Supervisor.
