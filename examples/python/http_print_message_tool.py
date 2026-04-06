#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path

FIXED_PORT = 8181
SESSION_ID = "sess_http_print_message_tool"


def new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"


def send(writer, message: dict) -> None:
    writer.write(json.dumps(message) + "\n")
    writer.flush()


def read_message(reader) -> dict | None:
    line = reader.readline()
    if not line:
        return None
    return json.loads(line)


def register_executor(stdout) -> None:
    send(
        stdout,
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_executor",
            "message_id": new_message_id(),
            "session_id": SESSION_ID,
            "payload": {
                "executor_id": "python-http-print-message",
                "display_name": "Python HTTP print message example",
                "capabilities": {"tools": True, "resources": False, "prompts": False},
                "metadata": {},
            },
        },
    )


def register_tools(stdout) -> None:
    send(
        stdout,
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": new_message_id(),
            "session_id": SESSION_ID,
            "payload": {
                "tools": [
                    {
                        "name": "print_message",
                        "description": "Print a message in the local process and return it.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                            },
                            "required": ["message"],
                        },
                        "metadata": {},
                    }
                ]
            },
        },
    )


def execution_result(message: dict, text: str) -> dict:
    return {
        "protocol": "tep",
        "version": "1.0",
        "message_type": "execution_result",
        "message_id": new_message_id(),
        "session_id": message.get("session_id", SESSION_ID),
        "request_id": message.get("request_id") or message.get("message_id"),
        "execution_id": message["execution_id"],
        "payload": {
            "tool_name": message["payload"]["tool_name"],
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            },
            "is_error": False,
            "metadata": {},
        },
    }


def run() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    preferred_python = repo_root / ".venv" / "bin" / "python"
    relay_python = str(preferred_python) if preferred_python.exists() else sys.executable
    config_yaml = textwrap.dedent(
        f"""\
        role: direct
        mcp:
          transport: http
          host: 127.0.0.1
          port: {FIXED_PORT}
        executor:
          transport: stdio
        """
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as config_file:
        config_file.write(config_yaml)
        config_path = Path(config_file.name)

    relay = subprocess.Popen(
        [relay_python, "-m", "naia_relay.cli", "--config-file", str(config_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
    )

    def cleanup(*_: object) -> None:
        if relay.poll() is None:
            relay.terminate()
            try:
                relay.wait(timeout=2)
            except subprocess.TimeoutExpired:
                relay.kill()
        config_path.unlink(missing_ok=True)
        raise SystemExit(0)

    def close_relay() -> None:
        if relay.poll() is None:
            relay.terminate()
            try:
                relay.wait(timeout=2)
            except subprocess.TimeoutExpired:
                relay.kill()
        config_path.unlink(missing_ok=True)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        assert relay.stdin is not None
        assert relay.stdout is not None

        register_executor(relay.stdin)
        if read_message(relay.stdout) is None:
            return 1

        register_tools(relay.stdin)
        if read_message(relay.stdout) is None:
            return 1

        print(f"HTTP MCP server listening on http://127.0.0.1:{FIXED_PORT}/mcp", flush=True)
        print("Registered tool: print_message", flush=True)

        while True:
            message = read_message(relay.stdout)
            if message is None:
                return 0

            if message.get("message_type") == "execute_tool":
                arguments = message.get("payload", {}).get("arguments", {})
                text = str(arguments.get("message", ""))
                print(f"print_message tool invoked with: {text}", flush=True)
                send(
                    relay.stdin,
                    execution_result(
                        message,
                        f"print_message tool printed: {text}",
                    ),
                )
    finally:
        close_relay()


if __name__ == "__main__":
    raise SystemExit(run())
