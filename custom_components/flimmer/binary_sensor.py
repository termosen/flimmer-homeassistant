"""Flimmer: what is so or not."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlimmerConfigEntry
from .entity import FlimmerEntity


@dataclass(frozen=True, kw_only=True)
class FlimmerBinaryDescription(BinarySensorEntityDescription):
    value: Callable[[dict[str, Any]], bool]


BINARY: tuple[FlimmerBinaryDescription, ...] = (
    FlimmerBinaryDescription(
        key="watching", translation_key="watching", device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:television-play", value=lambda d: bool(d.get("sessions")),
    ),
    FlimmerBinaryDescription(
        key="watching_live", translation_key="watching_live", icon="mdi:broadcast",
        value=lambda d: any(s.get("kind") == "live" for s in d.get("sessions", [])),
    ),
    FlimmerBinaryDescription(
        key="playing_music", translation_key="playing_music", icon="mdi:music",
        value=lambda d: any(s.get("kind") == "music" for s in d.get("sessions", [])),
    ),
    FlimmerBinaryDescription(
        key="provider_here", translation_key="provider_here", icon="mdi:satellite-uplink",
        value=lambda d: bool(d.get("server", {}).get("provider_here")),
    ),
    FlimmerBinaryDescription(
        key="network", translation_key="network", device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value=lambda d: all(p.get("online") for p in d.get("server", {}).get("linked", [])),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FlimmerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(FlimmerBinary(entry.runtime_data, d) for d in BINARY)


class FlimmerBinary(FlimmerEntity, BinarySensorEntity):
    entity_description: FlimmerBinaryDescription

    def __init__(self, coordinator, description: FlimmerBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "network":
            return {"servers": self.coordinator.data.get("server", {}).get("linked", [])}
        return None
