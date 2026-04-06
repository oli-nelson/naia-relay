# MCP Compatibility

This document summarizes the MCP-facing behavior that `naia-relay` currently
implements.

## Current runtime support

The main MCP runtime path in the executable is:

- `MCP stdio`
- `MCP http`

`MCP stdio` is the main path used by Codex-like clients in the current
implementation.

`MCP http` is available as a simple request/response runtime path.

## Implemented MCP areas

`naia-relay` currently implements the MCP behavior needed for:

- lifecycle / initialization
- tools
- resources
- prompts
- logging level updates

## Explicitly unsupported MCP features in v1

The relay currently returns explicit unsupported responses for:

- `sampling/createMessage`
- `roots/list`
- `completion/complete`

These are currently treated as unsupported v1 features rather than partially
implemented behavior.

## MCP stdio framing

For MCP over stdio, `naia-relay` expects:

- UTF-8 newline-delimited JSON

Logs and diagnostics should go to:

- `stderr`

Protocol traffic should remain on:

- `stdout`

## MCP protocol version

The current implementation is aligned with:

- MCP `2025-06-18`

Official MCP reference:

- <https://modelcontextprotocol.io/specification/2025-06-18/>

## Practical note

The main MCP paths you should rely on today are:

- MCP client ↔ `stdio` ↔ `naia-relay`
- MCP client ↔ `http` ↔ `naia-relay`

For HTTP MCP, the runtime currently accepts POST requests on:

- `/`
- `/mcp`

For operator guidance, see:

- [operator-guide.md](operator-guide.md)
- [integrations.md](integrations.md)
- [unsupported-v1.md](unsupported-v1.md)
