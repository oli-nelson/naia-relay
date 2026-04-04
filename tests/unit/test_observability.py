from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from naia_relay.config import load_config
from naia_relay.errors import ProtocolError
from naia_relay.runtime import ClientRelayRuntime, create_runtime


def load_inline_config(text: str):
    config, _ = load_config(cli_config_yaml=text)
    return config


@pytest.mark.asyncio
async def test_runtime_logs_include_role_and_session_identity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
        )
    )

    with caplog.at_level(logging.INFO):
        await runtime.start()
        await runtime.stop()

    startup = next(
        record for record in caplog.records if record.message == "starting relay runtime"
    )
    assert startup.role == "direct"
    assert startup.protocol_side == "runtime"
    assert startup.session_id == runtime.session_id


@pytest.mark.asyncio
async def test_runtime_logs_include_request_identifier(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
        )
    )
    await runtime.start()

    with caplog.at_level(logging.DEBUG):
        await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 7, "method": "tools/list"})

    record = next(record for record in caplog.records if record.message == "handling mcp message")
    assert record.protocol_side == "mcp"
    assert record.request_id == "7"

    await runtime.stop()


@pytest.mark.asyncio
async def test_execution_logs_include_execution_identifier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
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

    await runtime.handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {}},
        }
    )

    record = next(
        record for record in caplog.records if record.message == "starting tool execution"
    )
    assert record.protocol_side == "execution"
    assert record.execution_id.startswith("exec_")

    await runtime.stop()


@pytest.mark.asyncio
async def test_validation_failures_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
        )
    )
    await runtime.start()

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValidationError):
            await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 9})

    assert any("protocol validation failed" in record.message for record in caplog.records)
    assert runtime.stats.validation_failures >= 1

    await runtime.stop()


@pytest.mark.asyncio
async def test_disconnect_and_reconnect_events_are_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    host = create_runtime(
        load_inline_config(
            "role: host\n"
            "executor:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    client = ClientRelayRuntime(
        config=load_inline_config(
            "role: client\n"
            "mcp:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  port: 9001\n"
        )
    )
    await host.start()
    await client.start()

    with caplog.at_level(logging.INFO):
        client.on_rlp_disconnect()
        with pytest.raises(ProtocolError):
            await client.call_tool("demo", {})
        await client.bind_to_host(host)  # host has an empty snapshot, which is okay

    messages = [record.message for record in caplog.records]
    assert "client relay marked stale after relay-link disconnect" in messages
    assert "relay-link bind succeeded" in messages
    assert client.stats.disconnects == 1
    assert client.stats.reconnect_attempts >= 1

    await client.stop()
    await host.stop()


@pytest.mark.asyncio
async def test_runtime_counters_update_for_basic_activity() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: stdio\n"
        )
    )
    await runtime.start()
    await runtime.handle_mcp_message({"jsonrpc": "2.0", "id": 21, "method": "tools/list"})
    await runtime.stop()

    assert runtime.stats.completed_requests >= 1
