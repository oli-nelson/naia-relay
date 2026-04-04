from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from naia_relay.protocols.mcp.models import JsonRpcRequest
from naia_relay.registry import RegistryStore

ExecuteToolCallback = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
ReadResourceCallback = Callable[[str, dict[str, Any]], Awaitable[list[Any]]]
GetPromptCallback = Callable[[str, dict[str, Any]], Awaitable[list[Any]]]

SUPPORTED_PROTOCOL_VERSION = "2025-03-26"


@dataclass(slots=True)
class MCPHandler:
    registry: RegistryStore
    execute_tool: ExecuteToolCallback | None = None
    read_resource: ReadResourceCallback | None = None
    get_prompt: GetPromptCallback | None = None
    initialized: bool = False

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request = JsonRpcRequest.model_validate(message)

        match request.method:
            case "initialize":
                self.initialized = False
                return self._result(
                    request.id,
                    {
                        "protocolVersion": SUPPORTED_PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "resources": {"listChanged": True},
                            "prompts": {"listChanged": True},
                            "logging": {},
                        },
                        "serverInfo": {"name": "naia-relay", "version": "0.1.0"},
                    },
                )
            case "notifications/initialized":
                self.initialized = True
                return None
            case "tools/list":
                return self._result(
                    request.id,
                    {
                        "tools": [
                            {
                                "name": tool.name,
                                "title": tool.title,
                                "description": tool.description,
                                "inputSchema": tool.input_schema,
                                "outputSchema": tool.output_schema,
                            }
                            for tool in self.registry.snapshot()["tools"]
                        ]
                    },
                )
            case "tools/call":
                tool_name = request.params["name"]
                arguments = request.params.get("arguments", {})
                if self.execute_tool is None:
                    return self._error(request.id, -32601, "tools/call not available")
                result = await self.execute_tool(tool_name, arguments)
                return self._result(request.id, result)
            case "resources/list":
                return self._result(
                    request.id,
                    {
                        "resources": [
                            {
                                "uri": resource.uri,
                                "name": resource.name,
                                "description": resource.description,
                                "mimeType": resource.mime_type,
                            }
                            for resource in self.registry.snapshot()["resources"]
                        ]
                    },
                )
            case "resources/read":
                uri = request.params["uri"]
                arguments = request.params.get("arguments", {})
                if self.read_resource is None:
                    return self._error(request.id, -32601, "resources/read not available")
                contents = await self.read_resource(uri, arguments)
                return self._result(request.id, {"contents": contents})
            case "prompts/list":
                return self._result(
                    request.id,
                    {
                        "prompts": [
                            {
                                "name": prompt.name,
                                "description": prompt.description,
                                "arguments": prompt.arguments,
                            }
                            for prompt in self.registry.snapshot()["prompts"]
                        ]
                    },
                )
            case "prompts/get":
                name = request.params["name"]
                arguments = request.params.get("arguments", {})
                if self.get_prompt is None:
                    return self._error(request.id, -32601, "prompts/get not available")
                messages = await self.get_prompt(name, arguments)
                return self._result(request.id, {"messages": messages})
            case "sampling/createMessage" | "roots/list" | "completion/complete":
                return self._error(
                    request.id,
                    -32601,
                    f"{request.method} is unsupported in naia-relay v1",
                )
            case _:
                return self._error(request.id, -32601, f"Method not found: {request.method}")

    def _result(self, request_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(
        self,
        request_id: str | int | None,
        code: int,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message, "data": data or {}},
        }
