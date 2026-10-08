"""Flimmer: the server as a device."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlimmerCoordinator


class FlimmerEntity(CoordinatorEntity[FlimmerCoordinator]):
    """Something of the server's."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlimmerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        server = coordinator.data["server"]
        self._attr_unique_id = f"{server['id']}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, server["id"])},
            name=f"Flimmer {server['name']}",
            manufacturer="Lightroad",
            model="Flimmer Server",
            sw_version=str(server.get("build", "")),
            configuration_url=coordinator.api.url,
        )
