"""Flimmer: the household's players -- the televisions with Flimmer open."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FlimmerConfigEntry
from .api import FlimmerError
from .const import DOMAIN
from .coordinator import FlimmerCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: FlimmerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new() -> None:
        # A player turns up when Flimmer is opened on it, and stays.
        new = [p for p in coordinator.data.get("players", []) if p.get("id") and p["id"] not in known]
        for p in new:
            known.add(p["id"])
        if new:
            async_add_entities(FlimmerPlayer(coordinator, p) for p in new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class FlimmerPlayer(CoordinatorEntity[FlimmerCoordinator], MediaPlayerEntity):
    """One player: on while Flimmer is open on it, playing while it plays."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(self, coordinator: FlimmerCoordinator, player: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._id = player["id"]
        self._name = player.get("name") or self._id
        self._paused = False
        self._attr_unique_id = f"player-{self._id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"player-{self._id}")},
            name=self._name.title() if self._name.islower() else self._name,
            manufacturer="Lightroad",
            model=f"Flimmer on {player.get('platform', 'a player')}",
            via_device=(DOMAIN, coordinator.data["server"]["id"]),
        )

    def _session(self) -> dict[str, Any] | None:
        name = self._name.lower()
        for s in self.coordinator.data.get("sessions", []):
            if any((d or "").lower() == name for d in s.get("devices", [])):
                return s
        return None

    @property
    def available(self) -> bool:
        return super().available

    @property
    def state(self) -> MediaPlayerState:
        on = any(p.get("id") == self._id for p in self.coordinator.data.get("players", []))
        if self._session():
            return MediaPlayerState.PAUSED if self._paused else MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE if on else MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        s = self._session()
        return s.get("title") if s else None

    @property
    def media_content_type(self) -> MediaType | None:
        s = self._session()
        if not s:
            return None
        return MediaType.CHANNEL if s.get("kind") == "live" else MediaType.VIDEO

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        s = self._session()
        if not s:
            return None
        return {k: s.get(k) for k in ("kind", "media_id", "engine", "quality", "user", "network", "started_at")}

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self._session():
            self._paused = False
        super()._handle_coordinator_update()

    async def _send(self, tool: str) -> None:
        try:
            await self.coordinator.api.command(tool, {"player": self._name})
        except FlimmerError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_media_pause(self) -> None:
        await self._send("pause")
        self._paused = True
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        await self._send("resume")
        self._paused = False
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        await self._send("stop")
        self._paused = False
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        await self._send("next_track")

    async def async_media_previous_track(self) -> None:
        await self._send("previous_track")
