from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from naia_relay.config import load_config
from naia_relay.runtime import ClientRelayRuntime, DirectRelayRuntime, HostRelayRuntime
from naia_relay.transports import (
    HttpTransportAdapter,
    HttpTransportConfig,
    LineJsonFramer,
    StdioTransportAdapter,
    TcpTransportAdapter,
)


def load_inline_config(text: str):
    config, _ = load_config(cli_config_yaml=text)
    return config


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


async def stdio_round_trip(
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]],
    message: dict[str, Any],
) -> dict[str, Any] | None:
    client_reader = asyncio.StreamReader()
    client_writer = MemoryWriter()
    server_reader = asyncio.StreamReader()
    server_writer = MemoryWriter()

    client = StdioTransportAdapter(reader=client_reader, writer=client_writer)
    server = StdioTransportAdapter(reader=server_reader, writer=server_writer)
    await client.start()
    await server.start()

    await client.send(message)
    server_reader.feed_data(bytes(client_writer.buffer))
    server_reader.feed_eof()
    inbound = await server.receive()
    response = await handler(inbound)
    if response is not None:
        await server.send(response)
        client_reader.feed_data(bytes(server_writer.buffer))
        client_reader.feed_eof()
        result = await client.receive()
    else:
        result = None

    await client.stop()
    await server.stop()
    return result


class LinkedWriter:
    def __init__(self, peer_reader: asyncio.StreamReader) -> None:
        self.peer_reader = peer_reader
        self.closed = False

    def write(self, data: bytes) -> None:
        self.peer_reader.feed_data(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True
        self.peer_reader.feed_eof()

    async def wait_closed(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self.closed


async def tcp_round_trip(
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]],
    message: dict[str, Any],
) -> dict[str, Any] | None:
    framer = LineJsonFramer()
    client_reader = asyncio.StreamReader()
    server_reader = asyncio.StreamReader()
    client_writer = LinkedWriter(server_reader)
    server_writer = LinkedWriter(client_reader)

    async def fake_open_connection(host: str, port: int):
        return client_reader, client_writer

    async def handle_server_side() -> None:
        line = await server_reader.readline()
        inbound = framer.decode(line)
        response = await handler(inbound)
        if response is not None:
            server_writer.write(framer.encode(response))
            await server_writer.drain()

    original_open_connection = asyncio.open_connection
    asyncio.open_connection = fake_open_connection  # type: ignore[assignment]
    try:
        adapter = TcpTransportAdapter(host="127.0.0.1", port=9999)
        await adapter.start()
        server_task = asyncio.create_task(handle_server_side())
        await adapter.send(message)
        response = await adapter.receive()
        await server_task
        await adapter.stop()
        return response
    finally:
        asyncio.open_connection = original_open_connection  # type: ignore[assignment]


async def http_round_trip(
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]],
    message: dict[str, Any],
) -> dict[str, Any] | None:
    async def requester(payload: dict[str, Any]) -> dict[str, Any]:
        response = await handler(payload)
        assert response is not None
        return response

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"),
        requester=requester,
    )
    await adapter.start()
    response = await adapter.round_trip(message)
    await adapter.stop()
    return response


async def register_demo_executor_content(
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]],
    transport: str,
) -> None:
    round_trip = {
        "stdio": stdio_round_trip,
        "tcp": tcp_round_trip,
    }[transport]

    await round_trip(
        handler,
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": "msg_tool",
            "session_id": "sess_exec",
            "payload": {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
        },
    )
    await round_trip(
        handler,
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_resources",
            "message_id": "msg_resource",
            "session_id": "sess_exec",
            "payload": {"resources": [{"uri": "file:///demo", "name": "demo"}]},
        },
    )
    await round_trip(
        handler,
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_prompts",
            "message_id": "msg_prompt",
            "session_id": "sess_exec",
            "payload": {"prompts": [{"name": "prompt", "description": "Prompt"}]},
        },
    )


def build_round_trip(transport: str):
    return {
        "stdio": stdio_round_trip,
        "tcp": tcp_round_trip,
        "http": http_round_trip,
    }[transport]


def build_direct_runtime(mcp_transport: str, executor_transport: str) -> DirectRelayRuntime:
    mcp_port_block = "  port: 9101\n" if mcp_transport == "http" else ""
    executor_port_block = "  port: 9102\n" if executor_transport == "tcp" else ""
    config = load_inline_config(
        "role: direct\n"
        f"mcp:\n  transport: {mcp_transport}\n"
        f"{mcp_port_block}"
        f"executor:\n  transport: {executor_transport}\n"
        f"{executor_port_block}"
    )
    return DirectRelayRuntime(config=config)


def build_host_runtime() -> HostRelayRuntime:
    config = load_inline_config(
        "role: host\n"
        "executor:\n  transport: stdio\n"
        "relay_link:\n  transport: tcp\n  bind_port: 9201\n"
    )
    return HostRelayRuntime(config=config)


def build_client_runtime(rlp_transport: str = "tcp") -> ClientRelayRuntime:
    port_line = "  port: 9201\n" if rlp_transport == "tcp" else ""
    config = load_inline_config(
        "role: client\n"
        "mcp:\n  transport: stdio\n"
        f"relay_link:\n  transport: {rlp_transport}\n"
        f"{port_line}"
    )
    return ClientRelayRuntime(config=config)
