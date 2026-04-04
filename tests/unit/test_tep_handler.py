from __future__ import annotations

import pytest

from naia_relay.protocols.tep import TEPHandler
from naia_relay.registry import RegistryStore


def make_message(
    message_type: str, payload: dict[str, object], **extra: object
) -> dict[str, object]:
    message = {
        "protocol": "tep",
        "version": "1.0",
        "message_type": message_type,
        "message_id": "msg_1",
        "session_id": "sess_1",
        "payload": payload,
    }
    message.update(extra)
    return message


def test_tep_handler_validates_envelope() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))
    envelope = handler.validate_message(
        make_message("register_executor", {"executor_id": "nvim", "display_name": "Neovim"})
    )

    assert envelope.protocol == "tep"


def test_tep_handler_rejects_wrong_protocol() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))
    message = make_message("register_executor", {"executor_id": "nvim", "display_name": "Neovim"})
    message["protocol"] = "bad"

    with pytest.raises(ValueError):
        handler.validate_message(message)


@pytest.mark.asyncio
async def test_tep_handler_registers_tool_resource_and_prompt() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))

    await handler.handle_message(
        make_message(
            "register_tools",
            {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
        )
    )
    await handler.handle_message(
        make_message(
            "register_resources",
            {"resources": [{"uri": "file:///demo", "name": "demo"}]},
        )
    )
    await handler.handle_message(
        make_message(
            "register_prompts",
            {"prompts": [{"name": "prompt", "description": "Prompt"}]},
        )
    )

    assert handler.registry.get_tool("demo") is not None
    assert handler.registry.get_resource("file:///demo") is not None
    assert handler.registry.get_prompt("prompt") is not None


@pytest.mark.asyncio
async def test_tep_handler_executes_callbacks() -> None:
    async def execute_tool(payload):
        return {"tool_name": payload.tool_name, "result": {"ok": True}}

    async def read_resource(payload):
        return [{"text": f"read:{payload.uri}"}]

    async def get_prompt(payload):
        return [{"role": "user", "content": payload.name}]

    handler = TEPHandler(
        registry=RegistryStore(mode="authoritative"),
        execute_tool=execute_tool,
        read_resource=read_resource,
        get_prompt=get_prompt,
    )

    execute_response = await handler.handle_message(
        make_message(
            "execute_tool",
            {"tool_name": "demo", "arguments": {}},
            execution_id="exec_1",
        )
    )
    resource_response = await handler.handle_message(
        make_message("read_resource", {"uri": "file:///demo"})
    )
    prompt_response = await handler.handle_message(
        make_message("get_prompt", {"name": "prompt"})
    )

    assert execute_response["payload"]["status"] == "ok"
    assert resource_response["payload"]["status"] == "ok"
    assert prompt_response["payload"]["status"] == "ok"


@pytest.mark.asyncio
async def test_tep_handler_reports_missing_callbacks_as_errors() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))

    response = await handler.handle_message(
        make_message(
            "execute_tool",
            {"tool_name": "demo", "arguments": {}},
            execution_id="exec_1",
        )
    )

    assert response["payload"]["status"] == "error"
    assert response["payload"]["code"] == "unimplemented"
