from __future__ import annotations

import pytest

from naia_relay.protocols.rlp import RLPHandler
from naia_relay.registry import PromptDefinition, RegistryStore, ResourceDefinition, ToolDefinition


def make_message(
    message_type: str, payload: dict[str, object], **extra: object
) -> dict[str, object]:
    message = {
        "protocol": "rlp",
        "version": "1.0",
        "message_type": message_type,
        "message_id": "msg_1",
        "relay_session_id": "relay_session_1",
        "source_relay_id": "client_1",
        "payload": payload,
    }
    message.update(extra)
    return message


def build_handler() -> RLPHandler:
    registry = RegistryStore(mode="authoritative")
    registry.register_tool(ToolDefinition(name="demo", description="Demo", input_schema={}))
    registry.register_resource(ResourceDefinition(uri="file:///demo", name="demo"))
    registry.register_prompt(PromptDefinition(name="prompt", description="Prompt"))
    return RLPHandler(
        registry=registry,
        host_relay_id="host_1",
        relay_session_id="relay_session_1",
        session_token="secret",
    )


def test_rlp_handler_rejects_wrong_protocol() -> None:
    handler = build_handler()
    message = make_message("hello", {"relay_id": "client_1", "role": "client"})
    message["protocol"] = "bad"

    with pytest.raises(ValueError):
        handler.validate_message(message)


def test_rlp_handler_rejects_unsupported_version() -> None:
    handler = build_handler()
    message = make_message("hello", {"relay_id": "client_1", "role": "client"})
    message["version"] = "2.0"

    with pytest.raises(ValueError):
        handler.validate_message(message)


@pytest.mark.asyncio
async def test_rlp_bind_session_returns_snapshot_details() -> None:
    handler = build_handler()
    response = await handler.handle_message(
        make_message(
            "bind_session",
            {
                "relay_session_id": "relay_session_1",
                "session_token": "secret",
                "client_instance_id": "client_1",
            },
        )
    )

    assert response["payload"]["status"] == "ok"
    assert response["payload"]["details"]["registry_revision"] == handler.registry.revision
    assert handler.bound_client_count() == 1


@pytest.mark.asyncio
async def test_rlp_hello_handshake_succeeds() -> None:
    handler = build_handler()
    response = await handler.handle_message(
        make_message("hello", {"relay_id": "client_1", "role": "client"})
    )

    assert response["payload"]["status"] == "ok"
    assert response["payload"]["details"]["host_relay_id"] == "host_1"


@pytest.mark.asyncio
async def test_rlp_bind_session_rejects_unknown_session() -> None:
    handler = build_handler()
    response = await handler.handle_message(
        make_message(
            "bind_session",
            {
                "relay_session_id": "wrong",
                "session_token": "secret",
                "client_instance_id": "client_1",
            },
        )
    )

    assert response["payload"]["status"] == "error"
    assert response["payload"]["code"] == "unknown_session"


@pytest.mark.asyncio
async def test_rlp_bind_session_rejects_bad_token() -> None:
    handler = build_handler()
    response = await handler.handle_message(
        make_message(
            "bind_session",
            {
                "relay_session_id": "relay_session_1",
                "session_token": "wrong",
                "client_instance_id": "client_1",
            },
        )
    )

    assert response["payload"]["status"] == "error"
    assert response["payload"]["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_rlp_snapshot_replaces_mirrored_state() -> None:
    handler = RLPHandler(
        registry=RegistryStore(mode="mirrored"),
        host_relay_id="host_1",
        relay_session_id="relay_session_1",
    )

    response = await handler.handle_message(
        make_message(
            "tool_snapshot",
            {
                "registry_revision": 3,
                "tools": [{"name": "demo", "description": "Demo", "input_schema": {}}],
                "resources": [{"uri": "file:///demo", "name": "demo"}],
                "prompts": [{"name": "prompt", "description": "Prompt"}],
            },
        )
    )

    assert response["payload"]["status"] == "ok"
    assert handler.registry.revision == 3
    assert handler.registry.get_tool("demo") is not None
    assert handler.registry.get_resource("file:///demo") is not None
    assert handler.registry.get_prompt("prompt") is not None


@pytest.mark.asyncio
async def test_rlp_incremental_updates_apply_and_revision_gap_marks_stale() -> None:
    handler = RLPHandler(
        registry=RegistryStore(mode="mirrored"),
        host_relay_id="host_1",
        relay_session_id="relay_session_1",
    )
    await handler.handle_message(
        make_message(
            "tool_snapshot",
            {
                "registry_revision": 1,
                "tools": [{"name": "demo", "description": "Demo", "input_schema": {}}],
                "resources": [],
                "prompts": [],
            },
        )
    )

    added = await handler.handle_message(
        make_message(
            "tool_added",
            {
                "registry_revision": 2,
                "tool": {"name": "demo2", "description": "Demo 2", "input_schema": {}},
            },
        )
    )
    assert added["payload"]["status"] == "ok"
    assert handler.registry.get_tool("demo2") is not None

    added = await handler.handle_message(
        make_message(
            "resource_added",
            {"registry_revision": 3, "resource": {"uri": "file:///demo", "name": "demo"}},
        )
    )
    assert added["payload"]["status"] == "ok"
    assert handler.registry.get_resource("file:///demo") is not None

    added = await handler.handle_message(
        make_message(
            "prompt_added",
            {"registry_revision": 4, "prompt": {"name": "prompt", "description": "Prompt"}},
        )
    )
    assert added["payload"]["status"] == "ok"
    assert handler.registry.get_prompt("prompt") is not None

    gap = await handler.handle_message(
        make_message(
            "prompt_added",
            {"registry_revision": 6, "prompt": {"name": "prompt2", "description": "Prompt 2"}},
        )
    )
    assert gap["payload"]["status"] == "error"
    assert handler.registry.stale is True


@pytest.mark.asyncio
async def test_rlp_executes_callbacks() -> None:
    async def execute_tool(payload):
        return {"tool_name": payload.tool_name, "result": {"ok": True}}

    async def read_resource(payload):
        return [{"text": payload.uri}]

    async def get_prompt(payload):
        return [{"role": "user", "content": payload.name}]

    handler = RLPHandler(
        registry=RegistryStore(mode="authoritative"),
        host_relay_id="host_1",
        relay_session_id="relay_session_1",
        execute_tool=execute_tool,
        read_resource=read_resource,
        get_prompt=get_prompt,
    )

    execute_response = await handler.handle_message(
        make_message(
            "execute_tool",
            {"tool_name": "demo"},
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
async def test_rlp_terminal_messages_are_recorded() -> None:
    handler = build_handler()
    progress = await handler.handle_message(
        make_message(
            "execution_progress",
            {"tool_name": "demo", "progress": {"message": "working", "percentage": 25}},
            execution_id="exec_1",
        )
    )
    result = await handler.handle_message(
        make_message(
            "execution_result",
            {"tool_name": "demo", "result": {"ok": True}},
            execution_id="exec_1",
        )
    )
    error = await handler.handle_message(
        make_message(
            "execution_error",
            {"tool_name": "demo", "code": "boom", "message": "failed"},
            execution_id="exec_1",
        )
    )
    resource = await handler.handle_message(
        make_message("resource_result", {"uri": "file:///demo", "contents": [{"text": "demo"}]})
    )
    prompt = await handler.handle_message(
        make_message("prompt_result", {"name": "prompt", "messages": [{"role": "user"}]})
    )

    assert progress["payload"]["status"] == "ok"
    assert result["payload"]["status"] == "ok"
    assert error["payload"]["status"] == "ok"
    assert resource["payload"]["status"] == "ok"
    assert prompt["payload"]["status"] == "ok"


@pytest.mark.asyncio
async def test_rlp_reconnect_snapshot_clears_stale_state() -> None:
    handler = RLPHandler(
        registry=RegistryStore(mode="mirrored"),
        host_relay_id="host_1",
        relay_session_id="relay_session_1",
    )
    handler.registry.mark_stale()
    response = await handler.handle_message(
        make_message(
            "tool_snapshot",
            {
                "registry_revision": 5,
                "tools": [{"name": "demo", "description": "Demo", "input_schema": {}}],
                "resources": [],
                "prompts": [],
            },
        )
    )

    assert response["payload"]["status"] == "ok"
    assert handler.registry.stale is False
