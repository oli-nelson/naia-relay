from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SessionKind = Literal["mcp", "tep", "rlp"]


@dataclass(slots=True)
class SessionState:
    session_id: str
    kind: SessionKind
    peer_id: str | None = None
    connected: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def add(self, session: SessionState) -> None:
        if session.session_id in self._sessions:
            raise ValueError(f"Duplicate session_id: {session.session_id}")
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def mark_connected(self, session_id: str, connected: bool) -> SessionState:
        session = self._sessions[session_id]
        session.connected = connected
        return session

    def remove(self, session_id: str) -> SessionState | None:
        return self._sessions.pop(session_id, None)

    def count(self, kind: SessionKind | None = None) -> int:
        if kind is None:
            return len(self._sessions)
        return sum(1 for session in self._sessions.values() if session.kind == kind)
