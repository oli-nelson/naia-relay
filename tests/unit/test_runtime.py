from __future__ import annotations

import asyncio
import json

import pytest

from naia_relay.config import load_config
from naia_relay.errors import ProtocolError
from naia_relay.runtime import ClientRelayRuntime, HostRelayRuntime, create_runtime, run_from_config


def load_inline_config(text: str):
    config, _ = load_config(cli_config_yaml=text)
    return config


@pytest.mark.asyncio
async def test_direct_runtime_starts_from_valid_config() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
        )
    )
    await runtime.start()
    await runtime.stop()
    assert runtime.role == "direct"


@pytest.mark.asyncio
async def test_host_runtime_starts_from_valid_config() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: host\n"
            "executor:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    await runtime.start()
    await runtime.stop()
    assert runtime.role == "host"


@pytest.mark.asyncio
async def test_client_runtime_starts_from_valid_config() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: client\nmcp:\n  transport: stdio\nrelay_link:\n  transport: tcp\n  port: 9001\n"
        )
    )
    await runtime.start()
    await runtime.stop()
    assert runtime.role == "client"


@pytest.mark.asyncio
async def test_direct_runtime_routes_tool_execution() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
        )
    )
    await runtime.start()
    await runtime.handle_tep_message(
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": "msg_1",
            "session_id": "sess_exec",
            "payload": {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
        }
    )
    response = await runtime.handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"x": 1}},
        }
    )
    await runtime.stop()
    assert response["result"]["content"][0]["text"] == "demo:{'x': 1}"


@pytest.mark.asyncio
async def test_host_accepts_client_and_client_binds() -> None:
    host = HostRelayRuntime(
        config=load_inline_config(
            "role: host\n"
            "executor:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    client = ClientRelayRuntime(
        config=load_inline_config(
            "role: client\nmcp:\n  transport: stdio\nrelay_link:\n  transport: tcp\n  port: 9001\n"
        )
    )
    await host.start()
    await client.start()

    await host.handle_tep_message(
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": "msg_1",
            "session_id": "sess_exec",
            "payload": {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
        }
    )
    response = await client.bind_to_host(host)

    await client.stop()
    await host.stop()

    assert response["payload"]["status"] == "ok"
    assert host.stats.attached_clients == 1


@pytest.mark.asyncio
async def test_client_rejects_operations_while_stale() -> None:
    client = ClientRelayRuntime(
        config=load_inline_config(
            "role: client\nmcp:\n  transport: stdio\nrelay_link:\n  transport: tcp\n  port: 9001\n"
        )
    )
    await client.start()
    client.mark_stale()

    with pytest.raises(ProtocolError):
        await client.call_tool("demo", {})

    await client.stop()


@pytest.mark.asyncio
async def test_shutdown_waits_for_inflight_request_completion() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
            "relay:\n  request_timeout_seconds: 2\n"
        )
    )

    async def slow_execute(name: str, arguments: dict[str, object]):
        await asyncio.sleep(0.2)
        return {"content": [{"type": "text", "text": f"{name}:{arguments}"}]}

    runtime.mcp_handler.execute_tool = slow_execute
    await runtime.start()
    await runtime.handle_tep_message(
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": "msg_1",
            "session_id": "sess_exec",
            "payload": {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
        }
    )

    request_task = asyncio.create_task(
        runtime.handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "demo", "arguments": {"x": 1}},
            }
        )
    )
    await asyncio.sleep(0.05)
    await runtime.stop()

    result = await request_task

    assert runtime.started is False
    assert result is not None
    assert runtime.stats.completed_requests >= 1


@pytest.mark.asyncio
async def test_host_dynamic_listener_writes_readiness_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSocket:
        def getsockname(self):
            return ("127.0.0.1", 54321)

    class FakeServer:
        sockets = [FakeSocket()]

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    async def fake_start_server(handler, host, port):
        assert host == "127.0.0.1"
        assert port == 0
        return FakeServer()

    monkeypatch.setattr(asyncio, "start_server", fake_start_server)
    ready_file = tmp_path / "ready.json"
    config = load_inline_config(
        "role: host\n"
        "executor:\n  transport: stdio\n"
        "relay_link:\n  transport: tcp\n  bind_host: 127.0.0.1\n  bind_port: 0\n"
    )

    runtime = await run_from_config(config, once=True, ready_file=ready_file)
    payload = json.loads(ready_file.read_text(encoding="utf-8"))

    assert runtime.role == "host"
    assert payload["event"] == "listener_ready"
    assert payload["role"] == "host"
    assert payload["listeners"]["relay_link"]["port"] == 54321
