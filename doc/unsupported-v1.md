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

The implementation does not support a single direct-mode process using stdio
for both MCP and TEP on one shared stdin/stdout pair.

`naia-relay` cannot use one shared stdin/stdout pair for two independent peers.

Supported alternatives are:

- host mode with executor `stdio` and relay-link `tcp`
- client mode with MCP `stdio` and relay-link `tcp`
- bridged topologies where different relay processes own different stdio channels

## Current implementation notes

- integration coverage exists for direct and bridged topologies
- process-level `tests/e2e/` coverage exists for MCP stdio and TEP stdio runtime loops
- direct dual-stdio configuration is explicitly rejected at config validation time

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
