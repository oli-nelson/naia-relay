from __future__ import annotations

import asyncio
import contextlib

import pytest

from naia_relay.runtime import serve_tep_stdio

from .helpers import (
    build_client_runtime,
    build_host_runtime,
    build_round_trip,
    register_demo_executor_content,
    stdio_round_trip,
)


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


@pytest.mark.asyncio
@pytest.mark.parametrize("rlp_transport", ["tcp"])
async def test_bridged_topology_supports_end_to_end_flows(rlp_transport: str) -> None:
    host = build_host_runtime()
    client = build_client_runtime(rlp_transport=rlp_transport)
    rlp_round_trip = build_round_trip(rlp_transport)

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await rlp_round_trip(host.handle_rlp_message, message)
        assert response is not None
        return response

    await host.start()
    await client.start()
    await register_demo_executor_content(host.handle_tep_message, "stdio")
    await client.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    tools = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    resources = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
    )
    prompts = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 3, "method": "prompts/list"},
    )
    tool_call = await stdio_round_trip(
        client.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"x": 2}},
        },
    )
    resource_read = await stdio_round_trip(
        client.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "file:///demo", "arguments": {"view": "bridge"}},
        },
    )
    prompt_get = await stdio_round_trip(
        client.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "prompts/get",
            "params": {"name": "prompt", "arguments": {"mode": "bridge"}},
        },
    )

    await client.stop()
    await host.stop()

    assert tools["result"]["tools"][0]["name"] == "demo"
    assert resources["result"]["resources"][0]["uri"] == "file:///demo"
    assert prompts["result"]["prompts"][0]["name"] == "prompt"
    assert tool_call["result"]["content"][0]["text"] == "demo:{'x': 2}"
    assert resource_read["result"]["contents"][0]["uri"] == "file:///demo"
    assert prompt_get["result"]["messages"][0]["content"]["name"] == "prompt"


@pytest.mark.asyncio
async def test_host_supports_multiple_concurrent_client_relays() -> None:
    host = build_host_runtime()
    client_a = build_client_runtime("tcp")
    client_b = build_client_runtime("tcp")

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await build_round_trip("tcp")(host.handle_rlp_message, message)
        assert response is not None
        return response

    await host.start()
    await client_a.start()
    await client_b.start()
    await register_demo_executor_content(host.handle_tep_message, "stdio")

    await client_a.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )
    await client_b.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    results = await asyncio.gather(
        client_a.handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "demo", "arguments": {"client": "a"}},
            }
        ),
        client_b.handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "demo", "arguments": {"client": "b"}},
            }
        ),
    )

    await client_a.stop()
    await client_b.stop()
    await host.stop()

    assert host.stats.attached_clients == 2
    assert results[0]["result"]["content"][0]["text"] == "demo:{'client': 'a'}"
    assert results[1]["result"]["content"][0]["text"] == "demo:{'client': 'b'}"


@pytest.mark.asyncio
async def test_bridged_reconnect_and_resnapshot_restore_updated_state() -> None:
    host = build_host_runtime()
    client = build_client_runtime("tcp")

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await build_round_trip("tcp")(host.handle_rlp_message, message)
        assert response is not None
        return response

    await host.start()
    await client.start()
    await register_demo_executor_content(host.handle_tep_message, "stdio")
    await client.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    client.on_rlp_disconnect()
    await stdio_round_trip(
        host.handle_tep_message,
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": "msg_tool_2",
            "session_id": "sess_exec",
            "payload": {"tools": [{"name": "demo2", "description": "Demo 2", "input_schema": {}}]},
        },
    )
    await client.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    tools = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 12, "method": "tools/list"},
    )

    await client.stop()
    await host.stop()

    assert {tool["name"] for tool in tools["result"]["tools"]} == {"demo", "demo2"}


@pytest.mark.asyncio
async def test_regression_bridged_tool_calls_forward_to_host_executor() -> None:
    host = build_host_runtime()
    client = build_client_runtime("tcp")

    async def forwarded_execute(payload):
        return {"content": [{"type": "text", "text": "host-forwarded"}]}

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await build_round_trip("tcp")(host.handle_rlp_message, message)
        assert response is not None
        return response

    await host.start()
    await client.start()
    await register_demo_executor_content(host.handle_tep_message, "stdio")
    host.rlp_handler.execute_tool = forwarded_execute
    await client.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    tool_call = await stdio_round_trip(
        client.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {}},
        },
    )

    await client.stop()
    await host.stop()

    assert tool_call["result"]["content"][0]["text"] == "host-forwarded"


@pytest.mark.asyncio
async def test_bridged_tool_call_reaches_stdio_executor_and_returns_real_output() -> None:
    host = build_host_runtime()
    client = build_client_runtime("tcp")
    host_reader = asyncio.StreamReader()
    executor_reader = asyncio.StreamReader()
    host_writer = LinkedWriter(executor_reader)
    executor_writer = LinkedWriter(host_reader)
    registered = asyncio.Event()

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await build_round_trip("tcp")(host.handle_rlp_message, message)
        assert response is not None
        return response

    async def fake_executor() -> None:
        from naia_relay.transports import StdioTransportAdapter

        adapter = StdioTransportAdapter(reader=executor_reader, writer=executor_writer)
        await adapter.start()
        await adapter.send(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_executor",
                "message_id": "msg_exec",
                "session_id": "sess_exec",
                "payload": {"executor_id": "fake_nvim", "metadata": {}},
            }
        )
        await adapter.receive()
        await adapter.send(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_tools",
                "message_id": "msg_tools",
                "session_id": "sess_exec",
                "payload": {
                    "tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]
                },
            }
        )
        await adapter.receive()
        registered.set()
        request = await adapter.receive()
        assert request["message_type"] == "execute_tool"
        assert request["payload"]["tool_name"] == "demo"
        await adapter.send(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "execution_result",
                "message_id": "msg_exec_result",
                "session_id": "sess_exec",
                "request_id": request["message_id"],
                "execution_id": request["execution_id"],
                "payload": {
                    "tool_name": "demo",
                    "result": {
                        "content": [{"type": "text", "text": "from-real-executor"}],
                        "isError": False,
                    },
                },
            }
        )
        await adapter.receive()
        executor_writer.close()
        await adapter.stop()

    await host.start()
    await client.start()
    host_task = asyncio.create_task(serve_tep_stdio(host, reader=host_reader, writer=host_writer))
    executor_task = asyncio.create_task(fake_executor())
    await registered.wait()

    await client.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    tool_call = await stdio_round_trip(
        client.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"x": 9}},
        },
    )

    await client.stop()
    await executor_task
    with contextlib.suppress(Exception):
        await host_task

    assert tool_call["result"]["content"][0]["text"] == "from-real-executor"
