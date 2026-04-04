from __future__ import annotations

import asyncio
from typing import Any

from naia_relay.errors import TransportError
from naia_relay.transports.base import TransportAdapter
from naia_relay.transports.framing import LineJsonFramer


class TcpTransportAdapter(TransportAdapter):
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int,
        max_message_size_bytes: int = 1_048_576,
    ) -> None:
        self.host = host
        self.port = port
        self._framer = LineJsonFramer(max_message_size_bytes=max_message_size_bytes)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def start(self) -> None:
        try:
            self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        except Exception as exc:  # pragma: no cover
            message = f"Failed to connect to TCP peer {self.host}:{self.port}: {exc}"
            raise TransportError(message) from exc

    async def stop(self) -> None:
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def send(self, message: dict[str, Any]) -> None:
        if self._writer is None:
            raise TransportError("tcp transport is not connected")
        self._writer.write(self._framer.encode(message))
        await self._writer.drain()

    async def receive(self) -> dict[str, Any]:
        if self._reader is None:
            raise TransportError("tcp transport is not connected")
        frame = await self._reader.readline()
        if not frame:
            await self.stop()
            raise TransportError("tcp peer disconnected")
        return self._framer.decode(frame)

    def connection_info(self) -> dict[str, Any]:
        return {"transport": "tcp", "host": self.host, "port": self.port}

    def is_connected(self) -> bool:
        return (
            self._reader is not None
            and self._writer is not None
            and not self._writer.is_closing()
        )
