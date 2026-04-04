class NaiaRelayError(Exception):
    """Base error for the relay."""


class ConfigurationError(NaiaRelayError):
    """Raised when configuration is invalid."""


class TransportError(NaiaRelayError):
    """Raised when transport operations fail."""


class ProtocolError(NaiaRelayError):
    """Raised when protocol operations fail."""
