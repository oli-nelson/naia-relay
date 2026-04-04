from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import aiohttp

from naia_relay.errors import TransportError
from naia_relay.transports.base import TransportAdapter

HttpRequester = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class HttpTransportConfig:
    base_url: str
    timeout_seconds: int = 10


class HttpTransportAdapter(TransportAdapter):
    def __init__(
        self,
        config: HttpTransportConfig,
        *,
        requester: HttpRequester | None = None,
    ) -> None:
        self.config = config
        self._requester = requester
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self._requester is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def stop(self) -> None:
        if self._session is not None:
            await self._session.close()
        self._session = None

    async def send(self, message: dict[str, Any]) -> None:
        await self._perform_request(message)

    async def receive(self) -> dict[str, Any]:
        raise TransportError("HTTP transport does not support standalone receive() in v1.")

    async def round_trip(self, message: dict[str, Any]) -> dict[str, Any]:
        return await self._perform_request(message)

    async def _perform_request(self, message: dict[str, Any]) -> dict[str, Any]:
        if self._requester is not None:
            try:
                payload = await self._requester(message)
            except Exception as exc:
                raise TransportError(f"HTTP transport request failed: {exc}") from exc
        else:
            if self._session is None:
                raise TransportError("http transport is not connected")
            try:
                async with self._session.post(self.config.base_url, json=message) as response:
                    response.raise_for_status()
                    payload = await response.json()
            except Exception as exc:  # pragma: no cover
                raise TransportError(f"HTTP transport request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise TransportError("HTTP transport response must be a JSON object.")
        return payload

    def connection_info(self) -> dict[str, Any]:
        return {"transport": "http", "base_url": self.config.base_url}

    def is_connected(self) -> bool:
        return self._requester is not None or self._session is not None
