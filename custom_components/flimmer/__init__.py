"""Flimmer: the household's media server, for Home Assistant.

What plays where, whether the server holds the IPTV provider, the library and
the transcoders -- read on every change the server tells -- and the players
to pause, resume, stop and play on.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FlimmerApi, FlimmerError
from .const import CONF_KEY, CONF_URL, DOMAIN
from .coordinator import FlimmerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.MEDIA_PLAYER, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type FlimmerConfigEntry = ConfigEntry[FlimmerCoordinator]

PLAY_SCHEMA = vol.Schema(
    {
        vol.Optional("server"): cv.string,
        vol.Optional("player"): cv.string,
        vol.Optional("title_id"): vol.Coerce(int),
        vol.Optional("channel_id"): vol.Coerce(int),
        vol.Optional("from_start", default=False): cv.boolean,
    }
)
MUSIC_SCHEMA = vol.Schema(
    {
        vol.Optional("server"): cv.string,
        vol.Optional("player"): cv.string,
        vol.Optional("album_id"): cv.string,
        vol.Optional("artist_id"): cv.string,
        vol.Optional("track_id"): vol.Coerce(int),
        vol.Optional("shuffle", default=False): cv.boolean,
    }
)


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> FlimmerCoordinator:
    """The server a call is for: the one named, or the only one."""
    entries = [e for e in hass.config_entries.async_loaded_entries(DOMAIN)]
    if not entries:
        raise HomeAssistantError("No Flimmer server is set up")
    wanted = call.data.get("server")
    for entry in entries:
        if not wanted or wanted.lower() in (entry.title.lower(), (entry.unique_id or "").lower()):
            return entry.runtime_data
    raise HomeAssistantError(f"No Flimmer server called {wanted}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The services: play a title or a channel, play music."""

    async def play(call: ServiceCall) -> ServiceResponse:
        args = {k: v for k, v in call.data.items() if k != "server"}
        try:
            return await _coordinator(hass, call).api.command("play", args)
        except FlimmerError as err:
            raise HomeAssistantError(str(err)) from err

    async def play_music(call: ServiceCall) -> ServiceResponse:
        args = {k: v for k, v in call.data.items() if k != "server"}
        try:
            return await _coordinator(hass, call).api.command("play_music", args)
        except FlimmerError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(DOMAIN, "play", play, schema=PLAY_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(
        DOMAIN, "play_music", play_music, schema=MUSIC_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FlimmerConfigEntry) -> bool:
    api = FlimmerApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_KEY])
    coordinator = FlimmerCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # Which Flimmer network the server is in, kept with the entry: its other
    # members are then not offered when found (config_flow.py).
    network = coordinator.data["server"].get("network", "")
    if entry.data.get("net") != network:
        hass.config_entries.async_update_entry(entry, data={**entry.data, "net": network})
    # The server as a device before anything of it: the players are
    # connected through it, and it must be there for them to say so.
    server = coordinator.data["server"]
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, server["id"])},
        name=f"Flimmer {server['name']}",
        manufacturer="Lightroad",
        model="Flimmer Server",
        sw_version=str(server.get("build", "")),
        configuration_url=api.url,
    )
    entry.async_create_background_task(hass, coordinator.listen(), f"{DOMAIN}-changes-{entry.entry_id}")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlimmerConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
