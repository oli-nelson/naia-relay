from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from naia_relay.errors import TransportError
from naia_relay.transports.base import TransportAdapter
from naia_relay.transports.framing import LineJsonFramer


class McpStdioTransportAdapter(TransportAdapter):
    def __init__(
        self,
        reader: asyncio.StreamReader | None = None,
        writer: Any | None = None,
        *,
        max_message_size_bytes: int = 1_048_576,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._framer = LineJsonFramer(max_message_size_bytes=max_message_size_bytes)
        self._connected = False
        self._transport: asyncio.Transport | None = None
        self._read_pipe: Any | None = None

    async def start(self) -> None:
        if self._reader is None:
            self._reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            loop = asyncio.get_running_loop()
            self._read_pipe = os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0)
            self._transport, _ = await loop.connect_read_pipe(lambda: protocol, self._read_pipe)
        if self._writer is None:
            self._writer = sys.stdout.buffer
        self._connected = True

    async def stop(self) -> None:
        self._connected = False
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        if self._read_pipe is not None:
            self._read_pipe.close()
            self._read_pipe = None

    async def send(self, message: dict[str, Any]) -> None:
        if not self._connected:
            raise TransportError("mcp stdio transport is not connected")
        frame = self._framer.encode(message)
        self._writer.write(frame)
        if hasattr(self._writer, "drain"):
            await self._writer.drain()
        elif hasattr(self._writer, "flush"):
            self._writer.flush()

    async def receive(self) -> dict[str, Any]:
        if not self._connected:
            raise TransportError("mcp stdio transport is not connected")
        assert self._reader is not None
        frame = await self._reader.readline()
        if not frame:
            self._connected = False
            raise TransportError("mcp stdio transport reached EOF")
        return self._framer.decode(frame)

    def connection_info(self) -> dict[str, Any]:
        return {"transport": "stdio", "protocol": "mcp"}

    def is_connected(self) -> bool:
        return self._connected
