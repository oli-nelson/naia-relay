from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from naia_relay.errors import ConfigurationError

TransportType = Literal["stdio", "tcp", "http"]
RelayLinkTransportType = Literal["stdio", "tcp"]
RoleType = Literal["direct", "host", "client"]


class NaiaBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelayConfig(NaiaBaseModel):
    request_timeout_seconds: int = Field(default=60, ge=1)
    connection_timeout_seconds: int = Field(default=10, ge=1)
    heartbeat_timeout_seconds: int = Field(default=30, ge=1)
    max_message_size_bytes: int = Field(default=1_048_576, ge=1024)
    reject_duplicate_tool_names: bool = True
    log_level: str = "info"


class McpConfig(NaiaBaseModel):
    transport: TransportType
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_transport_requirements(self) -> McpConfig:
        if self.transport == "tcp":
            self.host = self.host or "127.0.0.1"
            if self.port is None:
                raise ValueError("mcp.port is required when mcp.transport=tcp")
        if self.transport == "http":
            self.host = self.host or "127.0.0.1"
            if self.port is None:
                raise ValueError("mcp.port is required when mcp.transport=http")
        return self


class TcpEndpointConfig(NaiaBaseModel):
    transport: TransportType
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    bind_host: str | None = None
    bind_port: int | None = Field(default=None, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_transport_requirements(self) -> TcpEndpointConfig:
        if self.transport == "tcp":
            if self.host is None and self.bind_host is None:
                self.host = "127.0.0.1"
            if self.port is None and self.bind_port is None:
                raise ValueError("tcp transport requires port or bind_port")
        if self.transport == "http":
            if self.host is None and self.bind_host is None:
                self.host = "127.0.0.1"
            if self.port is None and self.bind_port is None:
                raise ValueError("http transport requires port or bind_port")
        return self


class RelayLinkConfig(NaiaBaseModel):
    transport: RelayLinkTransportType
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    bind_host: str | None = None
    bind_port: int | None = Field(default=None, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_transport_requirements(self) -> RelayLinkConfig:
        if self.transport == "tcp":
            if self.host is None and self.bind_host is None:
                self.host = "127.0.0.1"
            if self.port is None and self.bind_port is None:
                raise ValueError("relay_link tcp transport requires port or bind_port")
        return self


class DirectConfig(NaiaBaseModel):
    role: Literal["direct"]
    mcp: McpConfig
    executor: TcpEndpointConfig
    relay: RelayConfig = Field(default_factory=RelayConfig)
    relay_link: None = None


class HostConfig(NaiaBaseModel):
    role: Literal["host"]
    executor: TcpEndpointConfig
    relay_link: RelayLinkConfig
    relay: RelayConfig = Field(default_factory=RelayConfig)
    mcp: None = None


class ClientConfig(NaiaBaseModel):
    role: Literal["client"]
    mcp: McpConfig
    relay_link: RelayLinkConfig
    relay: RelayConfig = Field(default_factory=RelayConfig)
    executor: None = None


RelayAppConfig = DirectConfig | HostConfig | ClientConfig


class RawConfig(NaiaBaseModel):
    role: RoleType
    mcp: McpConfig | None = None
    executor: TcpEndpointConfig | None = None
    relay_link: RelayLinkConfig | None = None
    relay: RelayConfig = Field(default_factory=RelayConfig)

    @model_validator(mode="after")
    def validate_for_role(self) -> RawConfig:
        if self.role == "direct":
            if self.mcp is None or self.executor is None:
                raise ValueError("role 'direct' requires both 'mcp' and 'executor'")
            if self.relay_link is not None:
                raise ValueError("role 'direct' must not define 'relay_link'")
        elif self.role == "host":
            if self.executor is None or self.relay_link is None:
                raise ValueError("role 'host' requires both 'executor' and 'relay_link'")
            if self.mcp is not None:
                raise ValueError("role 'host' must not define 'mcp'")
        elif self.role == "client":
            if self.mcp is None or self.relay_link is None:
                raise ValueError("role 'client' requires both 'mcp' and 'relay_link'")
            if self.executor is not None:
                raise ValueError("role 'client' must not define 'executor'")
        return self

    def to_typed_config(self) -> RelayAppConfig:
        payload = self.model_dump()
        role = payload["role"]
        if role == "direct":
            return DirectConfig(**payload)
        if role == "host":
            return HostConfig(**payload)
        return ClientConfig(**payload)


def parse_config(data: dict[str, Any]) -> RelayAppConfig:
    try:
        return RawConfig.model_validate(data).to_typed_config()
    except Exception as exc:  # pragma: no cover - shaped into ConfigurationError below
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(str(exc)) from exc
