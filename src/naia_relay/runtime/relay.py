from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web

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
from naia_relay.protocols.tep.models import (
    ExecutionErrorPayload as TEPExecutionErrorPayload,
)
from naia_relay.protocols.tep.models import (
    ExecutionProgressPayload as TEPExecutionProgressPayload,
)
from naia_relay.protocols.tep.models import (
    ExecutionResultPayload as TEPExecutionResultPayload,
)
from naia_relay.protocols.tep.models import (
    PromptResultPayload as TEPPromptResultPayload,
)
from naia_relay.protocols.tep.models import (
    ResourceResultPayload as TEPResourceResultPayload,
)
from naia_relay.registry import RegistryStore
from naia_relay.transports import (
    LineJsonFramer,
    McpStdioTransportAdapter,
    StdioTransportAdapter,
    TcpTransportAdapter,
)
from naia_relay.transports.base import TransportAdapter

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
    resolved_listeners: dict[str, dict[str, Any]] = field(default_factory=dict)
    _tep_server: asyncio.AbstractServer | None = field(default=None, init=False, repr=False)
    _mcp_http_runner: web.AppRunner | None = field(default=None, init=False, repr=False)

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
        if self._tep_server is not None:
            self._tep_server.close()
            await self._tep_server.wait_closed()
            self._tep_server = None
        if self._mcp_http_runner is not None:
            await self._mcp_http_runner.cleanup()
            self._mcp_http_runner = None
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

    def readiness_payload(self) -> dict[str, Any]:
        return {
            "event": "listener_ready",
            "role": self.role,
            "relay_id": self.relay_id,
            "session_id": self.session_id,
            "listeners": self.resolved_listeners,
        }

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

    async def _start_tep_listener(self, *, bind_host: str, bind_port: int) -> None:
        async def handle_client(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            adapter = StdioTransportAdapter(
                reader=reader,
                writer=writer,
                max_message_size_bytes=self.config.relay.max_message_size_bytes,
            )
            await adapter.start()
            attach_executor_transport = getattr(self, "attach_executor_transport", None)
            if callable(attach_executor_transport):
                attach_executor_transport(adapter)
            try:
                while self.started:
                    try:
                        message = await adapter.receive()
                    except Exception:
                        break
                    response = await _handle_tep_message_with_runtime(self, message)
                    if response is not None:
                        await adapter.send(response)
            finally:
                detach_executor_transport = getattr(self, "detach_executor_transport", None)
                if callable(detach_executor_transport):
                    detach_executor_transport(adapter)
                await adapter.stop()
                writer.close()
                await writer.wait_closed()

        self._tep_server = await asyncio.start_server(handle_client, bind_host, bind_port)
        sock = self._tep_server.sockets[0]
        host, port = sock.getsockname()[:2]
        self.resolved_listeners["executor"] = {
            "transport": "tcp",
            "host": host,
            "port": port,
        }

    async def _start_mcp_http_listener(self, *, bind_host: str, bind_port: int) -> None:
        await serve_mcp_http(self, bind_host=bind_host, bind_port=bind_port)


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
    _rlp_server: asyncio.AbstractServer | None = field(default=None, init=False, repr=False)
    _rlp_framer: LineJsonFramer = field(default_factory=LineJsonFramer, init=False, repr=False)
    _executor_transport: TransportAdapter | None = field(default=None, init=False, repr=False)
    _executor_send_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _pending_executor_requests: dict[str, asyncio.Future[Any]] = field(
        default_factory=dict, init=False, repr=False
    )
    _pending_executor_executions: dict[str, asyncio.Future[Any]] = field(
        default_factory=dict, init=False, repr=False
    )

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

    async def stop(self) -> None:
        if self._rlp_server is not None:
            self._rlp_server.close()
            await self._rlp_server.wait_closed()
            self._rlp_server = None
        if self._executor_transport is not None:
            self._executor_transport = None
        await BaseRelayRuntime.stop(self)

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
        if self._executor_transport is None:
            return await self._executor_execute_tool(payload)
        message_id = new_message_id()
        execution_id = new_execution_id()
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending_executor_executions[execution_id] = future
        await self._send_executor_message(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "execute_tool",
                "message_id": message_id,
                "session_id": f"{self.session_id}:executor",
                "execution_id": execution_id,
                "payload": {
                    "tool_name": payload.tool_name,
                    "arguments": payload.arguments,
                    "context": payload.context,
                    "stream": payload.stream,
                },
            }
        )
        try:
            return await self._with_request_timeout(future)
        finally:
            self._pending_executor_executions.pop(execution_id, None)

    async def _rlp_read_resource(self, payload: Any) -> list[Any]:
        if self._executor_transport is None:
            return await self._executor_read_resource(payload)
        message_id = new_message_id()
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending_executor_requests[message_id] = future
        await self._send_executor_message(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "read_resource",
                "message_id": message_id,
                "session_id": f"{self.session_id}:executor",
                "payload": {
                    "uri": payload.uri,
                    "arguments": payload.arguments,
                    "context": payload.context,
                },
            }
        )
        try:
            return await self._with_request_timeout(future)
        finally:
            self._pending_executor_requests.pop(message_id, None)

    async def _rlp_get_prompt(self, payload: Any) -> list[Any]:
        if self._executor_transport is None:
            return await self._executor_get_prompt(payload)
        message_id = new_message_id()
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending_executor_requests[message_id] = future
        await self._send_executor_message(
            {
                "protocol": "tep",
                "version": "1.0",
                "message_type": "get_prompt",
                "message_id": message_id,
                "session_id": f"{self.session_id}:executor",
                "payload": {
                    "name": payload.name,
                    "arguments": payload.arguments,
                    "context": payload.context,
                },
            }
        )
        try:
            return await self._with_request_timeout(future)
        finally:
            self._pending_executor_requests.pop(message_id, None)

    async def _send_executor_message(self, message: dict[str, Any]) -> None:
        if self._executor_transport is None:
            raise ProtocolError(
                "Executor transport is not connected",
                code="executor_not_connected",
            )
        async with self._executor_send_lock:
            await self._executor_transport.send(message)

    def attach_executor_transport(self, adapter: TransportAdapter) -> None:
        self._executor_transport = adapter

    def detach_executor_transport(self, adapter: TransportAdapter | None = None) -> None:
        if adapter is None or self._executor_transport is adapter:
            self._executor_transport = None

    async def handle_executor_stdio_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        message_type = str(message.get("message_type") or "")
        if message_type.endswith("_response"):
            request_id = str(message.get("request_id") or "")
            future = self._pending_executor_requests.get(request_id)
            if future is not None and not future.done():
                payload = message.get("payload", {})
                if isinstance(payload, dict) and payload.get("status") == "ok":
                    future.set_result(payload.get("details", {}))
                else:
                    future.set_exception(
                        ProtocolError(
                            str(payload.get("message", "Executor request failed")),
                            code=str(payload.get("code", "executor_error")),
                            data=payload.get("details", {}) if isinstance(payload, dict) else {},
                        )
                    )
            return None
        if message_type == "execution_progress":
            response = await self.tep_handler.handle_message_or_error(message)
            try:
                payload = TEPExecutionProgressPayload.model_validate(message.get("payload", {}))
            except Exception:
                return response
            self.rlp_handler.last_progress = payload.model_dump()
            return response
        if message_type == "execution_result":
            response = await self.tep_handler.handle_message_or_error(message)
            try:
                payload = TEPExecutionResultPayload.model_validate(message.get("payload", {}))
            except Exception:
                return response
            execution_id = str(message.get("execution_id") or "")
            future = self._pending_executor_executions.get(execution_id)
            if future is not None and not future.done():
                future.set_result(payload.result)
            self.rlp_handler.last_execution_result = payload.model_dump()
            return response
        if message_type == "execution_error":
            response = await self.tep_handler.handle_message_or_error(message)
            try:
                payload = TEPExecutionErrorPayload.model_validate(message.get("payload", {}))
            except Exception:
                return response
            execution_id = str(message.get("execution_id") or "")
            future = self._pending_executor_executions.get(execution_id)
            if future is not None and not future.done():
                future.set_exception(
                    ProtocolError(
                        payload.message,
                        code=payload.code,
                        data=payload.details,
                    )
                )
            self.rlp_handler.last_execution_error = payload.model_dump()
            return response
        if message_type == "resource_result":
            response = await self.tep_handler.handle_message_or_error(message)
            try:
                payload = TEPResourceResultPayload.model_validate(message.get("payload", {}))
            except Exception:
                return response
            request_id = str(message.get("request_id") or "")
            future = self._pending_executor_requests.get(request_id)
            if future is not None and not future.done():
                future.set_result(payload.contents)
            self.rlp_handler.last_resource_result = payload.model_dump()
            return response
        if message_type == "prompt_result":
            response = await self.tep_handler.handle_message_or_error(message)
            try:
                payload = TEPPromptResultPayload.model_validate(message.get("payload", {}))
            except Exception:
                return response
            request_id = str(message.get("request_id") or "")
            future = self._pending_executor_requests.get(request_id)
            if future is not None and not future.done():
                future.set_result(payload.messages)
            self.rlp_handler.last_prompt_result = payload.model_dump()
            return response
        return await self.tep_handler.handle_message_or_error(message)

    async def _start_rlp_listener(self, *, bind_port: int) -> None:
        bind_host = self.config.relay_link.bind_host or "127.0.0.1"

        async def handle_client(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    message = self._rlp_framer.decode(line)
                    response = await self.handle_rlp_message(message)
                    writer.write(self._rlp_framer.encode(response))
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        self._rlp_server = await asyncio.start_server(handle_client, bind_host, bind_port)
        sock = self._rlp_server.sockets[0]
        host, port = sock.getsockname()[:2]
        self.resolved_listeners["relay_link"] = {
            "transport": "tcp",
            "host": host,
            "port": port,
        }


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

    async def _tcp_round_trip(self, message: dict[str, Any]) -> dict[str, Any]:
        host = self.config.relay_link.host or "127.0.0.1"
        port = self.config.relay_link.port
        if port is None:
            raise ConfigurationError("client relay tcp transport requires relay_link.port")
        adapter = TcpTransportAdapter(
            host=host,
            port=port,
            max_message_size_bytes=self.config.relay.max_message_size_bytes,
        )
        await adapter.start()
        try:
            await adapter.send(message)
            return await adapter.receive()
        finally:
            await adapter.stop()

    async def _auto_bind_tcp_relay_link(self) -> None:
        hello = await self._with_timeout(
            self._tcp_round_trip(
                {
                    "protocol": "rlp",
                    "version": "1.0",
                    "message_type": "hello",
                    "message_id": new_message_id(),
                    "source_relay_id": self.relay_id,
                    "payload": {
                        "relay_id": self.relay_id,
                        "role": "client",
                        "capabilities": {"tool_sync": True, "tool_execution": True},
                        "metadata": {},
                    },
                }
            ),
            timeout=self.connection_timeout_seconds,
            label="Relay-link hello",
        )
        host_session_id = str(hello.get("relay_session_id") or "")
        host_relay_id = str(hello.get("source_relay_id") or "")
        if not host_session_id or not host_relay_id:
            raise ProtocolError(
                "Relay-link hello did not return host identity",
                code="relay_link_hello_failed",
            )
        await self.bind_via_requester(
            self._tcp_round_trip,
            host_session_id=host_session_id,
            host_relay_id=host_relay_id,
        )

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


def write_readiness_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


async def run_from_config(
    config: RelayAppConfig,
    *,
    once: bool = True,
    ready_file: Path | None = None,
) -> BaseRelayRuntime:
    runtime = create_runtime(config)
    await runtime.start()
    if getattr(config, "executor", None) is not None and config.executor.transport == "tcp":
        bind_host = config.executor.bind_host or config.executor.host or "127.0.0.1"
        bind_port = config.executor.bind_port
        if bind_port is not None:
            await runtime._start_tep_listener(bind_host=bind_host, bind_port=bind_port)
    if getattr(config, "mcp", None) is not None and config.mcp.transport == "http":
        bind_host = config.mcp.host or "127.0.0.1"
        bind_port = config.mcp.port
        if bind_port is None:
            raise ConfigurationError("mcp.port is required when mcp.transport=http")
        await runtime._start_mcp_http_listener(bind_host=bind_host, bind_port=bind_port)
    if isinstance(runtime, HostRelayRuntime) and config.relay_link.transport == "tcp":
        bind_port = config.relay_link.bind_port
        if bind_port is not None:
            await runtime._start_rlp_listener(bind_port=bind_port)
    if isinstance(runtime, ClientRelayRuntime) and config.relay_link.transport == "tcp":
        await runtime._auto_bind_tcp_relay_link()
    if ready_file is not None:
        write_readiness_file(ready_file, runtime.readiness_payload())
    if once:
        await runtime.stop()
    else:
        has_mcp = (
            hasattr(runtime, "handle_mcp_message")
            and getattr(config, "mcp", None) is not None
        )
        has_executor = (
            hasattr(runtime, "handle_tep_message")
            and getattr(config, "executor", None) is not None
        )

        if has_mcp and has_executor and config.executor.transport == "stdio":
            if config.mcp.transport == "stdio":
                await serve_mcp_stdio(runtime)
            else:
                await serve_tep_stdio(runtime)
        elif has_mcp:
            if config.mcp.transport == "stdio":
                await serve_mcp_stdio(runtime)
            elif config.mcp.transport == "http":
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:  # pragma: no cover - lifecycle convenience
                    await runtime.stop()
                    raise
            else:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:  # pragma: no cover - lifecycle convenience
                    await runtime.stop()
                    raise
        elif has_executor:
            if config.executor.transport == "stdio":
                await serve_tep_stdio(runtime)
            else:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:  # pragma: no cover - lifecycle convenience
                    await runtime.stop()
                    raise
        else:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:  # pragma: no cover - lifecycle convenience
                await runtime.stop()
                raise
    return runtime


async def serve_mcp_stdio(
    runtime: BaseRelayRuntime,
    *,
    reader: asyncio.StreamReader | None = None,
    writer: Any | None = None,
) -> None:
    if not hasattr(runtime, "handle_mcp_message"):
        raise ConfigurationError("Runtime does not support MCP stdio serving.")

    adapter = McpStdioTransportAdapter(
        reader=reader,
        writer=writer,
        max_message_size_bytes=runtime.config.relay.max_message_size_bytes,
    )
    await adapter.start()
    try:
        while runtime.started:
            try:
                message = await adapter.receive()
            except Exception:
                break
            response = await runtime.handle_mcp_message(message)  # type: ignore[attr-defined]
            if response is not None:
                await adapter.send(response)
    finally:
        await adapter.stop()
        await runtime.stop()


async def serve_mcp_http(
    runtime: BaseRelayRuntime,
    *,
    bind_host: str,
    bind_port: int,
) -> None:
    if not hasattr(runtime, "handle_mcp_message"):
        raise ConfigurationError("Runtime does not support MCP HTTP serving.")

    app = web.Application()

    async def handle_post(request: web.Request) -> web.StreamResponse:
        try:
            payload = await request.json()
        except Exception:
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Invalid JSON request body",
                    },
                },
                status=400,
            )
        status, response = await _handle_mcp_http_payload(runtime, payload)
        if response is None:
            return web.Response(status=status)
        return web.json_response(response, status=status)

    app.router.add_post("/", handle_post)
    app.router.add_post("/mcp", handle_post)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, bind_host, bind_port)
    await site.start()
    runtime._mcp_http_runner = runner
    runtime.resolved_listeners["mcp"] = {
        "transport": "http",
        "host": bind_host,
        "port": bind_port,
    }


async def _handle_mcp_http_payload(
    runtime: BaseRelayRuntime,
    payload: Any,
) -> tuple[int, dict[str, Any] | None]:
    if not hasattr(runtime, "handle_mcp_message"):
        raise ConfigurationError("Runtime does not support MCP HTTP serving.")
    if not isinstance(payload, dict):
        return (
            400,
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "HTTP MCP payload must be a JSON object",
                },
            },
        )

    response = await runtime.handle_mcp_message(payload)  # type: ignore[attr-defined]
    if response is None:
        return (202, None)
    return (200, response)


async def _handle_tep_message_with_runtime(
    runtime: BaseRelayRuntime,
    message: dict[str, Any],
) -> dict[str, Any] | None:
    custom_handler = getattr(runtime, "handle_executor_stdio_message", None)
    if callable(custom_handler):
        return await custom_handler(message)
    try:
        handler = runtime.tep_handler.handle_message_or_error  # type: ignore[attr-defined]
        return await handler(message)
    except AttributeError:
        return await runtime.handle_tep_message(message)  # type: ignore[attr-defined]


async def serve_tep_stdio(
    runtime: BaseRelayRuntime,
    *,
    reader: asyncio.StreamReader | None = None,
    writer: Any | None = None,
) -> None:
    if not hasattr(runtime, "handle_tep_message"):
        raise ConfigurationError("Runtime does not support TEP stdio serving.")

    adapter = StdioTransportAdapter(
        reader=reader,
        writer=writer,
        max_message_size_bytes=runtime.config.relay.max_message_size_bytes,
    )
    await adapter.start()
    attach_executor_transport = getattr(runtime, "attach_executor_transport", None)
    if callable(attach_executor_transport):
        attach_executor_transport(adapter)
    try:
        while runtime.started:
            try:
                message = await adapter.receive()
            except Exception:
                break
            response = await _handle_tep_message_with_runtime(runtime, message)
            if response is not None:
                await adapter.send(response)
    finally:
        detach_executor_transport = getattr(runtime, "detach_executor_transport", None)
        if callable(detach_executor_transport):
            detach_executor_transport(adapter)
        await adapter.stop()
        await runtime.stop()
