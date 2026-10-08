"""Flimmer: setting a server up -- found on the network, or by its address --
with a personal key made in Flimmer's Settings (Mine -> Keys)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import FlimmerApi, FlimmerAuthError, FlimmerError
from .const import CONF_KEY, CONF_URL, DOMAIN


class FlimmerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None
        self._name: str | None = None

    async def _check(self, url: str, key: str) -> tuple[dict[str, Any] | None, str | None]:
        api = FlimmerApi(async_get_clientsession(self.hass), url, key)
        try:
            return await api.state(), None
        except FlimmerAuthError:
            return None, "invalid_auth"
        except FlimmerError:
            return None, "cannot_connect"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if "://" not in url:
                url = "http://" + url
            state, error = await self._check(url, user_input[CONF_KEY].strip())
            if state:
                server = state["server"]
                await self.async_set_unique_id(server["id"])
                self._abort_if_unique_id_configured(updates={CONF_URL: url})
                return self.async_create_entry(
                    title=server.get("name") or "Flimmer", data={CONF_URL: url, CONF_KEY: user_input[CONF_KEY].strip()}
                )
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL, default=self._url or "http://"): str, vol.Required(CONF_KEY): str}
            ),
            description_placeholders={"name": self._name or "Flimmer"},
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        props = discovery_info.properties or {}
        server_id = props.get("id")
        if not server_id:
            return self.async_abort(reason="not_flimmer")
        # A member of a Flimmer network is set up through the network's main
        # server, which every member names: only that one is offered.
        primary = props.get("primary")
        if primary and primary != server_id:
            return self.async_abort(reason="not_primary")
        host = discovery_info.host
        port = props.get("port") or discovery_info.port
        await self.async_set_unique_id(server_id)
        self._abort_if_unique_id_configured(updates={CONF_URL: f"http://{host}:{port}"})
        self._url = f"http://{host}:{port}"
        self._name = props.get("name") or "Flimmer"
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            state, error = await self._check(entry.data[CONF_URL], user_input[CONF_KEY].strip())
            if state:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_KEY: user_input[CONF_KEY].strip()})
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_KEY): str}), errors=errors
        )
