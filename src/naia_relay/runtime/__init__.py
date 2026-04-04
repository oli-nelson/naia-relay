"""Role-specific runtime wiring."""

from naia_relay.runtime.relay import (
    BaseRelayRuntime,
    ClientRelayRuntime,
    DirectRelayRuntime,
    HostRelayRuntime,
    create_runtime,
    run_from_config,
    serve_mcp_stdio,
    serve_tep_stdio,
)

__all__ = [
    "BaseRelayRuntime",
    "ClientRelayRuntime",
    "DirectRelayRuntime",
    "HostRelayRuntime",
    "create_runtime",
    "run_from_config",
    "serve_mcp_stdio",
    "serve_tep_stdio",
]
