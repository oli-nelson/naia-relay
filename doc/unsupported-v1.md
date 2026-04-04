# Unsupported or Deferred v1 Features

This document summarizes intentional v1 limitations.

## MCP features explicitly unsupported in v1

The relay currently returns explicit unsupported responses for:

- `sampling/createMessage`
- `roots/list`
- `completion/complete`

Expected result:

- MCP JSON-RPC error code `-32601`
- message indicating the feature is unsupported in `naia-relay v1`

## Transport limitations

### RLP over HTTP

Not supported in v1.

If configured, validation should fail before runtime startup.

### stdio on both sides

Supported only when each side has a dedicated stdio channel.

`naia-relay` cannot use one shared stdin/stdout pair for two independent peers.

## Current implementation notes

- integration coverage exists for direct and bridged topologies
- external-process end-to-end orchestration is still lighter than the full spec vision
- the `tests/e2e/` area is reserved for future process-level coverage

## Expected structured runtime errors

Examples of explicit runtime error categories used in the implementation:

- `timeout`
- `transport_failure`
- `relay_link_bind_failed`
- `stale_registry`
- `unknown_tool`
- `unknown_resource`
- `unknown_prompt`
- `backpressure_limit_exceeded`
- `slow_consumer_limit_exceeded`
