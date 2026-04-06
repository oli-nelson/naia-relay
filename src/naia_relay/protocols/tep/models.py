from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TEPBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _coerce_empty_list_to_dict(value: Any) -> Any:
    if value == []:
        return {}
    return value


class ExecutorCapabilities(TEPBaseModel):
    tools: bool = True
    resources: bool = True
    prompts: bool = True


class RegisterExecutorPayload(TEPBaseModel):
    executor_id: str
    display_name: str | None = None
    capabilities: ExecutorCapabilities = Field(default_factory=ExecutorCapabilities)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class ToolPayload(TEPBaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    title: str | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_input_schema = field_validator("input_schema", mode="before")(
        _coerce_empty_list_to_dict
    )
    _normalize_output_schema = field_validator("output_schema", mode="before")(
        _coerce_empty_list_to_dict
    )
    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class RegisterToolsPayload(TEPBaseModel):
    tools: list[ToolPayload]


class DeregisterToolsPayload(TEPBaseModel):
    tool_names: list[str]


class ResourcePayload(TEPBaseModel):
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class RegisterResourcesPayload(TEPBaseModel):
    resources: list[ResourcePayload]


class DeregisterResourcesPayload(TEPBaseModel):
    resource_uris: list[str]


class ReadResourcePayload(TEPBaseModel):
    uri: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)

    _normalize_arguments = field_validator("arguments", mode="before")(_coerce_empty_list_to_dict)
    _normalize_context = field_validator("context", mode="before")(_coerce_empty_list_to_dict)


class ResourceResultPayload(TEPBaseModel):
    uri: str
    contents: list[Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class PromptArgumentPayload(TEPBaseModel):
    name: str
    description: str | None = None
    required: bool = False


class PromptPayload(TEPBaseModel):
    name: str
    description: str
    arguments: list[PromptArgumentPayload] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class RegisterPromptsPayload(TEPBaseModel):
    prompts: list[PromptPayload]


class DeregisterPromptsPayload(TEPBaseModel):
    prompt_names: list[str]


class GetPromptPayload(TEPBaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)

    _normalize_arguments = field_validator("arguments", mode="before")(_coerce_empty_list_to_dict)
    _normalize_context = field_validator("context", mode="before")(_coerce_empty_list_to_dict)


class PromptResultPayload(TEPBaseModel):
    name: str
    messages: list[Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class ExecuteToolPayload(TEPBaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False

    _normalize_arguments = field_validator("arguments", mode="before")(_coerce_empty_list_to_dict)
    _normalize_context = field_validator("context", mode="before")(_coerce_empty_list_to_dict)


class ProgressPayload(TEPBaseModel):
    message: str | None = None
    percentage: int | None = Field(default=None, ge=0, le=100)


class ExecutionProgressPayload(TEPBaseModel):
    tool_name: str
    progress: ProgressPayload


class ExecutionResultPayload(TEPBaseModel):
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    _normalize_result = field_validator("result", mode="before")(_coerce_empty_list_to_dict)
    _normalize_metadata = field_validator("metadata", mode="before")(_coerce_empty_list_to_dict)


class ExecutionErrorPayload(TEPBaseModel):
    tool_name: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    _normalize_details = field_validator("details", mode="before")(_coerce_empty_list_to_dict)


class HeartbeatPayload(TEPBaseModel):
    timestamp: str


class DisconnectPayload(TEPBaseModel):
    reason: str


class StatusPayload(TEPBaseModel):
    status: Literal["ok", "error"]
    code: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    _normalize_details = field_validator("details", mode="before")(_coerce_empty_list_to_dict)


MESSAGE_PAYLOAD_MODELS: dict[str, type[TEPBaseModel]] = {
    "register_executor": RegisterExecutorPayload,
    "register_tools": RegisterToolsPayload,
    "deregister_tools": DeregisterToolsPayload,
    "register_resources": RegisterResourcesPayload,
    "deregister_resources": DeregisterResourcesPayload,
    "read_resource": ReadResourcePayload,
    "resource_result": ResourceResultPayload,
    "register_prompts": RegisterPromptsPayload,
    "deregister_prompts": DeregisterPromptsPayload,
    "get_prompt": GetPromptPayload,
    "prompt_result": PromptResultPayload,
    "execute_tool": ExecuteToolPayload,
    "execution_progress": ExecutionProgressPayload,
    "execution_result": ExecutionResultPayload,
    "execution_error": ExecutionErrorPayload,
    "heartbeat": HeartbeatPayload,
    "shutdown": DisconnectPayload,
    "disconnect_notice": DisconnectPayload,
}
