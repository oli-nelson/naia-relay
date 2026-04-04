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


def test_tep_handler_rejects_unsupported_version() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))
    message = make_message("register_executor", {"executor_id": "nvim", "display_name": "Neovim"})
    message["version"] = "2.0"

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
async def test_tep_handler_register_executor_and_terminal_messages() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))

    register_response = await handler.handle_message(
        make_message("register_executor", {"executor_id": "nvim", "display_name": "Neovim"})
    )
    progress_response = await handler.handle_message(
        make_message(
            "execution_progress",
            {"tool_name": "demo", "progress": {"message": "working", "percentage": 50}},
            execution_id="exec_1",
        )
    )
    result_response = await handler.handle_message(
        make_message(
            "execution_result",
            {"tool_name": "demo", "result": {"ok": True}},
            execution_id="exec_1",
        )
    )
    error_response = await handler.handle_message(
        make_message(
            "execution_error",
            {"tool_name": "demo", "code": "boom", "message": "failed"},
            execution_id="exec_1",
        )
    )

    assert register_response["payload"]["status"] == "ok"
    assert progress_response["payload"]["status"] == "ok"
    assert result_response["payload"]["status"] == "ok"
    assert error_response["payload"]["status"] == "ok"


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
async def test_tep_handler_records_resource_and_prompt_results_and_disconnects() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))
    resource_result = await handler.handle_message(
        make_message("resource_result", {"uri": "file:///demo", "contents": [{"text": "demo"}]})
    )
    prompt_result = await handler.handle_message(
        make_message("prompt_result", {"name": "prompt", "messages": [{"role": "user"}]})
    )
    disconnect = await handler.handle_message(
        make_message("disconnect_notice", {"reason": "bye"})
    )

    assert resource_result["payload"]["status"] == "ok"
    assert prompt_result["payload"]["status"] == "ok"
    assert disconnect["payload"]["status"] == "ok"
    assert handler.executor_available is False


@pytest.mark.asyncio
async def test_tep_handler_duplicate_registration_fails() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))
    await handler.handle_message(
        make_message(
            "register_tools",
            {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
        )
    )

    with pytest.raises(ValueError):
        await handler.handle_message(
            make_message(
                "register_tools",
                {"tools": [{"name": "demo", "description": "Demo", "input_schema": {}}]},
            )
        )


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
