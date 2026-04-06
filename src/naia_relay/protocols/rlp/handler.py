from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from naia_relay.core import new_message_id
from naia_relay.protocols.rlp.models import (
    MESSAGE_PAYLOAD_MODELS,
    BindSessionPayload,
    ExecuteToolPayload,
    ExecutionErrorPayload,
    ExecutionProgressPayload,
    ExecutionResultPayload,
    GetPromptPayload,
    HelloPayload,
    PromptMutationPayload,
    PromptRemovedPayload,
    PromptResultPayload,
    ReadResourcePayload,
    ResourceMutationPayload,
    ResourceRemovedPayload,
    ResourceResultPayload,
    SnapshotPayload,
    StatusPayload,
    ToolMutationPayload,
    ToolRemovedPayload,
)
from naia_relay.registry import PromptDefinition, RegistryStore, ResourceDefinition, ToolDefinition

ExecuteToolCallback = Callable[[ExecuteToolPayload], Awaitable[dict[str, Any]]]
ReadResourceCallback = Callable[[ReadResourcePayload], Awaitable[list[Any]]]
GetPromptCallback = Callable[[GetPromptPayload], Awaitable[list[Any]]]


class RLPEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    version: str
    message_type: str
    message_id: str
    relay_session_id: str | None = None
    source_relay_id: str | None = None
    target_relay_id: str | None = None
    request_id: str | None = None
    execution_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class RLPHandler:
    registry: RegistryStore
    host_relay_id: str
    relay_session_id: str
    session_token: str | None = None
    execute_tool: ExecuteToolCallback | None = None
    read_resource: ReadResourceCallback | None = None
    get_prompt: GetPromptCallback | None = None
    _bound_clients: set[str] = None  # type: ignore[assignment]
    last_progress: dict[str, Any] | None = None
    last_execution_result: dict[str, Any] | None = None
    last_execution_error: dict[str, Any] | None = None
    last_resource_result: dict[str, Any] | None = None
    last_prompt_result: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self._bound_clients is None:
            self._bound_clients = set()

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        envelope = self.validate_message(message)
        payload_model = MESSAGE_PAYLOAD_MODELS.get(envelope.message_type)
        if payload_model is None:
            return self._error_response(envelope, "unknown_message_type", envelope.message_type)
        payload = payload_model.model_validate(envelope.payload)

        match envelope.message_type:
            case "hello" | "handshake":
                assert isinstance(payload, HelloPayload)
                return self._ok_response(envelope, {"host_relay_id": self.host_relay_id})
            case "bind_session":
                assert isinstance(payload, BindSessionPayload)
                if payload.relay_session_id != self.relay_session_id:
                    return self._error_response(
                        envelope, "unknown_session", payload.relay_session_id
                    )
                if self.session_token is not None and payload.session_token != self.session_token:
                    return self._error_response(
                        envelope, "invalid_token", "Invalid session token."
                    )
                self._bound_clients.add(payload.client_instance_id)
                return self._ok_response(envelope, self._build_snapshot_details())
            case "tool_snapshot" | "resource_snapshot" | "prompt_snapshot":
                assert isinstance(payload, SnapshotPayload)
                self._replace_registry_from_snapshot(payload)
                return self._ok_response(envelope)
            case "tool_added" | "tool_updated":
                assert isinstance(payload, ToolMutationPayload)
                gap = self._validate_incremental_revision(payload.registry_revision)
                if gap is not None:
                    return gap
                self._upsert_tool(payload)
                return self._ok_response(envelope)
            case "tool_removed":
                assert isinstance(payload, ToolRemovedPayload)
                gap = self._validate_incremental_revision(payload.registry_revision)
                if gap is not None:
                    return gap
                self.registry.deregister_tool(payload.tool_name)
                return self._ok_response(envelope)
            case "resource_added" | "resource_updated":
                assert isinstance(payload, ResourceMutationPayload)
                gap = self._validate_incremental_revision(payload.registry_revision)
                if gap is not None:
                    return gap
                self._upsert_resource(payload)
                return self._ok_response(envelope)
            case "resource_removed":
                assert isinstance(payload, ResourceRemovedPayload)
                gap = self._validate_incremental_revision(payload.registry_revision)
                if gap is not None:
                    return gap
                self.registry.deregister_resource(payload.uri)
                return self._ok_response(envelope)
            case "prompt_added" | "prompt_updated":
                assert isinstance(payload, PromptMutationPayload)
                gap = self._validate_incremental_revision(payload.registry_revision)
                if gap is not None:
                    return gap
                self._upsert_prompt(payload)
                return self._ok_response(envelope)
            case "prompt_removed":
                assert isinstance(payload, PromptRemovedPayload)
                gap = self._validate_incremental_revision(payload.registry_revision)
                if gap is not None:
                    return gap
                self.registry.deregister_prompt(payload.name)
                return self._ok_response(envelope)
            case "execute_tool":
                assert isinstance(payload, ExecuteToolPayload)
                if self.execute_tool is None:
                    return self._error_response(
                        envelope, "unimplemented", "execute_tool callback missing"
                    )
                try:
                    return self._ok_response(envelope, await self.execute_tool(payload))
                except Exception as exc:
                    return self._exception_response(envelope, exc, default_code="execution_failed")
            case "read_resource":
                assert isinstance(payload, ReadResourcePayload)
                if self.read_resource is None:
                    return self._error_response(
                        envelope, "unimplemented", "read_resource callback missing"
                    )
                try:
                    return self._ok_response(
                        envelope,
                        {"uri": payload.uri, "contents": await self.read_resource(payload)},
                    )
                except Exception as exc:
                    return self._exception_response(
                        envelope, exc, default_code="resource_read_failed"
                    )
            case "resource_result":
                assert isinstance(payload, ResourceResultPayload)
                self.last_resource_result = payload.model_dump()
                return self._ok_response(envelope, payload.model_dump())
            case "get_prompt":
                assert isinstance(payload, GetPromptPayload)
                if self.get_prompt is None:
                    return self._error_response(
                        envelope, "unimplemented", "get_prompt callback missing"
                    )
                try:
                    return self._ok_response(
                        envelope,
                        {"name": payload.name, "messages": await self.get_prompt(payload)},
                    )
                except Exception as exc:
                    return self._exception_response(envelope, exc, default_code="prompt_get_failed")
            case "prompt_result":
                assert isinstance(payload, PromptResultPayload)
                self.last_prompt_result = payload.model_dump()
                return self._ok_response(envelope, payload.model_dump())
            case "execution_progress":
                assert isinstance(payload, ExecutionProgressPayload)
                self.last_progress = payload.model_dump()
                return self._ok_response(envelope, payload.model_dump())
            case "execution_result":
                assert isinstance(payload, ExecutionResultPayload)
                self.last_execution_result = payload.model_dump()
                return self._ok_response(envelope, payload.model_dump())
            case "execution_error":
                assert isinstance(payload, ExecutionErrorPayload)
                self.last_execution_error = payload.model_dump()
                return self._ok_response(envelope, payload.model_dump())
            case (
                "heartbeat"
                | "disconnect_notice"
            ):
                return self._ok_response(envelope)
            case _:
                return self._error_response(envelope, "unsupported", envelope.message_type)

    def validate_message(self, message: dict[str, Any]) -> RLPEnvelope:
        envelope = RLPEnvelope.model_validate(message)
        if envelope.protocol != "rlp":
            raise ValueError("RLP messages must have protocol='rlp'")
        if envelope.version != "1.0":
            raise ValueError(f"Unsupported RLP version: {envelope.version}")
        return envelope

    def bound_client_count(self) -> int:
        return len(self._bound_clients)

    def _build_snapshot_details(self) -> dict[str, Any]:
        snapshot = self.registry.snapshot()
        return {
            "registry_revision": snapshot["revision"],
            "tools": [self._serialize_tool(tool) for tool in snapshot["tools"]],
            "resources": [self._serialize_resource(resource) for resource in snapshot["resources"]],
            "prompts": [self._serialize_prompt(prompt) for prompt in snapshot["prompts"]],
        }

    def _replace_registry_from_snapshot(self, payload: SnapshotPayload) -> None:
        snapshot = {
            "revision": payload.registry_revision,
            "tools": [
                ToolDefinition(
                    name=tool.name,
                    title=tool.title,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    metadata=tool.metadata,
                )
                for tool in payload.tools
            ],
            "resources": [
                ResourceDefinition(
                    uri=resource.uri,
                    name=resource.name,
                    description=resource.description,
                    mime_type=resource.mime_type,
                    metadata=resource.metadata,
                )
                for resource in payload.resources
            ],
            "prompts": [
                PromptDefinition(
                    name=prompt.name,
                    description=prompt.description,
                    arguments=[argument.model_dump() for argument in prompt.arguments],
                    metadata=prompt.metadata,
                )
                for prompt in payload.prompts
            ],
        }
        self.registry.replace_from_snapshot(snapshot)

    def mark_stale(self) -> None:
        self.registry.mark_stale()

    def _validate_incremental_revision(self, revision: int) -> dict[str, Any] | None:
        expected = self.registry.revision + 1
        if revision != expected:
            self.registry.mark_stale()
            envelope = RLPEnvelope(
                protocol="rlp",
                version="1.0",
                message_type="revision_gap",
                message_id=new_message_id(),
                relay_session_id=self.relay_session_id,
                source_relay_id=self.host_relay_id,
                payload={},
            )
            return self._error_response(
                envelope,
                "revision_gap",
                f"Expected registry revision {expected} but received {revision}",
            )
        self.registry.mark_fresh()
        return None

    def _upsert_tool(self, payload: ToolMutationPayload) -> None:
        existing = self.registry.get_tool(payload.tool.name)
        if existing is not None:
            self.registry.deregister_tool(payload.tool.name)
        self.registry.register_tool(
            ToolDefinition(
                name=payload.tool.name,
                title=payload.tool.title,
                description=payload.tool.description,
                input_schema=payload.tool.input_schema,
                output_schema=payload.tool.output_schema,
                metadata=payload.tool.metadata,
            )
        )

    def _upsert_resource(self, payload: ResourceMutationPayload) -> None:
        existing = self.registry.get_resource(payload.resource.uri)
        if existing is not None:
            self.registry.deregister_resource(payload.resource.uri)
        self.registry.register_resource(
            ResourceDefinition(
                uri=payload.resource.uri,
                name=payload.resource.name,
                description=payload.resource.description,
                mime_type=payload.resource.mime_type,
                metadata=payload.resource.metadata,
            )
        )

    def _upsert_prompt(self, payload: PromptMutationPayload) -> None:
        existing = self.registry.get_prompt(payload.prompt.name)
        if existing is not None:
            self.registry.deregister_prompt(payload.prompt.name)
        self.registry.register_prompt(
            PromptDefinition(
                name=payload.prompt.name,
                description=payload.prompt.description,
                arguments=[item.model_dump() for item in payload.prompt.arguments],
                metadata=payload.prompt.metadata,
            )
        )

    def _serialize_tool(self, tool: Any) -> dict[str, Any]:
        payload = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "metadata": tool.metadata,
        }
        if tool.title is not None:
            payload["title"] = tool.title
        if tool.output_schema is not None:
            payload["output_schema"] = tool.output_schema
        return payload

    def _serialize_resource(self, resource: Any) -> dict[str, Any]:
        payload = {
            "uri": resource.uri,
            "name": resource.name,
            "metadata": resource.metadata,
        }
        if resource.description is not None:
            payload["description"] = resource.description
        if resource.mime_type is not None:
            payload["mime_type"] = resource.mime_type
        return payload

    def _serialize_prompt_argument(self, argument: dict[str, Any]) -> dict[str, Any]:
        payload = {"name": argument["name"], "required": bool(argument.get("required", False))}
        if argument.get("description") is not None:
            payload["description"] = argument["description"]
        return payload

    def _serialize_prompt(self, prompt: Any) -> dict[str, Any]:
        return {
            "name": prompt.name,
            "description": prompt.description,
            "arguments": [self._serialize_prompt_argument(argument) for argument in prompt.arguments],
            "metadata": prompt.metadata,
        }

    def _ok_response(
        self, envelope: RLPEnvelope, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = StatusPayload(status="ok", details=details or {}).model_dump()
        return {
            "protocol": "rlp",
            "version": "1.0",
            "message_type": f"{envelope.message_type}_response",
            "message_id": new_message_id(),
            "relay_session_id": self.relay_session_id,
            "source_relay_id": self.host_relay_id,
            "target_relay_id": envelope.source_relay_id,
            "request_id": envelope.request_id or envelope.message_id,
            "execution_id": envelope.execution_id,
            "payload": payload,
        }

    def _error_response(
        self,
        envelope: RLPEnvelope,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = StatusPayload(
            status="error",
            code=code,
            message=message,
            details=details or {},
        ).model_dump()
        return {
            "protocol": "rlp",
            "version": "1.0",
            "message_type": f"{envelope.message_type}_response",
            "message_id": new_message_id(),
            "relay_session_id": self.relay_session_id,
            "source_relay_id": self.host_relay_id,
            "target_relay_id": envelope.source_relay_id,
            "request_id": envelope.request_id or envelope.message_id,
            "execution_id": envelope.execution_id,
            "payload": payload,
        }

    def _exception_response(
        self,
        envelope: RLPEnvelope,
        exc: Exception,
        *,
        default_code: str,
    ) -> dict[str, Any]:
        from naia_relay.errors import ProtocolError

        if isinstance(exc, ProtocolError):
            details = dict(exc.data)
            details.setdefault("exception_type", type(exc).__name__)
            details.setdefault("detail", str(exc))
            return self._error_response(envelope, exc.code, str(exc), details)
        return self._error_response(
            envelope,
            default_code,
            str(exc),
            {
                "exception_type": type(exc).__name__,
                "detail": str(exc),
            },
        )
