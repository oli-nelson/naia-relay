#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

VENV_PYTHON = PROJECT_ROOT / ".venv/bin/python"
if sys.executable != str(VENV_PYTHON):
    try:
        import importlib.util

        available = importlib.util.find_spec("yaml") is not None
    except Exception:
        available = False
    if not available:
        if VENV_PYTHON.exists():
            import os

            os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

import argparse
import asyncio
import json
import os
import tempfile
import textwrap
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 61280
DEFAULT_PROTOCOL_VERSION = "2025-06-18"


async def read_mcp_message(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


async def write_mcp_message(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    writer.write(json.dumps(message).encode("utf-8") + b"\n")
    await writer.drain()


async def run_probe(
    host: str,
    port: int,
    python_executable: str,
    project_root: Path,
) -> dict[str, Any]:
    config_text = textwrap.dedent(
        f"""\
        role: client
        mcp:
          transport: stdio
        relay_link:
          transport: tcp
          host: {host}
          port: {port}
        """
    )

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        handle.write(config_text)
        config_path = handle.name

    process = await asyncio.create_subprocess_exec(
        python_executable,
        "-m",
        "naia_relay.cli",
        "--config-file",
        config_path,
        cwd=str(project_root),
        env={**os.environ, "PYTHONPATH": str(project_root / "src")},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    result: dict[str, Any] = {
        "config": {
            "role": "client",
            "mcp_transport": "stdio",
            "relay_link_transport": "tcp",
            "relay_link_host": host,
            "relay_link_port": port,
        },
        "initialize_response": None,
        "tools_list_response": None,
        "tool_names": None,
    }

    try:
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None

        await write_mcp_message(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "naia-relay-probe", "version": "1.0"},
                },
            },
        )
        result["initialize_response"] = await asyncio.wait_for(
            read_mcp_message(process.stdout), timeout=2
        )

        await write_mcp_message(
            process.stdin,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        await write_mcp_message(
            process.stdin,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        result["tools_list_response"] = await asyncio.wait_for(
            read_mcp_message(process.stdout), timeout=2
        )
        tools = result["tools_list_response"] or {}
        result["tool_names"] = [
            tool.get("name") for tool in tools.get("result", {}).get("tools", [])
        ]
    except Exception as exc:  # pragma: no cover - debugging helper
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except Exception:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except Exception:
                pass
        stderr = b""
        if process.stderr is not None:
            stderr = await process.stderr.read()
        result["stderr"] = stderr.decode("utf-8", errors="replace")
        os.unlink(config_path)

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Temporary probe for naia-relay client mode over MCP stdio to a TCP host relay."
        )
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"TCP host to probe (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port to probe (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--python",
        default=str(PROJECT_ROOT / ".venv/bin/python"),
        help="Python executable to use for launching naia-relay",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = PROJECT_ROOT
    result = asyncio.run(run_probe(args.host, args.port, args.python, project_root))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
