from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from naia_relay.core import new_message_id
from naia_relay.protocols.tep.models import (
    MESSAGE_PAYLOAD_MODELS,
    DeregisterPromptsPayload,
    DeregisterResourcesPayload,
    DeregisterToolsPayload,
    ExecuteToolPayload,
    GetPromptPayload,
    ReadResourcePayload,
    RegisterExecutorPayload,
    RegisterPromptsPayload,
    RegisterResourcesPayload,
    RegisterToolsPayload,
    StatusPayload,
)
from naia_relay.registry import PromptDefinition, RegistryStore, ResourceDefinition, ToolDefinition

ExecuteToolCallback = Callable[[ExecuteToolPayload], Awaitable[dict[str, Any]]]
ReadResourceCallback = Callable[[ReadResourcePayload], Awaitable[list[Any]]]
GetPromptCallback = Callable[[GetPromptPayload], Awaitable[list[Any]]]


class TEPEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    version: str
    message_type: str
    message_id: str
    session_id: str | None = None
    request_id: str | None = None
    execution_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class TEPHandler:
    registry: RegistryStore
    execute_tool: ExecuteToolCallback | None = None
    read_resource: ReadResourceCallback | None = None
    get_prompt: GetPromptCallback | None = None

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        envelope = self.validate_message(message)
        payload_model = MESSAGE_PAYLOAD_MODELS.get(envelope.message_type)
        if payload_model is None:
            return self._error_response(envelope, "unknown_message_type", envelope.message_type)
        payload = payload_model.model_validate(envelope.payload)

        match envelope.message_type:
            case "register_executor":
                assert isinstance(payload, RegisterExecutorPayload)
                return self._ok_response(envelope, {"executor_id": payload.executor_id})
            case "register_tools":
                assert isinstance(payload, RegisterToolsPayload)
                for tool in payload.tools:
                    self.registry.register_tool(
                        ToolDefinition(
                            name=tool.name,
                            title=tool.title,
                            description=tool.description,
                            input_schema=tool.input_schema,
                            output_schema=tool.output_schema,
                            metadata=tool.metadata,
                            owner_session_id=envelope.session_id,
                        )
                    )
                return self._ok_response(envelope)
            case "deregister_tools":
                assert isinstance(payload, DeregisterToolsPayload)
                for tool_name in payload.tool_names:
                    self.registry.deregister_tool(tool_name)
                return self._ok_response(envelope)
            case "register_resources":
                assert isinstance(payload, RegisterResourcesPayload)
                for resource in payload.resources:
                    self.registry.register_resource(
                        ResourceDefinition(
                            uri=resource.uri,
                            name=resource.name,
                            description=resource.description,
                            mime_type=resource.mime_type,
                            metadata=resource.metadata,
                            owner_session_id=envelope.session_id,
                        )
                    )
                return self._ok_response(envelope)
            case "deregister_resources":
                assert isinstance(payload, DeregisterResourcesPayload)
                for uri in payload.resource_uris:
                    self.registry.deregister_resource(uri)
                return self._ok_response(envelope)
            case "register_prompts":
                assert isinstance(payload, RegisterPromptsPayload)
                for prompt in payload.prompts:
                    self.registry.register_prompt(
                        PromptDefinition(
                            name=prompt.name,
                            description=prompt.description,
                            arguments=[item.model_dump() for item in prompt.arguments],
                            metadata=prompt.metadata,
                            owner_session_id=envelope.session_id,
                        )
                    )
                return self._ok_response(envelope)
            case "deregister_prompts":
                assert isinstance(payload, DeregisterPromptsPayload)
                for prompt_name in payload.prompt_names:
                    self.registry.deregister_prompt(prompt_name)
                return self._ok_response(envelope)
            case "execute_tool":
                assert isinstance(payload, ExecuteToolPayload)
                if self.execute_tool is None:
                    return self._error_response(
                        envelope, "unimplemented", "execute_tool callback missing"
                    )
                result = await self.execute_tool(payload)
                return self._ok_response(envelope, result)
            case "read_resource":
                assert isinstance(payload, ReadResourcePayload)
                if self.read_resource is None:
                    return self._error_response(
                        envelope, "unimplemented", "read_resource callback missing"
                    )
                contents = await self.read_resource(payload)
                return self._ok_response(envelope, {"uri": payload.uri, "contents": contents})
            case "get_prompt":
                assert isinstance(payload, GetPromptPayload)
                if self.get_prompt is None:
                    return self._error_response(
                        envelope, "unimplemented", "get_prompt callback missing"
                    )
                messages = await self.get_prompt(payload)
                return self._ok_response(envelope, {"name": payload.name, "messages": messages})
            case "heartbeat" | "shutdown" | "disconnect_notice":
                return self._ok_response(envelope)
            case _:
                return self._error_response(envelope, "unsupported", envelope.message_type)

    def validate_message(self, message: dict[str, Any]) -> TEPEnvelope:
        envelope = TEPEnvelope.model_validate(message)
        if envelope.protocol != "tep":
            raise ValueError("TEP messages must have protocol='tep'")
        if envelope.version != "1.0":
            raise ValueError(f"Unsupported TEP version: {envelope.version}")
        if envelope.message_type in {
            "execute_tool",
            "execution_progress",
            "execution_result",
            "execution_error",
        } and envelope.execution_id is None:
            raise ValueError(f"{envelope.message_type} requires execution_id")
        return envelope

    def _ok_response(
        self, envelope: TEPEnvelope, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = StatusPayload(status="ok", details=details or {}).model_dump()
        return {
            "protocol": "tep",
            "version": "1.0",
            "message_type": f"{envelope.message_type}_response",
            "message_id": new_message_id(),
            "session_id": envelope.session_id,
            "request_id": envelope.request_id or envelope.message_id,
            "execution_id": envelope.execution_id,
            "payload": payload,
        }

    def _error_response(self, envelope: TEPEnvelope, code: str, message: str) -> dict[str, Any]:
        payload = StatusPayload(status="error", code=code, message=message).model_dump()
        return {
            "protocol": "tep",
            "version": "1.0",
            "message_type": f"{envelope.message_type}_response",
            "message_id": new_message_id(),
            "session_id": envelope.session_id,
            "request_id": envelope.request_id or envelope.message_id,
            "execution_id": envelope.execution_id,
            "payload": payload,
        }
