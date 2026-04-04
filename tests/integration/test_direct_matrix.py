from __future__ import annotations

import pytest

from .helpers import (
    build_direct_runtime,
    build_round_trip,
    register_demo_executor_content,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mcp_transport", "executor_transport"),
    [
        ("stdio", "tcp"),
        ("tcp", "stdio"),
        ("stdio", "http"),
        ("http", "stdio"),
    ],
)
async def test_direct_topology_matrix_supports_end_to_end_flows(
    mcp_transport: str,
    executor_transport: str,
) -> None:
    runtime = build_direct_runtime(mcp_transport, executor_transport)
    mcp_round_trip = build_round_trip(mcp_transport)

    await runtime.start()
    await register_demo_executor_content(runtime.handle_tep_message, executor_transport)

    initialize = await mcp_round_trip(
        runtime.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
        },
    )
    tools = await mcp_round_trip(
        runtime.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    resources = await mcp_round_trip(
        runtime.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list"},
    )
    prompts = await mcp_round_trip(
        runtime.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 4, "method": "prompts/list"},
    )
    tool_call = await mcp_round_trip(
        runtime.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"x": 1}},
        },
    )
    resource_read = await mcp_round_trip(
        runtime.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {"uri": "file:///demo", "arguments": {"view": "full"}},
        },
    )
    prompt_get = await mcp_round_trip(
        runtime.handle_mcp_message,
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "prompts/get",
            "params": {"name": "prompt", "arguments": {"mode": "test"}},
        },
    )

    await runtime.stop()

    assert initialize is not None
    assert initialize["result"]["protocolVersion"] == "2025-06-18"
    assert tools["result"]["tools"][0]["name"] == "demo"
    assert resources["result"]["resources"][0]["uri"] == "file:///demo"
    assert prompts["result"]["prompts"][0]["name"] == "prompt"
    assert tool_call["result"]["content"][0]["text"] == "demo:{'x': 1}"
    assert resource_read["result"]["contents"][0]["uri"] == "file:///demo"
    assert prompt_get["result"]["messages"][0]["content"]["name"] == "prompt"
