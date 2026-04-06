#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import uuid

SESSION_ID = "sess_python_tcp_executor"


def new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"


def send(sock: socket.socket, message: dict) -> None:
    sock.sendall((json.dumps(message) + "\n").encode("utf-8"))


def read_message(fileobj) -> dict | None:
    line = fileobj.readline()
    if not line:
        return None
    return json.loads(line)


def status_response(
    message: dict,
    *,
    status: str = "ok",
    details: dict | None = None,
    code: str | None = None,
    text: str | None = None,
) -> dict:
    return {
        "protocol": "tep",
        "version": "1.0",
        "message_type": f"{message['message_type']}_response",
        "message_id": new_message_id(),
        "session_id": message.get("session_id", SESSION_ID),
        "request_id": message.get("request_id") or message.get("message_id"),
        "execution_id": message.get("execution_id"),
        "payload": {
            "status": status,
            "code": code,
            "message": text,
            "details": details or {},
        },
    }


def execution_result(message: dict, result: dict) -> dict:
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
            "result": result,
            "is_error": False,
            "metadata": {},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port)) as sock:
        fileobj = sock.makefile("r", encoding="utf-8")

        send(
            sock,
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_executor",
                "message_id": new_message_id(),
                "session_id": SESSION_ID,
                "payload": {
                    "executor_id": "python-tcp-example",
                    "display_name": "Python tcp example",
                    "capabilities": {"tools": True, "resources": False, "prompts": False},
                    "metadata": {},
                },
            },
        )
        if read_message(fileobj) is None:
            return 1

        send(
            sock,
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "register_tools",
                "message_id": new_message_id(),
                "session_id": SESSION_ID,
                "payload": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echoes the input message",
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
        if read_message(fileobj) is None:
            return 1

        while True:
            message = read_message(fileobj)
            if message is None:
                return 0

            message_type = message.get("message_type")

            if message_type == "execute_tool":
                arguments = message.get("payload", {}).get("arguments", {})
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"python tcp executor received: {arguments.get('message', '')}",
                        }
                    ],
                    "isError": False,
                }
                send(sock, execution_result(message, result))
                continue

            if message_type in {"heartbeat", "shutdown", "disconnect_notice"}:
                send(sock, status_response(message))
                if message_type == "shutdown":
                    return 0
                continue

            send(
                sock,
                status_response(
                    message,
                    status="error",
                    code="unsupported",
                    text=f"unsupported message type: {message_type}",
                ),
            )


if __name__ == "__main__":
    raise SystemExit(main())
