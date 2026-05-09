# Home Assistant Integration Guide

This guide covers all the ways **MTG Collection Manager** integrates deeply with Home Assistant:

- [Wishlist Item Sensors](#wishlist-item-sensors)
- [Aggregate Sensors (Spending, Listing Health)](#aggregate-sensors)
- [MQTT-Based Service Registry](#mqtt-based-service-registry)
- [Persistent Notifications with Deep Links](#persistent-notifications-with-deep-links)
- [Voice Integration (HA Assist)](#voice-integration-ha-assist)
- [Example Automations](#example-automations)
- [Example Dashboard Cards](#example-dashboard-cards)
- [Troubleshooting](#troubleshooting)

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

All sensors are registered via MQTT Discovery under the `MTG Collection` device.

---

## MQTT-Based Service Registry

The add-on subscribes to `mtg-collection/service/+` and exposes four callable services:

| Command topic | Payload | Description |
|---------------|---------|-------------|
| `mtg-collection/service/trigger_sync` | `{}` | Kick off a full Archidekt sync |
| `mtg-collection/service/sync_prices` | `{}` | Sync Cardmarket prices immediately |
| `mtg-collection/service/add_to_wishlist` | `{"card_name": "Sol Ring", "priority": 4}` | Add a card to the wishlist |
| `mtg-collection/service/mark_acquired` | `{"item_id": 42, "source": "whatnot", "paid_price_eur": 1.20}` | Mark a wishlist item as acquired |

Every command publishes a response to `mtg-collection/service/{cmd}/response`.

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

Add to your `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: "MTG Card Count Query"
    resource_template: "http://localhost:8099/api/voice/card-count?name={{ states('input_text.mtg_card_query') }}"
    value_template: "{{ value_json.quantity }}"
    json_attributes:
      - card_name
      - found
    scan_interval: 3600  # Only refresh on demand

  - platform: rest
    name: "MTG Active Deals Count"
    resource: "http://localhost:8099/api/voice/active-deals"
    value_template: "{{ value_json.deals_count }}"
    json_attributes:
      - items
    scan_interval: 3600
```

### Voice sentences (HA Assist)

Copy [voice/sentences.yaml](../mtg-collection/voice/sentences.yaml) into your HA config as
`custom_sentences/en/mtg_collection.yaml` and restart HA.

Then configure response scripts/automations to call the REST sensors above.

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
3. Check add-on logs for `"MQTT discovery configs published"`.
4. In HA → Developer Tools → MQTT, subscribe to `homeassistant/sensor/mtg_#` and restart the add-on.

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
