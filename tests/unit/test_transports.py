from __future__ import annotations

import asyncio

import pytest

from naia_relay.errors import TransportError
from naia_relay.transports import (
    LineJsonFramer,
    McpStdioTransportAdapter,
    StdioTransportAdapter,
    TcpTransportAdapter,
)


class MemoryWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self.closed


@pytest.mark.asyncio
async def test_stdio_adapter_sends_and_receives_json_frames() -> None:
    reader = asyncio.StreamReader()
    writer = MemoryWriter()
    adapter = StdioTransportAdapter(reader=reader, writer=writer)
    await adapter.start()

    reader.feed_data(b'{"hello":"world"}\n')
    reader.feed_eof()

    await adapter.send({"ping": "pong"})
    received = await adapter.receive()

    assert writer.buffer == b'{"ping":"pong"}\n'
    assert received == {"hello": "world"}


def test_line_json_framer_rejects_oversized_payloads() -> None:
    framer = LineJsonFramer(max_message_size_bytes=8)

    with pytest.raises(TransportError):
        framer.encode({"hello": "world"})


def test_line_json_framer_rejects_malformed_json() -> None:
    framer = LineJsonFramer()

    with pytest.raises(TransportError):
        framer.decode(b'{"bad"\n')


@pytest.mark.asyncio
async def test_mcp_stdio_adapter_uses_newline_delimited_json() -> None:
    reader = asyncio.StreamReader()
    writer = MemoryWriter()
    adapter = McpStdioTransportAdapter(reader=reader, writer=writer)
    await adapter.start()

    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    reader.feed_data(b'{"jsonrpc":"2.0","id":1,"method":"initialize"}\n')
    reader.feed_eof()

    await adapter.send({"jsonrpc": "2.0", "id": 1, "result": {}})
    received = await adapter.receive()

    assert writer.buffer == b'{"id":1,"jsonrpc":"2.0","result":{}}\n'
    assert received == payload


@pytest.mark.asyncio
async def test_tcp_adapter_can_send_and_receive(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = asyncio.StreamReader()
    writer = MemoryWriter()
    reader.feed_data(b'{"reply":"ok"}\n')
    reader.feed_eof()

    async def fake_open_connection(host: str, port: int):
        assert host == "127.0.0.1"
        assert port == 9999
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    adapter = TcpTransportAdapter(host="127.0.0.1", port=9999)
    await adapter.start()
    await adapter.send({"hello": "tcp"})
    response = await adapter.receive()
    await adapter.stop()

    assert writer.buffer == b'{"hello":"tcp"}\n'
    assert response == {"reply": "ok"}


@pytest.mark.asyncio
async def test_tcp_adapter_handles_peer_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = asyncio.StreamReader()
    writer = MemoryWriter()
    reader.feed_eof()

    async def fake_open_connection(host: str, port: int):
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    adapter = TcpTransportAdapter(host="127.0.0.1", port=9999)
    await adapter.start()

    with pytest.raises(TransportError):
        await adapter.receive()
