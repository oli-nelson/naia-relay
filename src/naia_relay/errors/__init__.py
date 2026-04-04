class NaiaRelayError(Exception):
    """Base error for the relay."""


class ConfigurationError(NaiaRelayError):
    """Raised when configuration is invalid."""


class TransportError(NaiaRelayError):
    """Raised when transport operations fail."""


class ProtocolError(NaiaRelayError):
    """Raised when protocol operations fail."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "protocol_error",
        data: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data or {}
