from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RegistryMode = Literal["authoritative", "mirrored"]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    title: str | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    owner_session_id: str | None = None


@dataclass(slots=True)
class ResourceDefinition:
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    owner_session_id: str | None = None


@dataclass(slots=True)
class PromptDefinition:
    name: str
    description: str
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    owner_session_id: str | None = None
