from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PendingRequest:
    request_id: str
    message_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionState:
    execution_id: str
    tool_name: str
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


class RequestTracker:
    def __init__(self) -> None:
        self._requests: dict[str, PendingRequest] = {}

    def add(self, request: PendingRequest) -> None:
        if request.request_id in self._requests:
            raise ValueError(f"Duplicate request_id: {request.request_id}")
        self._requests[request.request_id] = request

    def get(self, request_id: str) -> PendingRequest | None:
        return self._requests.get(request_id)

    def pop(self, request_id: str) -> PendingRequest | None:
        return self._requests.pop(request_id, None)

    def count(self) -> int:
        return len(self._requests)


class ExecutionTracker:
    def __init__(self) -> None:
        self._executions: dict[str, ExecutionState] = {}

    def add(self, state: ExecutionState) -> None:
        if state.execution_id in self._executions:
            raise ValueError(f"Duplicate execution_id: {state.execution_id}")
        self._executions[state.execution_id] = state

    def get(self, execution_id: str) -> ExecutionState | None:
        return self._executions.get(execution_id)

    def update_status(self, execution_id: str, status: str) -> ExecutionState:
        state = self._executions[execution_id]
        state.status = status
        return state

    def pop(self, execution_id: str) -> ExecutionState | None:
        return self._executions.pop(execution_id, None)

    def count(self) -> int:
        return len(self._executions)
