from __future__ import annotations

import asyncio

from naia_relay.core import from_json, to_json
from naia_relay.errors import TransportError


class LineJsonFramer:
    def __init__(self, max_message_size_bytes: int = 1_048_576) -> None:
        self.max_message_size_bytes = max_message_size_bytes

    def encode(self, message: dict[str, object]) -> bytes:
        payload = to_json(message).encode("utf-8")
        if len(payload) > self.max_message_size_bytes:
            raise TransportError("Message exceeds configured maximum message size.")
        return payload + b"\n"

    def decode(self, frame: bytes) -> dict[str, object]:
        if len(frame) > self.max_message_size_bytes:
            raise TransportError("Received frame exceeds configured maximum message size.")
        payload = frame.rstrip(b"\n")
        if not payload:
            raise TransportError("Received empty frame.")
        try:
            return from_json(payload.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - normalized below
            raise TransportError(f"Received malformed JSON frame: {exc}") from exc


class ContentLengthJsonFramer:
    def __init__(self, max_message_size_bytes: int = 1_048_576) -> None:
        self.max_message_size_bytes = max_message_size_bytes

    def encode(self, message: dict[str, object]) -> bytes:
        payload = to_json(message).encode("utf-8")
        if len(payload) > self.max_message_size_bytes:
            raise TransportError("Message exceeds configured maximum message size.")
        header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
        return header + payload

    def read_sync(self, reader: object) -> dict[str, object]:
        content_length: int | None = None

        while True:
            line = reader.readline()
            if not line:
                raise TransportError("stdio transport reached EOF")
            if line in {b"\r\n", b"\n"}:
                break
            try:
                header = line.decode("ascii").strip()
            except UnicodeDecodeError as exc:
                raise TransportError(f"Received malformed MCP header: {exc}") from exc
            if ":" not in header:
                raise TransportError(f"Received malformed MCP header line: {header!r}")
            name, value = header.split(":", 1)
            if name.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError as exc:
                    raise TransportError("Received invalid Content-Length header.") from exc

        if content_length is None:
            raise TransportError("Missing Content-Length header.")
        if content_length > self.max_message_size_bytes:
            raise TransportError("Received frame exceeds configured maximum message size.")

        payload = reader.read(content_length)
        if len(payload) != content_length:
            raise TransportError("Received truncated MCP message body.")

        try:
            return from_json(payload.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - normalized below
            raise TransportError(f"Received malformed JSON frame: {exc}") from exc

    async def read(self, reader: asyncio.StreamReader) -> dict[str, object]:
        content_length: int | None = None

        while True:
            line = await reader.readline()
            if not line:
                raise TransportError("stdio transport reached EOF")
            if line in {b"\r\n", b"\n"}:
                break
            try:
                header = line.decode("ascii").strip()
            except UnicodeDecodeError as exc:
                raise TransportError(f"Received malformed MCP header: {exc}") from exc
            if ":" not in header:
                raise TransportError(f"Received malformed MCP header line: {header!r}")
            name, value = header.split(":", 1)
            if name.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError as exc:
                    raise TransportError("Received invalid Content-Length header.") from exc

        if content_length is None:
            raise TransportError("Missing Content-Length header.")
        if content_length > self.max_message_size_bytes:
            raise TransportError("Received frame exceeds configured maximum message size.")

        try:
            payload = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError as exc:
            raise TransportError("Received truncated MCP message body.") from exc

        try:
            return from_json(payload.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - normalized below
            raise TransportError(f"Received malformed JSON frame: {exc}") from exc
