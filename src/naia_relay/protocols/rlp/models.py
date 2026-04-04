from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from naia_relay.protocols.tep.models import PromptPayload, ResourcePayload, ToolPayload


class RLPBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HelloPayload(RLPBaseModel):
    relay_id: str
    role: Literal["host", "client"]
    capabilities: dict[str, bool] = Field(
        default_factory=lambda: {"tool_sync": True, "tool_execution": True}
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class BindSessionPayload(RLPBaseModel):
    relay_session_id: str
    session_token: str | None = None
    client_instance_id: str


class SnapshotPayload(RLPBaseModel):
    registry_revision: int
    tools: list[ToolPayload] = Field(default_factory=list)
    resources: list[ResourcePayload] = Field(default_factory=list)
    prompts: list[PromptPayload] = Field(default_factory=list)


class ToolMutationPayload(RLPBaseModel):
    registry_revision: int
    tool: ToolPayload


class ToolRemovedPayload(RLPBaseModel):
    registry_revision: int
    tool_name: str


class ResourceMutationPayload(RLPBaseModel):
    registry_revision: int
    resource: ResourcePayload


class ResourceRemovedPayload(RLPBaseModel):
    registry_revision: int
    uri: str


class PromptMutationPayload(RLPBaseModel):
    registry_revision: int
    prompt: PromptPayload


class PromptRemovedPayload(RLPBaseModel):
    registry_revision: int
    name: str


class ReadResourcePayload(RLPBaseModel):
    uri: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class ResourceResultPayload(RLPBaseModel):
    uri: str
    contents: list[Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class GetPromptPayload(RLPBaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class PromptResultPayload(RLPBaseModel):
    name: str
    messages: list[Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecuteToolPayload(RLPBaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class ProgressPayload(RLPBaseModel):
    message: str | None = None
    percentage: int | None = Field(default=None, ge=0, le=100)


class ExecutionProgressPayload(RLPBaseModel):
    tool_name: str
    progress: ProgressPayload


class ExecutionResultPayload(RLPBaseModel):
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionErrorPayload(RLPBaseModel):
    tool_name: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class HeartbeatPayload(RLPBaseModel):
    timestamp: str


class DisconnectPayload(RLPBaseModel):
    reason: str


class StatusPayload(RLPBaseModel):
    status: Literal["ok", "error"]
    code: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


MESSAGE_PAYLOAD_MODELS: dict[str, type[RLPBaseModel]] = {
    "hello": HelloPayload,
    "handshake": HelloPayload,
    "bind_session": BindSessionPayload,
    "tool_snapshot": SnapshotPayload,
    "resource_snapshot": SnapshotPayload,
    "prompt_snapshot": SnapshotPayload,
    "tool_added": ToolMutationPayload,
    "tool_updated": ToolMutationPayload,
    "tool_removed": ToolRemovedPayload,
    "resource_added": ResourceMutationPayload,
    "resource_updated": ResourceMutationPayload,
    "resource_removed": ResourceRemovedPayload,
    "prompt_added": PromptMutationPayload,
    "prompt_updated": PromptMutationPayload,
    "prompt_removed": PromptRemovedPayload,
    "read_resource": ReadResourcePayload,
    "resource_result": ResourceResultPayload,
    "get_prompt": GetPromptPayload,
    "prompt_result": PromptResultPayload,
    "execute_tool": ExecuteToolPayload,
    "execution_progress": ExecutionProgressPayload,
    "execution_result": ExecutionResultPayload,
    "execution_error": ExecutionErrorPayload,
    "heartbeat": HeartbeatPayload,
    "disconnect_notice": DisconnectPayload,
}
