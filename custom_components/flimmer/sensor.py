"""Flimmer: what the server counts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlimmerConfigEntry
from .entity import FlimmerEntity


@dataclass(frozen=True, kw_only=True)
class FlimmerSensorDescription(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    admin_only: bool = False


def _playing(d: dict[str, Any]) -> str:
    titles = [s.get("title", "") for s in d.get("sessions", [])]
    return ", ".join(t for t in titles if t)[:250] or "Nothing"


SENSORS: tuple[FlimmerSensorDescription, ...] = (
    FlimmerSensorDescription(
        key="streams", translation_key="streams", icon="mdi:play-network",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: len(d.get("sessions", [])),
        attributes=lambda d: {"sessions": d.get("sessions", [])},
    ),
    FlimmerSensorDescription(
        key="now_playing", translation_key="now_playing", icon="mdi:television-play",
        value=_playing,
    ),
    FlimmerSensorDescription(
        key="players", translation_key="players", icon="mdi:television",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: len(d.get("players", [])),
        attributes=lambda d: {"players": [p.get("name") for p in d.get("players", [])]},
    ),
    FlimmerSensorDescription(
        key="films", translation_key="films", icon="mdi:movie-open",
        state_class=SensorStateClass.MEASUREMENT, value=lambda d: d.get("library", {}).get("films"),
    ),
    FlimmerSensorDescription(
        key="series", translation_key="series", icon="mdi:television-classic",
        state_class=SensorStateClass.MEASUREMENT, value=lambda d: d.get("library", {}).get("series"),
    ),
    FlimmerSensorDescription(
        key="albums", translation_key="albums", icon="mdi:album",
        state_class=SensorStateClass.MEASUREMENT, value=lambda d: d.get("library", {}).get("albums"),
    ),
    FlimmerSensorDescription(
        key="newest", translation_key="newest", icon="mdi:new-box",
        value=lambda d: d.get("library", {}).get("newest") or None,
    ),
    FlimmerSensorDescription(
        key="provider_holder", translation_key="provider_holder", icon="mdi:satellite-uplink",
        value=lambda d: d.get("server", {}).get("provider_holder") or None,
    ),
    FlimmerSensorDescription(
        key="transcoding", translation_key="transcoding", icon="mdi:cog-transfer",
        state_class=SensorStateClass.MEASUREMENT, admin_only=True,
        value=lambda d: sum(int(t.get("jobs") or 0) for t in d.get("transcoders", [])),
        attributes=lambda d: {
            "transcoders": [
                {"name": t.get("name"), "ok": t.get("ok"), "jobs": t.get("jobs"), "backend": t.get("backend")}
                for t in d.get("transcoders", [])
            ]
        },
    ),
    FlimmerSensorDescription(
        key="cpu", translation_key="cpu", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC, admin_only=True,
        value=lambda d: round(d.get("system", {}).get("cpu_percent", 0), 1),
    ),
    FlimmerSensorDescription(
        key="memory", translation_key="memory", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC, admin_only=True,
        value=lambda d: round(100 * d["system"]["mem_used_mb"] / d["system"]["mem_total_mb"], 1)
        if d.get("system", {}).get("mem_total_mb") else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FlimmerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    admin = "system" in coordinator.data
    async_add_entities(
        FlimmerSensor(coordinator, description)
        for description in SENSORS
        if admin or not description.admin_only
    )


class FlimmerSensor(FlimmerEntity, SensorEntity):
    entity_description: FlimmerSensorDescription

    def __init__(self, coordinator, description: FlimmerSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)
