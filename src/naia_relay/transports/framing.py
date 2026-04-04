from __future__ import annotations

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
