from __future__ import annotations

import asyncio
import json

import pytest

from naia_relay.config import load_config
from naia_relay.errors import ProtocolError
from naia_relay.runtime import (
    ClientRelayRuntime,
    HostRelayRuntime,
    create_runtime,
    run_from_config,
    serve_mcp_stdio,
    serve_tep_stdio,
)
from naia_relay.runtime.relay import _handle_mcp_http_payload


def load_inline_config(text: str):
    config, _ = load_config(cli_config_yaml=text)
    return config


@pytest.mark.asyncio
async def test_direct_runtime_starts_from_valid_config() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
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
            "executor:\n  transport: tcp\n  port: 9002\n"
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
            "executor:\n  transport: tcp\n  port: 9002\n"
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
            "executor:\n  transport: tcp\n  port: 9002\n"
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
            "executor:\n  transport: tcp\n  port: 9002\n"
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
        "executor:\n  transport: tcp\n  port: 9002\n"
        "relay_link:\n  transport: tcp\n  bind_host: 127.0.0.1\n  bind_port: 0\n"
    )

    runtime = await run_from_config(config, once=True, ready_file=ready_file)
    payload = json.loads(ready_file.read_text(encoding="utf-8"))

    assert runtime.role == "host"
    assert payload["event"] == "listener_ready"
    assert payload["role"] == "host"
    assert payload["listeners"]["relay_link"]["port"] == 54321


@pytest.mark.asyncio
async def test_executor_tcp_listener_writes_readiness_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSocket:
        def getsockname(self):
            return ("127.0.0.1", 65432)

    class FakeServer:
        sockets = [FakeSocket()]

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    started: list[tuple[str, int]] = []

    async def fake_start_server(handler, host, port):
        started.append((host, port))
        return FakeServer()

    monkeypatch.setattr(asyncio, "start_server", fake_start_server)
    ready_file = tmp_path / "ready.json"
    config = load_inline_config(
        "role: host\n"
        "executor:\n  transport: tcp\n  bind_host: 127.0.0.1\n  bind_port: 0\n"
        "relay_link:\n  transport: tcp\n  bind_host: 127.0.0.1\n  bind_port: 61280\n"
    )

    runtime = await run_from_config(config, once=True, ready_file=ready_file)
    payload = json.loads(ready_file.read_text(encoding="utf-8"))

    assert runtime.role == "host"
    assert ("127.0.0.1", 0) in started
    assert payload["listeners"]["executor"]["host"] == "127.0.0.1"
    assert payload["listeners"]["executor"]["port"] == 65432


@pytest.mark.asyncio
async def test_run_from_config_starts_mcp_http_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[tuple[str, int]] = []

    async def fake_serve_mcp_http(runtime, *, bind_host: str, bind_port: int) -> None:
        started.append((bind_host, bind_port))
        runtime.resolved_listeners["mcp"] = {
            "transport": "http",
            "host": bind_host,
            "port": bind_port,
        }

    monkeypatch.setattr("naia_relay.runtime.relay.serve_mcp_http", fake_serve_mcp_http)
    config = load_inline_config(
        "role: direct\n"
        "mcp:\n  transport: http\n  host: 127.0.0.1\n  port: 18080\n"
        "executor:\n  transport: tcp\n  port: 9002\n"
    )

    runtime = await run_from_config(config, once=True)

    assert runtime.role == "direct"
    assert started == [("127.0.0.1", 18080)]
    assert runtime.resolved_listeners["mcp"]["transport"] == "http"


@pytest.mark.asyncio
async def test_serve_mcp_http_registers_root_and_mcp_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes: list[tuple[str, object]] = []

    class FakeRouter:
        def add_post(self, path: str, handler: object) -> None:
            routes.append((path, handler))

    class FakeApp:
        def __init__(self) -> None:
            self.router = FakeRouter()

    class FakeRunner:
        def __init__(self, app: object) -> None:
            self.app = app

        async def setup(self) -> None:
            return None

        async def cleanup(self) -> None:
            return None

    class FakeSite:
        def __init__(self, runner: object, host: str, port: int) -> None:
            self.runner = runner
            self.host = host
            self.port = port

        async def start(self) -> None:
            return None

    monkeypatch.setattr("naia_relay.runtime.relay.web.Application", FakeApp)
    monkeypatch.setattr("naia_relay.runtime.relay.web.AppRunner", FakeRunner)
    monkeypatch.setattr("naia_relay.runtime.relay.web.TCPSite", FakeSite)

    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: http\n  host: 127.0.0.1\n  port: 18085\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
        )
    )
    await runtime.start()
    try:
        from naia_relay.runtime import serve_mcp_http

        await serve_mcp_http(runtime, bind_host="127.0.0.1", bind_port=18085)
    finally:
        await runtime.stop()

    assert [path for path, _ in routes] == ["/", "/mcp"]


@pytest.mark.asyncio
async def test_run_from_config_with_mcp_http_and_executor_stdio_serves_tep_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_http: list[tuple[str, int]] = []
    served_tep: list[str] = []

    async def fake_serve_mcp_http(runtime, *, bind_host: str, bind_port: int) -> None:
        started_http.append((bind_host, bind_port))
        runtime.resolved_listeners["mcp"] = {
            "transport": "http",
            "host": bind_host,
            "port": bind_port,
        }

    async def fake_serve_tep_stdio(runtime, **_: object) -> None:
        served_tep.append(runtime.role)
        await runtime.stop()

    monkeypatch.setattr("naia_relay.runtime.relay.serve_mcp_http", fake_serve_mcp_http)
    monkeypatch.setattr("naia_relay.runtime.relay.serve_tep_stdio", fake_serve_tep_stdio)
    config = load_inline_config(
        "role: direct\n"
        "mcp:\n  transport: http\n  host: 127.0.0.1\n  port: 18084\n"
        "executor:\n  transport: stdio\n"
    )

    runtime = await run_from_config(config, once=False)

    assert runtime.role == "direct"
    assert started_http == [("127.0.0.1", 18084)]
    assert served_tep == ["direct"]


@pytest.mark.asyncio
async def test_serve_mcp_stdio_returns_newline_delimited_initialize_response() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: stdio\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
        )
    )
    reader = asyncio.StreamReader()

    class BufferWriter:
        def __init__(self) -> None:
            self.buffer = bytearray()

        def write(self, data: bytes) -> None:
            self.buffer.extend(data)

        def flush(self) -> None:
            return None

    writer = BufferWriter()
    request_body = (
        b'{"jsonrpc":"2.0","id":1,"method":"initialize",'
        b'"params":{"protocolVersion":"2025-06-18","capabilities":{}}}\n'
    )
    reader.feed_data(request_body)
    reader.feed_eof()

    await runtime.start()
    await serve_mcp_stdio(runtime, reader=reader, writer=writer)

    assert writer.buffer.endswith(b"\n")
    assert b'"protocolVersion":"2025-06-18"' in writer.buffer


@pytest.mark.asyncio
async def test_mcp_http_payload_returns_initialize_response() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: http\n  host: 127.0.0.1\n  port: 18081\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
        )
    )

    await runtime.start()
    try:
        status, payload = await _handle_mcp_http_payload(
            runtime,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
            },
        )
        assert status == 200
        assert payload is not None
        assert payload["result"]["protocolVersion"] == "2025-06-18"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_mcp_http_payload_returns_accepted_for_notifications() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: http\n  host: 127.0.0.1\n  port: 18082\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
        )
    )

    await runtime.start()
    try:
        status, payload = await _handle_mcp_http_payload(
            runtime,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        assert status == 202
        assert payload is None
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_mcp_http_payload_rejects_non_object_input() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: direct\n"
            "mcp:\n  transport: http\n  host: 127.0.0.1\n  port: 18083\n"
            "executor:\n  transport: tcp\n  port: 9002\n"
        )
    )

    await runtime.start()
    try:
        status, payload = await _handle_mcp_http_payload(runtime, [])
        assert status == 400
        assert payload is not None
        assert payload["error"]["code"] == -32600
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_serve_tep_stdio_returns_structured_validation_error_and_keeps_running() -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: host\n"
            "executor:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
        )
    )
    reader = asyncio.StreamReader()

    class BufferWriter:
        def __init__(self) -> None:
            self.buffer = bytearray()

        def write(self, data: bytes) -> None:
            self.buffer.extend(data)

        def flush(self) -> None:
            return None

    writer = BufferWriter()
    invalid_request = (
        b'{"protocol":"tep","version":"1.0","message_type":"register_executor",'
        b'"message_id":"msg_bad","session_id":"sess_exec","payload":{"executor_id":"nvim",'
        b'"metadata":["bad"]}}\n'
    )
    valid_request = (
        b'{"protocol":"tep","version":"1.0","message_type":"register_executor",'
        b'"message_id":"msg_ok","session_id":"sess_exec","payload":{"executor_id":"nvim",'
        b'"metadata":[]}}\n'
    )
    reader.feed_data(invalid_request + valid_request)
    reader.feed_eof()

    await runtime.start()
    await serve_tep_stdio(runtime, reader=reader, writer=writer)

    lines = [json.loads(line) for line in writer.buffer.decode("utf-8").splitlines() if line]
    assert lines[0]["message_type"] == "register_executor_response"
    assert lines[0]["payload"]["status"] == "error"
    assert lines[0]["payload"]["code"] == "invalid_payload"
    assert "metadata" in lines[0]["payload"]["message"]
    assert lines[1]["payload"]["status"] == "ok"


@pytest.mark.asyncio
async def test_run_from_config_auto_binds_client_tcp_relay_link(monkeypatch) -> None:
    runtime = create_runtime(
        load_inline_config(
            "role: client\n"
            "mcp:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  port: 9001\n"
        )
    )

    called = False

    async def fake_auto_bind(self) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("naia_relay.runtime.relay.create_runtime", lambda config: runtime)
    monkeypatch.setattr(type(runtime), "_auto_bind_tcp_relay_link", fake_auto_bind)

    await run_from_config(runtime.config, once=True)

    assert called is True
