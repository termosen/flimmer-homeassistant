"""Flimmer: the household's players -- the televisions with Flimmer open."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
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
from homeassistant.util import dt as dt_util

from . import FlimmerConfigEntry
from .api import FlimmerError
from .const import DOMAIN
from .coordinator import FlimmerCoordinator

# The server's word for what plays, as Home Assistant's: an episode is a TV
# show to the media card, which then shows the series and S1E3 under the
# episode's title.
MEDIA_TYPES = {
    "movie": MediaType.MOVIE,
    "episode": MediaType.TVSHOW,
    "channel": MediaType.CHANNEL,
    "music": MediaType.MUSIC,
    "video": MediaType.VIDEO,
}

# What the server knows of how it plays, as the player's attributes.
EXTRA = (
    "kind", "media_id", "quality", "playback", "transcoder", "output", "video_codec", "resolution",
    "audio", "audio_language", "subtitles", "bitrate_mbps", "user", "profile", "network", "engine",
    "started_at", "programme_start", "programme_stop",
)


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
        # A television's own icon where nothing plays, not a speaker's.
        if "tv" in str(player.get("platform", "")).lower():
            self._attr_device_class = MediaPlayerDeviceClass.TV
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
        session = self._session()
        if session:
            # Paused as the television says, or as paused from here a moment
            # ago, before it has said so.
            return MediaPlayerState.PAUSED if (session.get("paused") or self._paused) else MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE if on else MediaPlayerState.OFF

    @property
    def media_content_type(self) -> MediaType | None:
        s = self._session()
        if not s:
            return None
        kind = s.get("media_type")
        if kind in MEDIA_TYPES:
            return MEDIA_TYPES[kind]
        # A server from before 0.2.0 says only the kind.
        if s.get("kind") == "music":
            return MediaType.MUSIC
        return MediaType.CHANNEL if s.get("kind") == "live" else MediaType.VIDEO

    @property
    def media_content_id(self) -> str | None:
        s = self._session()
        if not s:
            return None
        if s.get("stream_id"):
            return f"channel:{s['stream_id']}"
        return str(s["media_id"]) if s.get("media_id") else None

    @property
    def media_title(self) -> str | None:
        s = self._session()
        if not s:
            return None
        kind = s.get("media_type")
        if kind == "episode":
            return s.get("episode_title") or s.get("title")
        if kind == "channel":
            # What is on, under it the channel (app_name).
            return s.get("programme") or s.get("channel") or s.get("title")
        return s.get("title")

    @property
    def media_series_title(self) -> str | None:
        s = self._session()
        return (s.get("series") or None) if s and s.get("media_type") == "episode" else None

    @property
    def media_season(self) -> str | None:
        s = self._session()
        return str(s["season"]) if s and s.get("media_type") == "episode" and s.get("season") else None

    @property
    def media_episode(self) -> str | None:
        s = self._session()
        return str(s["episode"]) if s and s.get("media_type") == "episode" and s.get("episode") else None

    @property
    def media_channel(self) -> str | None:
        s = self._session()
        return (s.get("channel") or None) if s and s.get("media_type") == "channel" else None

    @property
    def app_name(self) -> str | None:
        # The media card's second line for a channel: its name.
        return self.media_channel

    @property
    def media_artist(self) -> str | None:
        s = self._session()
        return (s.get("artist") or None) if s else None

    @property
    def media_album_name(self) -> str | None:
        s = self._session()
        return (s.get("album") or None) if s else None

    @property
    def media_duration(self) -> int | None:
        s = self._session()
        if not s or not s.get("duration"):
            return None
        return int(s["duration"])

    @property
    def media_position(self) -> int | None:
        s = self._session()
        if not s or s.get("position") is None or not s.get("position_at"):
            return None
        return int(s["position"])

    @property
    def media_position_updated_at(self) -> datetime | None:
        s = self._session()
        if not s or s.get("position") is None or not s.get("position_at"):
            return None
        return dt_util.utc_from_timestamp(s["position_at"])

    @property
    def media_image_url(self) -> str | None:
        """The picture, on the server: fetched by Home Assistant with the key
        in a header (async_get_media_image) and handed to browsers through
        its own proxy -- the key is never in an address."""
        s = self._session()
        return self.coordinator.api.image_url(s.get("image")) if s else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return False

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        url = self.media_image_url
        if not url:
            return None, None
        return await self.coordinator.api.image(url)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        s = self._session()
        if not s:
            return None
        return {k: s[k] for k in EXTRA if s.get(k) not in (None, "")}

    @callback
    def _handle_coordinator_update(self) -> None:
        # Music: the television says itself whether it is paused, and that
        # wins over what was pressed here. A film: kept as pressed, until it
        # ends.
        session = self._session()
        if not session or session.get("kind") == "music":
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
