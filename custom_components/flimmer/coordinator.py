"""Flimmer: keeping the server's state, read again when it says something changed."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FlimmerApi, FlimmerAuthError, FlimmerError
from .const import DOMAIN, EVENT_CHANGE, REFRESH_ON, SCAN_SECONDS

_LOGGER = logging.getLogger(__name__)


class FlimmerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The server's state, every minute and on every change it tells."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: FlimmerApi) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=SCAN_SECONDS)
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.state()
        except FlimmerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FlimmerError as err:
            raise UpdateFailed(str(err)) from err

    async def listen(self) -> None:
        """Follows the server's changes for as long as the entry is loaded,
        coming back after a dropped connection; each change is an event on
        Home Assistant's bus, and the state is read again for those that
        matter to it."""
        wait = 2
        while True:
            try:
                async for kind in self.api.changes():
                    wait = 2
                    self.hass.bus.async_fire(
                        EVENT_CHANGE, {"type": kind, "server": (self.data or {}).get("server", {}).get("name", "")}
                    )
                    if kind in REFRESH_ON:
                        await self.async_request_refresh()
            except asyncio.CancelledError:
                raise
            except FlimmerAuthError:
                _LOGGER.warning("Flimmer refused the key; stopping the change stream")
                return
            except Exception as err:  # noqa: BLE001 -- any break is a reconnect
                _LOGGER.debug("Flimmer change stream: %s", err)
            await asyncio.sleep(wait)
            wait = min(wait * 2, 60)
