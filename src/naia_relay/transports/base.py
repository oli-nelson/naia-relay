from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TransportAdapter(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None: ...

    @abstractmethod
    async def receive(self) -> dict[str, Any]: ...

    @abstractmethod
    def connection_info(self) -> dict[str, Any]: ...

    @abstractmethod
    def is_connected(self) -> bool: ...
