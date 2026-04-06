from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from naia_relay.protocols.mcp.models import JsonRpcRequest
from naia_relay.registry import RegistryStore

ExecuteToolCallback = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
ReadResourceCallback = Callable[[str, dict[str, Any]], Awaitable[list[Any]]]
GetPromptCallback = Callable[[str, dict[str, Any]], Awaitable[list[Any]]]

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


@dataclass(slots=True)
class MCPHandler:
    registry: RegistryStore
    execute_tool: ExecuteToolCallback | None = None
    read_resource: ReadResourceCallback | None = None
    get_prompt: GetPromptCallback | None = None
    initialized: bool = False
    log_level: str = "info"

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request = JsonRpcRequest.model_validate(message)

        match request.method:
            case "initialize":
                self.initialized = False
                return self._result(
                    request.id,
                    {
                        "protocolVersion": self._negotiate_protocol_version(request.params),
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
                            self._serialize_tool(tool)
                            for tool in self.registry.snapshot()["tools"]
                        ]
                    },
                )
            case "tools/call":
                tool_name = request.params["name"]
                arguments = request.params.get("arguments", {})
                if self.execute_tool is None:
                    return self._error(request.id, -32601, "tools/call not available")
                try:
                    result = await self.execute_tool(tool_name, arguments)
                except Exception as exc:
                    return self._error(
                        request.id,
                        -32000,
                        f"tools/call failed for {tool_name}",
                        {"exception_type": type(exc).__name__, "detail": str(exc)},
                    )
                return self._result(request.id, result)
            case "resources/list":
                return self._result(
                    request.id,
                    {
                        "resources": [
                            self._serialize_resource(resource)
                            for resource in self.registry.snapshot()["resources"]
                        ]
                    },
                )
            case "resources/read":
                uri = request.params["uri"]
                arguments = request.params.get("arguments", {})
                if self.read_resource is None:
                    return self._error(request.id, -32601, "resources/read not available")
                try:
                    contents = await self.read_resource(uri, arguments)
                except Exception as exc:
                    return self._error(
                        request.id,
                        -32000,
                        f"resources/read failed for {uri}",
                        {"exception_type": type(exc).__name__, "detail": str(exc)},
                    )
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
                try:
                    messages = await self.get_prompt(name, arguments)
                except Exception as exc:
                    return self._error(
                        request.id,
                        -32000,
                        f"prompts/get failed for {name}",
                        {"exception_type": type(exc).__name__, "detail": str(exc)},
                    )
                return self._result(request.id, {"messages": messages})
            case "logging/setLevel":
                level = request.params.get("level", "info")
                self.log_level = str(level)
                return self._result(request.id, {})
            case "sampling/createMessage" | "roots/list" | "completion/complete":
                return self._error(
                    request.id,
                    -32601,
                    f"{request.method} is unsupported in naia-relay v1",
                )
            case _:
                return self._error(request.id, -32601, f"Method not found: {request.method}")


    def _negotiate_protocol_version(self, params: dict[str, Any]) -> str:
        requested = params.get("protocolVersion")
        if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
            return requested
        return DEFAULT_PROTOCOL_VERSION

    def make_log_notification(
        self, level: str, message: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"level": level, "data": data or {"message": message}},
        }

    def _serialize_tool(self, tool: Any) -> dict[str, Any]:
        payload = {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }
        if tool.title is not None:
            payload["title"] = tool.title
        if tool.output_schema is not None:
            payload["outputSchema"] = tool.output_schema
        return payload

    def _serialize_resource(self, resource: Any) -> dict[str, Any]:
        payload = {
            "uri": resource.uri,
            "name": resource.name,
        }
        if resource.description is not None:
            payload["description"] = resource.description
        if resource.mime_type is not None:
            payload["mimeType"] = resource.mime_type
        return payload

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
