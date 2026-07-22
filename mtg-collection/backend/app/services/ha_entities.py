"""Home Assistant MQTT Discovery entity descriptions.

One place that knows how a discovery payload is built, for every component type
(``sensor`` today; ``binary_sensor``/``select``/``number``/``switch``/``text``/
``button`` in the upcoming sprints).

The ``unique_id`` of an entity is its permanent identity in HA's entity
registry — changing one orphans the existing entity and its history, so the
values here are covered by snapshot tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..version import VERSION

DEVICE_INFO: dict[str, Any] = {
    "identifiers": ["mtg-collection-ha"],
    "name": "MTG Collection",
    "manufacturer": "mtg-collection-ha",
    "model": "Add-on",
}

# Device block used for per-item wishlist sensors
WISHLIST_DEVICE_INFO: dict[str, Any] = {
    "identifiers": ["mtg_collection_manager"],
    "name": "MTG Collection Manager",
    "model": f"v{VERSION}",
}


@dataclass(frozen=True)
class Entity:
    """A single HA entity exposed via MQTT Discovery.

    ``unique_id`` defaults to ``mtg_collection_{key}`` and doubles as the
    discovery node id; ``state_topic`` defaults to ``{prefix}/{key}``.
    """

    key: str
    name: str
    component: str = "sensor"
    unique_id: str = ""
    state_topic: str = ""
    icon: str = ""
    device_class: str = ""
    unit: str = ""
    state_class: str = ""
    value_template: str = ""
    json_attributes_topic: str = ""
    # Publish a JSON attribute payload alongside the state, on
    # `{state_topic}/attributes` (used for the top-N lists).
    has_attributes: bool = False
    device: dict[str, Any] = field(default_factory=lambda: DEVICE_INFO)
    # Component-specific keys (options, min/max, command_topic, …)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_unique_id(self) -> str:
        """Permanent identity in HA's entity registry, and the discovery node."""
        return self.unique_id or f"mtg_collection_{self.key}"

    @property
    def object_id(self) -> str:
        """Basis for the generated entity_id, i.e. `sensor.mtg_<key>`.

        Without it HA derives the entity_id from the device and entity name,
        which is neither obvious nor stable across renames.  It only applies
        when an entity is first registered — entities that already exist keep
        the entity_id they have.
        """
        return f"mtg_{self.key}"

    def resolved_state_topic(self, prefix: str) -> str:
        return self.state_topic or f"{prefix}/{self.key}"

    def resolved_attributes_topic(self, prefix: str) -> str:
        """Topic carrying the JSON attributes, or "" when the entity has none."""
        if self.json_attributes_topic:
            return self.json_attributes_topic
        if self.has_attributes:
            return f"{self.resolved_state_topic(prefix)}/attributes"
        return ""


def discovery_topic(entity: Entity) -> str:
    return f"homeassistant/{entity.component}/{entity.resolved_unique_id}/config"


def discovery_payload(entity: Entity, prefix: str, availability_topic: str) -> dict[str, Any]:
    """Build the retained discovery config for one entity."""
    payload: dict[str, Any] = {
        "name": entity.name,
        "unique_id": entity.resolved_unique_id,
        "object_id": entity.object_id,
        "state_topic": entity.resolved_state_topic(prefix),
        "device": entity.device,
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
    }

    optional = {
        "device_class": entity.device_class,
        "unit_of_measurement": entity.unit,
        "state_class": entity.state_class,
        "icon": entity.icon,
        "value_template": entity.value_template,
        "json_attributes_topic": entity.resolved_attributes_topic(prefix),
    }
    payload.update({k: v for k, v in optional.items() if v})
    payload.update(entity.extra)
    return payload
