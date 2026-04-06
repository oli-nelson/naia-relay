# MCP Compatibility

This document summarizes the MCP-facing behavior that `naia-relay` currently
implements.

## Current runtime support

The main MCP runtime path in the executable is:

- `MCP stdio`

That is the path used by Codex-like clients in the current implementation.

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

Although the repository contains other transport-related building blocks, the
main MCP path you should rely on today is:

- MCP client ↔ `stdio` ↔ `naia-relay`

For operator guidance, see:

- [operator-guide.md](operator-guide.md)
- [integrations.md](integrations.md)
- [unsupported-v1.md](unsupported-v1.md)
