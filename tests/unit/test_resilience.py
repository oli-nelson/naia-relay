from __future__ import annotations

import asyncio

import pytest

from naia_relay.config import load_config
from naia_relay.errors import ProtocolError
from naia_relay.runtime import ClientRelayRuntime, DirectRelayRuntime, HostRelayRuntime


def load_inline_config(text: str):
    config, _ = load_config(cli_config_yaml=text)
    return config


@pytest.mark.asyncio
async def test_request_timeout_is_enforced() -> None:
    runtime = DirectRelayRuntime(
        config=load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay:\n  request_timeout_seconds: 1\n"
        )
    )

    async def slow_execute(name: str, arguments: dict[str, object]):
        await asyncio.sleep(1.1)
        return {"content": []}

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

    with pytest.raises(ProtocolError) as exc_info:
        await runtime.handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "demo", "arguments": {}},
            }
        )

    assert exc_info.value.code == "timeout"

    await runtime.stop()


@pytest.mark.asyncio
async def test_registration_timeout_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = DirectRelayRuntime(
        config=load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay:\n  request_timeout_seconds: 1\n"
        )
    )

    async def slow_register(
        self: object,
        message: dict[str, object],
    ) -> dict[str, object]:
        await asyncio.sleep(1.1)
        return {"protocol": "tep", "version": "1.0", "message_type": "noop", "payload": {}}

    monkeypatch.setattr(type(runtime.tep_handler), "handle_message", slow_register)
    await runtime.start()

    with pytest.raises(ProtocolError, match="Request timed out") as exc_info:
        await runtime.handle_tep_message(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_tools",
                "message_id": "msg_reg",
                "session_id": "sess_exec",
                "payload": {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
            }
        )

    assert exc_info.value.code == "timeout"

    await runtime.stop()


@pytest.mark.asyncio
async def test_initialization_timeout_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = DirectRelayRuntime(
        config=load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay:\n  request_timeout_seconds: 1\n"
        )
    )

    async def slow_initialize(
        self: object,
        message: dict[str, object],
    ) -> dict[str, object] | None:
        await asyncio.sleep(1.1)
        return {"jsonrpc": "2.0", "id": 1, "result": {}}

    monkeypatch.setattr(type(runtime.mcp_handler), "handle_message", slow_initialize)
    await runtime.start()

    with pytest.raises(ProtocolError, match="Request timed out") as exc_info:
        await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert exc_info.value.code == "timeout"

    await runtime.stop()


@pytest.mark.asyncio
async def test_backpressure_limit_is_enforced() -> None:
    runtime = DirectRelayRuntime(
        config=load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay:\n  max_in_flight_requests: 1\n"
        )
    )
    await runtime.start()
    runtime.stats.active_requests = 1

    with pytest.raises(ProtocolError) as exc_info:
        await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert exc_info.value.code == "backpressure_limit_exceeded"

    await runtime.stop()


@pytest.mark.asyncio
async def test_queue_depth_limit_is_enforced() -> None:
    runtime = DirectRelayRuntime(
        config=load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay:\n  max_queue_depth: 1\n"
        )
    )
    await runtime.start()
    runtime.stats.queue_depth = 1

    with pytest.raises(ProtocolError) as exc_info:
        await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert exc_info.value.code == "slow_consumer_limit_exceeded"
    assert runtime.stats.slow_consumer_rejections == 1

    await runtime.stop()


@pytest.mark.asyncio
async def test_heartbeat_timeout_is_detected() -> None:
    runtime = HostRelayRuntime(
        config=load_inline_config(
            "role: host\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
            "relay:\n  heartbeat_timeout_seconds: 1\n"
        )
    )
    await runtime.start()
    runtime.last_heartbeat_at -= 2

    assert runtime.heartbeat_expired() is True

    await runtime.stop()


@pytest.mark.asyncio
async def test_client_bind_retries_and_stale_rejection() -> None:
    host = HostRelayRuntime(
        config=load_inline_config(
            "role: host\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    client = ClientRelayRuntime(
        config=load_inline_config(
            "role: client\n"
            "mcp:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  port: 9001\n"
            "relay:\n  reconnect_attempts: 1\n"
        )
    )
    await host.start()
    await client.start()
    client.mark_stale()

    with pytest.raises(ProtocolError) as exc_info:
        await client.call_tool("demo", {})

    assert exc_info.value.code == "stale_registry"

    response = await client.bind_to_host(host)
    assert response["payload"]["status"] == "ok"
    assert client.registry.stale is False

    await client.stop()
    await host.stop()


@pytest.mark.asyncio
async def test_connection_timeout_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    host = HostRelayRuntime(
        config=load_inline_config(
            "role: host\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    client = ClientRelayRuntime(
        config=load_inline_config(
            "role: client\n"
            "mcp:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  port: 9001\n"
            "relay:\n  connection_timeout_seconds: 1\n  reconnect_attempts: 0\n"
        )
    )

    async def slow_handle(
        self: HostRelayRuntime,
        message: dict[str, object],
    ) -> dict[str, object]:
        await asyncio.sleep(1.1)
        return {
            "protocol": "rlp",
            "version": "1.0",
            "message_type": "bind_session",
            "message_id": "timeout",
            "relay_session_id": self.session_id,
            "payload": {"status": "ok", "details": {}},
        }

    await host.start()
    await client.start()
    monkeypatch.setattr(HostRelayRuntime, "handle_rlp_message", slow_handle)

    with pytest.raises(ProtocolError, match="Relay-link bind timed out") as exc_info:
        await client.bind_to_host(host)

    assert exc_info.value.code == "timeout"
    assert client.registry.stale is True

    await client.stop()
    await host.stop()


@pytest.mark.asyncio
async def test_transport_failures_are_mapped_to_structured_protocol_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = HostRelayRuntime(
        config=load_inline_config(
            "role: host\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    client = ClientRelayRuntime(
        config=load_inline_config(
            "role: client\n"
            "mcp:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  port: 9001\n"
            "relay:\n  reconnect_attempts: 0\n"
        )
    )

    async def broken_handle(
        self: HostRelayRuntime,
        message: dict[str, object],
    ) -> dict[str, object]:
        raise RuntimeError("simulated transport break")

    monkeypatch.setattr(HostRelayRuntime, "handle_rlp_message", broken_handle)
    await host.start()
    await client.start()

    with pytest.raises(ProtocolError) as exc_info:
        await client.bind_to_host(host)

    assert exc_info.value.code == "transport_failure"
    assert exc_info.value.data["exception_type"] == "RuntimeError"

    await client.stop()
    await host.stop()


@pytest.mark.asyncio
async def test_slow_consumer_rejection_does_not_corrupt_protocol_state() -> None:
    runtime = DirectRelayRuntime(
        config=load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
            "relay:\n  max_queue_depth: 1\n"
        )
    )
    await runtime.start()
    runtime.stats.queue_depth = 1

    with pytest.raises(ProtocolError):
        await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    runtime.stats.queue_depth = 0
    response = await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert response is not None
    assert "result" in response

    await runtime.stop()
