from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from naia_relay.config import ClientConfig, DirectConfig, HostConfig, RelayAppConfig
from naia_relay.core import (
    SessionManager,
    SessionState,
    new_execution_id,
    new_message_id,
    new_relay_id,
    new_session_id,
)
from naia_relay.errors import ConfigurationError, ProtocolError
from naia_relay.protocols.mcp import MCPHandler
from naia_relay.protocols.rlp import RLPHandler
from naia_relay.protocols.tep import TEPHandler
from naia_relay.registry import RegistryStore

RlpRequester = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class RuntimeStats:
    active_requests: int = 0
    active_executions: int = 0
    attached_clients: int = 0
    queue_depth: int = 0
    completed_requests: int = 0
    timed_out_requests: int = 0
    reconnect_attempts: int = 0
    stale_rejections: int = 0
    validation_failures: int = 0
    disconnects: int = 0
    slow_consumer_rejections: int = 0


@dataclass(slots=True)
class BaseRelayRuntime:
    config: RelayAppConfig
    role: str
    relay_id: str = field(default_factory=new_relay_id)
    session_id: str = field(default_factory=new_session_id)
    session_manager: SessionManager = field(default_factory=SessionManager)
    logger: logging.Logger = field(init=False)
    started: bool = False
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    max_in_flight_requests: int = field(init=False)
    max_queue_depth: int = field(init=False)
    connection_timeout_seconds: int = field(init=False)
    request_timeout_seconds: int = field(init=False)
    heartbeat_timeout_seconds: int = field(init=False)
    reconnect_attempts: int = field(init=False)
    last_heartbeat_at: float | None = None
    _requests_drained: asyncio.Event = field(init=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(f"naia_relay.runtime.{self.role}")
        self.max_in_flight_requests = self.config.relay.max_in_flight_requests
        self.max_queue_depth = self.config.relay.max_queue_depth
        self.connection_timeout_seconds = self.config.relay.connection_timeout_seconds
        self.request_timeout_seconds = self.config.relay.request_timeout_seconds
        self.heartbeat_timeout_seconds = self.config.relay.heartbeat_timeout_seconds
        self.reconnect_attempts = self.config.relay.reconnect_attempts
        self._requests_drained = asyncio.Event()
        self._requests_drained.set()

    async def start(self) -> None:
        transport_summary = ",".join(
            f"{name}:{value}" for name, value in self.transport_summary().items()
        )
        self.logger.info(
            "starting relay runtime",
            extra={
                "role": self.role,
                "protocol_side": "runtime",
                "transport": transport_summary,
                "session_id": self.session_id,
            },
        )
        self.started = True
        self.last_heartbeat_at = time.monotonic()
        self.logger.info(
            "runtime startup summary",
            extra={
                "role": self.role,
                "protocol_side": "runtime",
                "transport": transport_summary,
                "session_id": self.session_id,
            },
        )

    async def stop(self) -> None:
        if self.stats.active_requests > 0:
            self.logger.info(
                "waiting for in-flight requests to drain",
                extra={
                    "role": self.role,
                    "protocol_side": "runtime",
                    "transport": ",".join(
                        f"{name}:{value}" for name, value in self.transport_summary().items()
                    ),
                    "session_id": self.session_id,
                },
            )
            try:
                await asyncio.wait_for(
                    self._requests_drained.wait(),
                    timeout=self.request_timeout_seconds,
                )
            except TimeoutError:
                self.logger.warning(
                    "shutdown timed out waiting for in-flight requests",
                    extra={
                        "role": self.role,
                        "protocol_side": "runtime",
                        "session_id": self.session_id,
                    },
                )
        self.logger.info(
            "stopping relay runtime",
            extra={
                "role": self.role,
                "protocol_side": "runtime",
                "session_id": self.session_id,
            },
        )
        self.started = False

    def _ensure_started(self) -> None:
        if not self.started:
            raise RuntimeError(f"{self.role} runtime is not started")

    async def _guard_request(self) -> None:
        if self.stats.active_requests >= self.max_in_flight_requests:
            raise ProtocolError(
                "Maximum in-flight requests exceeded",
                code="backpressure_limit_exceeded",
                data={"max_in_flight_requests": self.max_in_flight_requests},
            )
        if self.stats.queue_depth >= self.max_queue_depth:
            self.stats.slow_consumer_rejections += 1
            self.logger.warning(
                "slow-consumer protection triggered",
                extra={
                    "role": self.role,
                    "protocol_side": "runtime",
                    "session_id": self.session_id,
                },
            )
            raise ProtocolError(
                "Maximum queue depth exceeded",
                code="slow_consumer_limit_exceeded",
                data={"max_queue_depth": self.max_queue_depth},
            )
        self.stats.queue_depth += 1
        self.stats.active_requests += 1
        self._requests_drained.clear()

    async def _finish_request(self) -> None:
        self.stats.active_requests = max(0, self.stats.active_requests - 1)
        self.stats.queue_depth = max(0, self.stats.queue_depth - 1)
        self.stats.completed_requests += 1
        if self.stats.active_requests == 0:
            self._requests_drained.set()

    async def _with_timeout(self, awaitable: Any, *, timeout: int, label: str) -> Any:
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout)
        except TimeoutError as exc:
            self.stats.timed_out_requests += 1
            self.logger.error(
                "%s timed out",
                label,
                extra={
                    "role": self.role,
                    "protocol_side": "runtime",
                    "session_id": self.session_id,
                },
            )
            raise ProtocolError(
                f"{label} timed out",
                code="timeout",
                data={"label": label, "timeout_seconds": timeout},
            ) from exc

    async def _with_request_timeout(self, awaitable: Any) -> Any:
        return await self._with_timeout(
            awaitable,
            timeout=self.request_timeout_seconds,
            label="Request",
        )

    def record_heartbeat(self) -> None:
        self.last_heartbeat_at = time.monotonic()

    def heartbeat_expired(self) -> bool:
        if self.last_heartbeat_at is None:
            return False
        return (time.monotonic() - self.last_heartbeat_at) > self.heartbeat_timeout_seconds

    def transport_summary(self) -> dict[str, str]:
        summary: dict[str, str] = {}
        if hasattr(self.config, "mcp") and self.config.mcp is not None:
            summary["mcp"] = self.config.mcp.transport
        if hasattr(self.config, "executor") and self.config.executor is not None:
            summary["executor"] = self.config.executor.transport
        if hasattr(self.config, "relay_link") and self.config.relay_link is not None:
            summary["relay_link"] = self.config.relay_link.transport
        return summary

    def record_validation_failure(
        self,
        exc: Exception,
        *,
        request_id: str | int | None = None,
    ) -> None:
        self.stats.validation_failures += 1
        self.logger.error(
            "protocol validation failed: %s",
            exc,
            extra={
                "role": self.role,
                "protocol_side": "runtime",
                "session_id": self.session_id,
                "request_id": str(request_id) if request_id is not None else "-",
            },
        )

    def record_disconnect(self, *, peer: str) -> None:
        self.stats.disconnects += 1
        self.logger.warning(
            "peer disconnected",
            extra={
                "role": self.role,
                "protocol_side": "runtime",
                "session_id": self.session_id,
                "transport": peer,
            },
        )


@dataclass(slots=True)
class DirectRelayRuntime(BaseRelayRuntime):
    config: DirectConfig
    role: str = "direct"
    registry: RegistryStore = field(default_factory=lambda: RegistryStore(mode="authoritative"))
    mcp_handler: MCPHandler = field(init=False)
    tep_handler: TEPHandler = field(init=False)

    def __post_init__(self) -> None:
        BaseRelayRuntime.__post_init__(self)
        self.mcp_handler = MCPHandler(
            registry=self.registry,
            execute_tool=self.call_tool,
            read_resource=self.read_resource,
            get_prompt=self.get_prompt,
        )
        self.tep_handler = TEPHandler(
            registry=self.registry,
            execute_tool=self._executor_execute_tool,
            read_resource=self._executor_read_resource,
            get_prompt=self._executor_get_prompt,
        )

    async def start(self) -> None:
        await BaseRelayRuntime.start(self)
        self.session_manager.add(
            SessionState(session_id=self.session_id, kind="mcp", peer_id="client")
        )
        self.session_manager.add(
            SessionState(session_id=f"{self.session_id}:executor", kind="tep", peer_id="executor")
        )

    async def handle_mcp_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        self._ensure_started()
        await self._guard_request()
        try:
            self.logger.debug(
                "handling mcp message",
                extra={
                    "role": self.role,
                    "protocol_side": "mcp",
                    "session_id": self.session_id,
                    "request_id": str(message.get("id", "-")),
                },
            )
            return await self._with_request_timeout(self.mcp_handler.handle_message(message))
        except Exception as exc:
            self.record_validation_failure(exc, request_id=message.get("id"))
            raise
        finally:
            await self._finish_request()

    async def handle_tep_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self._ensure_started()
        if message.get("message_type") == "heartbeat":
            self.record_heartbeat()
        try:
            return await self._with_request_timeout(self.tep_handler.handle_message(message))
        except Exception as exc:
            self.record_validation_failure(exc, request_id=message.get("message_id"))
            raise

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        execution_id = new_execution_id()
        self.stats.active_executions += 1
        try:
            if self.registry.get_tool(name) is None:
                raise ProtocolError(
                    f"Unknown tool: {name}",
                    code="unknown_tool",
                    data={"tool_name": name},
                )
            self.logger.debug(
                "starting tool execution",
                extra={
                    "role": self.role,
                    "protocol_side": "execution",
                    "session_id": self.session_id,
                    "execution_id": execution_id,
                },
            )
            return {"content": [{"type": "text", "text": f"{name}:{arguments}"}]}
        finally:
            self.stats.active_executions = max(0, self.stats.active_executions - 1)
            self.logger.debug(
                "completed tool execution",
                extra={
                    "role": self.role,
                    "protocol_side": "execution",
                    "session_id": self.session_id,
                    "execution_id": execution_id,
                },
            )

    async def read_resource(self, uri: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        if self.registry.get_resource(uri) is None:
            raise ProtocolError(
                f"Unknown resource: {uri}",
                code="unknown_resource",
                data={"uri": uri},
            )
        return [{"uri": uri, "arguments": arguments}]

    async def get_prompt(self, name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        if self.registry.get_prompt(name) is None:
            raise ProtocolError(
                f"Unknown prompt: {name}",
                code="unknown_prompt",
                data={"name": name},
            )
        return [{"role": "user", "content": {"name": name, "arguments": arguments}}]

    async def _executor_execute_tool(self, payload: Any) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": f"{payload.tool_name}:{payload.arguments}"}]
        }

    async def _executor_read_resource(self, payload: Any) -> list[Any]:
        return [{"uri": payload.uri, "context": payload.context}]

    async def _executor_get_prompt(self, payload: Any) -> list[Any]:
        return [{"role": "user", "content": {"name": payload.name, "arguments": payload.arguments}}]


@dataclass(slots=True)
class HostRelayRuntime(BaseRelayRuntime):
    config: HostConfig
    role: str = "host"
    registry: RegistryStore = field(default_factory=lambda: RegistryStore(mode="authoritative"))
    tep_handler: TEPHandler = field(init=False)
    rlp_handler: RLPHandler = field(init=False)

    def __post_init__(self) -> None:
        BaseRelayRuntime.__post_init__(self)
        self.tep_handler = TEPHandler(
            registry=self.registry,
            execute_tool=self._executor_execute_tool,
            read_resource=self._executor_read_resource,
            get_prompt=self._executor_get_prompt,
        )
        self.rlp_handler = RLPHandler(
            registry=self.registry,
            host_relay_id=self.relay_id,
            relay_session_id=self.session_id,
            execute_tool=self._rlp_execute_tool,
            read_resource=self._rlp_read_resource,
            get_prompt=self._rlp_get_prompt,
        )

    async def start(self) -> None:
        await BaseRelayRuntime.start(self)
        self.session_manager.add(
            SessionState(session_id=f"{self.session_id}:executor", kind="tep", peer_id="executor")
        )
        self.session_manager.add(
            SessionState(session_id=f"{self.session_id}:clients", kind="rlp", peer_id="clients")
        )

    async def handle_tep_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self._ensure_started()
        if message.get("message_type") == "heartbeat":
            self.record_heartbeat()
        try:
            return await self._with_request_timeout(self.tep_handler.handle_message(message))
        except Exception as exc:
            self.record_validation_failure(exc, request_id=message.get("message_id"))
            raise

    async def handle_rlp_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self._ensure_started()
        if message.get("message_type") == "heartbeat":
            self.record_heartbeat()
        try:
            response = await self._with_request_timeout(self.rlp_handler.handle_message(message))
        except Exception as exc:
            self.record_validation_failure(exc, request_id=message.get("message_id"))
            raise
        self.stats.attached_clients = self.rlp_handler.bound_client_count()
        return response

    async def _executor_execute_tool(self, payload: Any) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": f"{payload.tool_name}:{payload.arguments}"}]
        }

    async def _executor_read_resource(self, payload: Any) -> list[Any]:
        return [{"uri": payload.uri, "context": payload.context}]

    async def _executor_get_prompt(self, payload: Any) -> list[Any]:
        return [{"role": "user", "content": {"name": payload.name, "arguments": payload.arguments}}]

    async def _rlp_execute_tool(self, payload: Any) -> dict[str, Any]:
        return await self._executor_execute_tool(payload)

    async def _rlp_read_resource(self, payload: Any) -> list[Any]:
        return await self._executor_read_resource(payload)

    async def _rlp_get_prompt(self, payload: Any) -> list[Any]:
        return await self._executor_get_prompt(payload)


@dataclass(slots=True)
class ClientRelayRuntime(BaseRelayRuntime):
    config: ClientConfig
    role: str = "client"
    registry: RegistryStore = field(default_factory=lambda: RegistryStore(mode="mirrored"))
    mcp_handler: MCPHandler = field(init=False)
    rlp_handler: RLPHandler = field(init=False)
    _upstream_requester: RlpRequester | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        BaseRelayRuntime.__post_init__(self)
        self.mcp_handler = MCPHandler(
            registry=self.registry,
            execute_tool=self.call_tool,
            read_resource=self.read_resource,
            get_prompt=self.get_prompt,
        )
        self.rlp_handler = RLPHandler(
            registry=self.registry,
            host_relay_id="upstream_host",
            relay_session_id=self.session_id,
        )

    async def start(self) -> None:
        await BaseRelayRuntime.start(self)
        self.session_manager.add(
            SessionState(session_id=self.session_id, kind="mcp", peer_id="client")
        )
        self.session_manager.add(
            SessionState(session_id=f"{self.session_id}:upstream", kind="rlp", peer_id="host")
        )

    async def handle_mcp_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        self._ensure_started()
        await self._guard_request()
        try:
            self.logger.debug(
                "handling mcp message",
                extra={
                    "role": self.role,
                    "protocol_side": "mcp",
                    "session_id": self.session_id,
                    "request_id": str(message.get("id", "-")),
                },
            )
            return await self._with_request_timeout(self.mcp_handler.handle_message(message))
        except Exception as exc:
            self.record_validation_failure(exc, request_id=message.get("id"))
            raise
        finally:
            await self._finish_request()

    async def handle_rlp_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self._ensure_started()
        if message.get("message_type") == "heartbeat":
            self.record_heartbeat()
        try:
            return await self._with_request_timeout(self.rlp_handler.handle_message(message))
        except Exception as exc:
            self.record_validation_failure(exc, request_id=message.get("message_id"))
            raise

    async def bind_to_host(self, host: HostRelayRuntime) -> dict[str, Any]:
        return await self.bind_via_requester(
            host.handle_rlp_message,
            host_session_id=host.session_id,
            host_relay_id=host.relay_id,
        )

    async def bind_via_requester(
        self,
        requester: RlpRequester,
        *,
        host_session_id: str,
        host_relay_id: str,
    ) -> dict[str, Any]:
        self._upstream_requester = requester
        self.rlp_handler.host_relay_id = host_relay_id
        self.rlp_handler.relay_session_id = host_session_id
        self.registry.mark_stale()
        last_error: ProtocolError | None = None
        for attempt in range(self.reconnect_attempts + 1):
            self.stats.reconnect_attempts += 1
            self.logger.info(
                "attempting relay-link bind",
                extra={
                    "role": self.role,
                    "protocol_side": "relay_link",
                    "session_id": self.session_id,
                    "transport": self.config.relay_link.transport,
                },
            )
            try:
                response = await self._with_timeout(
                    requester(
                        {
                            "protocol": "rlp",
                            "version": "1.0",
                            "message_type": "bind_session",
                            "message_id": "msg_bind",
                            "relay_session_id": host_session_id,
                            "source_relay_id": self.relay_id,
                            "payload": {
                                "relay_session_id": host_session_id,
                                "client_instance_id": self.relay_id,
                            },
                        }
                    ),
                    timeout=self.connection_timeout_seconds,
                    label="Relay-link bind",
                )
            except ProtocolError as exc:
                last_error = exc
                self.mark_stale()
                if attempt >= self.reconnect_attempts:
                    break
                self.logger.warning(
                    "relay-link bind failed; retrying",
                    extra={
                        "role": self.role,
                        "protocol_side": "relay_link",
                        "session_id": self.session_id,
                    },
                )
                continue
            except Exception as exc:
                self.mark_stale()
                last_error = ProtocolError(
                    f"Relay-link bind failed: {exc}",
                    code="transport_failure",
                    data={"exception_type": type(exc).__name__, "detail": str(exc)},
                )
                if attempt >= self.reconnect_attempts:
                    break
                self.logger.warning(
                    "relay-link bind failed due to transport error; retrying",
                    extra={
                        "role": self.role,
                        "protocol_side": "relay_link",
                        "session_id": self.session_id,
                    },
                )
                continue
            if response["payload"]["status"] == "ok":
                details = response["payload"]["details"]
                snapshot_message = {
                    "protocol": "rlp",
                    "version": "1.0",
                    "message_type": "tool_snapshot",
                    "message_id": "msg_snapshot",
                    "relay_session_id": host_session_id,
                    "source_relay_id": host_relay_id,
                    "payload": details,
                }
                await self.handle_rlp_message(snapshot_message)
                self.logger.info(
                    "relay-link bind succeeded",
                    extra={
                        "role": self.role,
                        "protocol_side": "relay_link",
                        "session_id": self.session_id,
                    },
                )
                return response
            last_error = ProtocolError(
                "Failed to bind client relay to host relay",
                code="relay_link_bind_failed",
            )
        raise last_error or ProtocolError(
            "Failed to bind client relay to host relay",
            code="relay_link_bind_failed",
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        execution_id = new_execution_id()
        if self.registry.stale:
            self.stats.stale_rejections += 1
            raise ProtocolError(
                "Client relay registry is stale; resync required before execution",
                code="stale_registry",
            )
        if self.registry.get_tool(name) is None:
            raise ProtocolError(
                f"Unknown tool: {name}",
                code="unknown_tool",
                data={"tool_name": name},
            )
        self.logger.debug(
            "forwarding mirrored tool execution",
            extra={
                "role": self.role,
                "protocol_side": "execution",
                "session_id": self.session_id,
                "execution_id": execution_id,
            },
        )
        if self._upstream_requester is None:
            return {"content": [{"type": "text", "text": f"{name}:{arguments}"}]}
        response = await self._upstream_requester(
            {
                "protocol": "rlp",
                "version": "1.0",
                "message_type": "execute_tool",
                "message_id": new_message_id(),
                "relay_session_id": self.rlp_handler.relay_session_id,
                "source_relay_id": self.relay_id,
                "execution_id": execution_id,
                "payload": {"tool_name": name, "arguments": arguments},
            }
        )
        if response["payload"]["status"] != "ok":
            raise ProtocolError(
                response["payload"].get("message", "Upstream tool execution failed"),
                code=str(response["payload"].get("code", "upstream_error")),
            )
        return response["payload"]["details"]

    async def read_resource(self, uri: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        if self.registry.stale:
            self.stats.stale_rejections += 1
            raise ProtocolError(
                "Client relay registry is stale; resync required before reads",
                code="stale_registry",
            )
        if self.registry.get_resource(uri) is None:
            raise ProtocolError(
                f"Unknown resource: {uri}",
                code="unknown_resource",
                data={"uri": uri},
            )
        if self._upstream_requester is None:
            return [{"uri": uri, "arguments": arguments}]
        response = await self._upstream_requester(
            {
                "protocol": "rlp",
                "version": "1.0",
                "message_type": "read_resource",
                "message_id": new_message_id(),
                "relay_session_id": self.rlp_handler.relay_session_id,
                "source_relay_id": self.relay_id,
                "payload": {"uri": uri, "context": arguments},
            }
        )
        if response["payload"]["status"] != "ok":
            raise ProtocolError(
                response["payload"].get("message", "Upstream resource read failed"),
                code=str(response["payload"].get("code", "upstream_error")),
            )
        return response["payload"]["details"]["contents"]

    async def get_prompt(self, name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        if self.registry.stale:
            self.stats.stale_rejections += 1
            raise ProtocolError(
                "Client relay registry is stale; resync required before prompts",
                code="stale_registry",
            )
        if self.registry.get_prompt(name) is None:
            raise ProtocolError(
                f"Unknown prompt: {name}",
                code="unknown_prompt",
                data={"name": name},
            )
        if self._upstream_requester is None:
            return [{"role": "user", "content": {"name": name, "arguments": arguments}}]
        response = await self._upstream_requester(
            {
                "protocol": "rlp",
                "version": "1.0",
                "message_type": "get_prompt",
                "message_id": new_message_id(),
                "relay_session_id": self.rlp_handler.relay_session_id,
                "source_relay_id": self.relay_id,
                "payload": {"name": name, "arguments": arguments},
            }
        )
        if response["payload"]["status"] != "ok":
            raise ProtocolError(
                response["payload"].get("message", "Upstream prompt retrieval failed"),
                code=str(response["payload"].get("code", "upstream_error")),
            )
        return response["payload"]["details"]["messages"]

    def mark_stale(self) -> None:
        self.registry.mark_stale()
        self.rlp_handler.mark_stale()

    def on_rlp_disconnect(self) -> None:
        self.mark_stale()
        self._upstream_requester = None
        self.record_disconnect(peer="relay_link")
        self.logger.warning(
            "client relay marked stale after relay-link disconnect",
            extra={
                "role": self.role,
                "protocol_side": "relay_link",
                "session_id": self.session_id,
            },
        )


def create_runtime(config: RelayAppConfig) -> BaseRelayRuntime:
    if config.role == "direct":
        return DirectRelayRuntime(config=config)
    if config.role == "host":
        return HostRelayRuntime(config=config)
    if config.role == "client":
        return ClientRelayRuntime(config=config)
    raise ConfigurationError(f"Unsupported role: {config.role}")


async def run_from_config(config: RelayAppConfig, *, once: bool = True) -> BaseRelayRuntime:
    runtime = create_runtime(config)
    await runtime.start()
    if once:
        await runtime.stop()
    else:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:  # pragma: no cover - lifecycle convenience
            await runtime.stop()
            raise
    return runtime
