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
import signal
import textwrap
from typing import Any

from naia_relay.config import load_config
from naia_relay.runtime import HostRelayRuntime

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 61280
DEFAULT_TOOL_NAME = "test_tool"


def make_tep_message(message_type: str, payload: dict[str, Any], **extra: Any) -> dict[str, Any]:
    message = {
        "protocol": "tep",
        "version": "1.0",
        "message_type": message_type,
        "message_id": f"msg_{message_type}",
        "session_id": "sess_fake_executor",
        "payload": payload,
    }
    message.update(extra)
    return message



async def run_probe(host: str, port: int, tool_name: str, exit_after_setup: bool) -> int:
    config_text = textwrap.dedent(
        f"""\
        role: host
        executor:
          transport: stdio
        relay_link:
          transport: tcp
          bind_host: {host}
          bind_port: {port}
        """
    )
    config, _ = load_config(cli_config_yaml=config_text)
    runtime = HostRelayRuntime(config=config)
    await runtime.start()
    if not runtime.resolved_listeners:
        await runtime._start_rlp_listener(bind_port=port)

    try:
        register_executor_response = await runtime.handle_tep_message(
            make_tep_message(
                "register_executor",
                {"executor_id": "fake_nvim", "display_name": "Fake Neovim Executor"},
            )
        )
        register_tools_response = await runtime.handle_tep_message(
            make_tep_message(
                "register_tools",
                {
                    "tools": [
                        {
                            "name": tool_name,
                            "description": "Temporary test tool from fake executor",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"},
                                },
                            },
                        }
                    ]
                },
            )
        )

        summary = {
            "config": {
                "role": "host",
                "executor_transport": "stdio",
                "relay_link_transport": "tcp",
                "relay_link_host": host,
                "relay_link_port": port,
            },
            "register_executor_response": register_executor_response,
            "register_tools_response": register_tools_response,
            "tool_names": sorted(tool.name for tool in runtime.registry.snapshot()["tools"]),
            "listeners": runtime.resolved_listeners,
        }
        print(json.dumps(summary, indent=2), flush=True)

        if exit_after_setup:
            return 0

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signame in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signame, stop_event.set)
            except NotImplementedError:
                pass
        await stop_event.wait()
        return 0
    finally:
        await runtime.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start a fake stdio TEP executor against a host-mode naia-relay with TCP relay-link."
        )
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--tool-name",
        default=DEFAULT_TOOL_NAME,
        help=f"Tool name to register (default: {DEFAULT_TOOL_NAME})",
    )
    parser.add_argument(
        "--exit-after-setup",
        action="store_true",
        help="Register the fake executor and tool, print a summary, and exit immediately.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run_probe(args.host, args.port, args.tool_name, args.exit_after_setup))


if __name__ == "__main__":
    raise SystemExit(main())
