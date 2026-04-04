from __future__ import annotations

import asyncio
import json
import os
import pathlib
import tempfile
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYTHON = str(ROOT / ".venv/bin/python")


async def read_line_json(reader: asyncio.StreamReader) -> dict[str, object] | None:
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode())


async def write_line_json(writer: asyncio.StreamWriter, message: dict[str, object]) -> None:
    writer.write(json.dumps(message).encode() + b"\n")
    await writer.drain()


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


@pytest.mark.asyncio
async def test_host_mode_stdio_tep_loop_accepts_register_messages() -> None:
    host_cfg = textwrap.dedent(
        """\
        role: host
        executor:
          transport: stdio
        relay_link:
          transport: tcp
          host: 127.0.0.1
          port: 61280
        """
    )

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as host_file:
        host_file.write(host_cfg)
        host_path = host_file.name

    host = await asyncio.create_subprocess_exec(
        PYTHON,
        "-m",
        "naia_relay.cli",
        "--config-file",
        host_path,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        assert host.stdin is not None
        assert host.stdout is not None

        await write_line_json(
            host.stdin,
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_executor",
                "message_id": "msg_exec",
                "session_id": "sess_exec",
                "payload": {"executor_id": "fake_nvim", "display_name": "Fake Neovim"},
            },
        )
        exec_response = await asyncio.wait_for(read_line_json(host.stdout), timeout=3)
        assert exec_response is not None
        assert exec_response["payload"]["status"] == "ok"

        await write_line_json(
            host.stdin,
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_tools",
                "message_id": "msg_tools",
                "session_id": "sess_exec",
                "payload": {
                    "tools": [
                        {
                            "name": "test_tool",
                            "description": "TEP stdio registered tool",
                            "input_schema": {"type": "object", "properties": {}},
                        }
                    ]
                },
            },
        )
        tool_response = await asyncio.wait_for(read_line_json(host.stdout), timeout=3)
        assert tool_response is not None
        assert tool_response["payload"]["status"] == "ok"
    finally:
        await terminate_process(host)
        os.unlink(host_path)


@pytest.mark.asyncio
async def test_direct_mode_mcp_stdio_loop_accepts_initialize() -> None:
    cfg = textwrap.dedent(
        """\
        role: direct
        mcp:
          transport: stdio
        executor:
          transport: tcp
          port: 61280
        """
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as config_file:
        config_file.write(cfg)
        config_path = config_file.name

    proc = await asyncio.create_subprocess_exec(
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
        assert proc.stdin is not None
        assert proc.stdout is not None

        await write_line_json(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
            },
        )
        response = await asyncio.wait_for(read_line_json(proc.stdout), timeout=3)
        assert response is not None
        assert response["result"]["protocolVersion"] == "2025-06-18"
    finally:
        await terminate_process(proc)
        os.unlink(config_path)
