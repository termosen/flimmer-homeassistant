"""Flimmer: talking to the server."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

import aiohttp

_LOGGER = logging.getLogger(__name__)


class FlimmerError(Exception):
    """The server could not be asked."""


class FlimmerAuthError(FlimmerError):
    """The key was refused."""


class FlimmerApi:
    """One Flimmer server, signed in with a personal key."""

    def __init__(self, session: aiohttp.ClientSession, url: str, key: str) -> None:
        self._session = session
        self.url = url.rstrip("/")
        self._key = key

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "X-Flimmer-Client": "Home Assistant"}

    async def state(self) -> dict[str, Any]:
        """What the server is doing: /api/ha/state."""
        try:
            async with self._session.get(
                f"{self.url}/api/ha/state", headers=self._headers, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status in (401, 403):
                    raise FlimmerAuthError("the key was refused")
                if resp.status != 200:
                    raise FlimmerError(f"the server answered {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FlimmerError(str(err)) from err

    async def command(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """A command, as Claude sends it: play, pause, resume, stop, play_music, next_track, previous_track."""
        try:
            async with self._session.post(
                f"{self.url}/api/ha/command",
                headers=self._headers,
                json={"tool": tool, "arguments": arguments},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200:
                    raise FlimmerError((body or {}).get("error") or f"the server answered {resp.status}")
                return body
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FlimmerError(str(err)) from err

    async def changes(self) -> AsyncIterator[str]:
        """Every change the server tells about, as it happens (server-sent events)."""
        async with self._session.get(
            f"{self.url}/api/changes/listen",
            headers={**self._headers, "Accept": "text/event-stream"},
            timeout=aiohttp.ClientTimeout(total=None, sock_read=120),
        ) as resp:
            if resp.status in (401, 403):
                raise FlimmerAuthError("the key was refused")
            if resp.status != 200:
                raise FlimmerError(f"the server answered {resp.status}")
            async for raw in resp.content:
                line = raw.decode(errors="replace").strip()
                if line.startswith("data:"):
                    try:
                        kind = json.loads(line[5:].strip()).get("type", "")
                    except ValueError:
                        continue
                    if kind:
                        yield kind
