from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import tempfile
import textwrap
import uuid
from pathlib import Path

import aiohttp
import pytest

ROOT = Path(__file__).resolve().parents[2]
PYTHON = str(ROOT / ".venv/bin/python")
RUN_CODEX_E2E = os.environ.get("RUN_CODEX_E2E") == "1"


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"


async def write_line_json(
    writer: asyncio.StreamWriter,
    payload: dict[str, object],
) -> None:
    writer.write(json.dumps(payload).encode("utf-8") + b"\n")
    await writer.drain()


async def read_line_json(reader: asyncio.StreamReader) -> dict[str, object] | None:
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


async def read_stderr(process: asyncio.subprocess.Process) -> str:
    if process.stderr is None:
        return ""
    try:
        data = await asyncio.wait_for(process.stderr.read(), timeout=0.5)
    except Exception:
        return ""
    return data.decode("utf-8", errors="replace")


async def terminate_process(process: asyncio.subprocess.Process) -> None:
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except Exception:
        try:
            process.kill()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except Exception:
            return


@pytest.mark.skipif(
    not RUN_CODEX_E2E or shutil.which("codex") is None,
    reason="requires local codex CLI and RUN_CODEX_E2E=1",
)
@pytest.mark.asyncio
async def test_codex_can_temporarily_see_http_mcp_server_without_touching_global_config() -> None:
    """Manual E2E probe.

    This test intentionally avoids modifying ~/.codex/config.toml.

    Codex does not currently expose a non-interactive equivalent of the `/mcp`
    slash command that also proves a live connection without sending a model
    prompt. So this test does two things:

    1. proves the relay is really serving MCP over HTTP and exposing a tool
       through direct HTTP MCP calls
    2. proves Codex can see a temporary HTTP MCP server configuration via
       `codex mcp get --json -c ...` using only per-command config overrides
    """

    http_port = allocate_port()
    relay_config = textwrap.dedent(
        f"""\
        role: direct
        mcp:
          transport: http
          host: 127.0.0.1
          port: {http_port}
        executor:
          transport: stdio
        """
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as config_file:
        config_file.write(relay_config)
        config_path = config_file.name

    relay = await asyncio.create_subprocess_exec(
        PYTHON,
        "-m",
        "naia_relay.cli",
        "--config-file",
        config_path,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        assert relay.stdin is not None
        assert relay.stdout is not None

        await write_line_json(
            relay.stdin,
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_executor",
                "message_id": new_message_id(),
                "session_id": "sess_codex_http_test",
                "payload": {
                    "executor_id": "pytest_stdio_exec",
                    "display_name": "pytest stdio executor",
                    "capabilities": {"tools": True, "resources": False, "prompts": False},
                    "metadata": {},
                },
            },
        )
        try:
            register_executor_response = await asyncio.wait_for(
                read_line_json(relay.stdout),
                timeout=3,
            )
        except TimeoutError as exc:  # pragma: no cover - local e2e diagnostics
            stderr_text = await read_stderr(relay)
            raise AssertionError(
                "timed out waiting for register_executor response "
                f"from relay stderr={stderr_text!r}"
            ) from exc
        assert register_executor_response is not None
        assert register_executor_response["payload"]["status"] == "ok"

        await write_line_json(
            relay.stdin,
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_tools",
                "message_id": new_message_id(),
                "session_id": "sess_codex_http_test",
                "payload": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo tool for Codex HTTP MCP E2E test",
                            "input_schema": {
                                "type": "object",
                                "properties": {"message": {"type": "string"}},
                                "required": ["message"],
                            },
                            "metadata": {},
                        }
                    ]
                },
            },
        )
        try:
            register_tools_response = await asyncio.wait_for(
                read_line_json(relay.stdout),
                timeout=3,
            )
        except TimeoutError as exc:  # pragma: no cover - local e2e diagnostics
            stderr_text = await read_stderr(relay)
            raise AssertionError(
                "timed out waiting for register_tools response "
                f"from relay stderr={stderr_text!r}"
            ) from exc
        assert register_tools_response is not None
        assert register_tools_response["payload"]["status"] == "ok"

        async with aiohttp.ClientSession() as session:
            deadline = asyncio.get_running_loop().time() + 5
            while True:
                try:
                    async with session.post(
                        f"http://127.0.0.1:{http_port}/",
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
                        },
                    ) as response:
                        initialize_payload = await response.json()
                    break
                except Exception:
                    if asyncio.get_running_loop().time() >= deadline:
                        raise
                    await asyncio.sleep(0.05)

            assert initialize_payload["result"]["protocolVersion"] == "2025-06-18"

            async with session.post(
                f"http://127.0.0.1:{http_port}/",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ) as response:
                tools_payload = await response.json()

        assert tools_payload["result"]["tools"][0]["name"] == "echo"

        codex_name = "temp_naia_http_test"
        codex_result = subprocess.run(
            [
                "codex",
                "mcp",
                "get",
                codex_name,
                "--json",
                "-c",
                f'mcp_servers.{codex_name}.url="http://127.0.0.1:{http_port}/"',
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        codex_payload = json.loads(
            "\n".join(
                line
                for line in codex_result.stdout.splitlines()
                if not line.startswith("WARNING:")
            )
        )

        assert codex_payload["name"] == codex_name
        assert codex_payload["transport"]["type"] == "streamable_http"
        assert codex_payload["transport"]["url"] == f"http://127.0.0.1:{http_port}/"
    finally:
        await terminate_process(relay)
        os.unlink(config_path)
