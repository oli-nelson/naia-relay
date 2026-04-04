from __future__ import annotations

import pytest

from naia_relay.protocols.mcp import DEFAULT_PROTOCOL_VERSION, MCPHandler
from naia_relay.registry import PromptDefinition, RegistryStore, ResourceDefinition, ToolDefinition


def build_registry() -> RegistryStore:
    registry = RegistryStore(mode="authoritative")
    registry.register_tool(ToolDefinition(name="demo", description="Demo", input_schema={}))
    registry.register_resource(ResourceDefinition(uri="file:///demo", name="demo"))
    registry.register_prompt(PromptDefinition(name="prompt", description="Prompt"))
    return registry


@pytest.mark.asyncio
async def test_mcp_initialize_and_initialized() -> None:
    handler = MCPHandler(registry=build_registry())

    response = await handler.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": DEFAULT_PROTOCOL_VERSION, "capabilities": {}},
        }
    )
    assert response["result"]["protocolVersion"] == DEFAULT_PROTOCOL_VERSION

    notification = await handler.handle_message(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    )
    assert notification is None
    assert handler.initialized is True


@pytest.mark.asyncio
async def test_mcp_lists_tools_resources_and_prompts() -> None:
    handler = MCPHandler(registry=build_registry())

    tools = await handler.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    resources = await handler.handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "resources/list"}
    )
    prompts = await handler.handle_message({"jsonrpc": "2.0", "id": 3, "method": "prompts/list"})

    assert tools["result"]["tools"][0]["name"] == "demo"
    assert resources["result"]["resources"][0]["uri"] == "file:///demo"
    assert prompts["result"]["prompts"][0]["name"] == "prompt"


@pytest.mark.asyncio
async def test_mcp_calls_tool_reads_resource_and_gets_prompt() -> None:
    async def execute_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        return {"content": [{"type": "text", "text": f"{name}:{arguments.get('x', 0)}"}]}

    async def read_resource(uri: str, arguments: dict[str, object]) -> list[dict[str, object]]:
        return [{"uri": uri, "text": "demo"}]

    async def get_prompt(name: str, arguments: dict[str, object]) -> list[dict[str, object]]:
        return [{"role": "user", "content": name}]

    handler = MCPHandler(
        registry=build_registry(),
        execute_tool=execute_tool,
        read_resource=read_resource,
        get_prompt=get_prompt,
    )

    tool = await handler.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"x": 1}},
        }
    )
    resource = await handler.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/read",
            "params": {"uri": "file:///demo"},
        }
    )
    prompt = await handler.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "prompts/get",
            "params": {"name": "prompt"},
        }
    )

    assert tool["result"]["content"][0]["text"] == "demo:1"
    assert resource["result"]["contents"][0]["uri"] == "file:///demo"
    assert prompt["result"]["messages"][0]["content"] == "prompt"


@pytest.mark.asyncio
async def test_mcp_unsupported_features_fail_explicitly() -> None:
    handler = MCPHandler(registry=build_registry())

    sampling = await handler.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "sampling/createMessage"}
    )
    roots = await handler.handle_message({"jsonrpc": "2.0", "id": 2, "method": "roots/list"})
    completions = await handler.handle_message(
        {"jsonrpc": "2.0", "id": 3, "method": "completion/complete"}
    )

    assert sampling["error"]["code"] == -32601
    assert roots["error"]["code"] == -32601
    assert completions["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_mcp_logging_set_level_and_notification_helper() -> None:
    handler = MCPHandler(registry=build_registry())

    response = await handler.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "logging/setLevel", "params": {"level": "debug"}}
    )
    notification = handler.make_log_notification("debug", "hello", {"message": "hello"})

    assert response["result"] == {}
    assert handler.log_level == "debug"
    assert notification["method"] == "notifications/message"


@pytest.mark.asyncio
async def test_mcp_error_mapping_preserves_structured_details() -> None:
    async def execute_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("boom")

    handler = MCPHandler(registry=build_registry(), execute_tool=execute_tool)

    response = await handler.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {}},
        }
    )

    assert response["error"]["code"] == -32000
    assert response["error"]["data"]["exception_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_mcp_discovery_reflects_registry_changes() -> None:
    registry = build_registry()
    handler = MCPHandler(registry=registry)

    registry.register_tool(ToolDefinition(name="demo2", description="Demo 2", input_schema={}))
    registry.register_resource(ResourceDefinition(uri="file:///demo2", name="demo2"))
    registry.register_prompt(PromptDefinition(name="prompt2", description="Prompt 2"))

    tools = await handler.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    resources = await handler.handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "resources/list"}
    )
    prompts = await handler.handle_message({"jsonrpc": "2.0", "id": 3, "method": "prompts/list"})

    assert {item["name"] for item in tools["result"]["tools"]} == {"demo", "demo2"}
    assert {item["uri"] for item in resources["result"]["resources"]} == {
        "file:///demo",
        "file:///demo2",
    }
    assert {item["name"] for item in prompts["result"]["prompts"]} == {"prompt", "prompt2"}
