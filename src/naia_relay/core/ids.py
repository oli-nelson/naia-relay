from __future__ import annotations

from uuid import uuid4


def new_message_id() -> str:
    return f"msg_{uuid4().hex}"


def new_request_id() -> str:
    return f"req_{uuid4().hex}"


def new_execution_id() -> str:
    return f"exec_{uuid4().hex}"


def new_session_id() -> str:
    return f"sess_{uuid4().hex}"


def new_relay_id() -> str:
    return f"relay_{uuid4().hex}"
