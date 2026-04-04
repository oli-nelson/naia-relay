from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MCPBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JsonRpcRequest(MCPBaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcError(MCPBaseModel):
    code: int
    message: str
    data: dict[str, Any] = Field(default_factory=dict)

