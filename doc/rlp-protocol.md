# Relay Link Protocol (RLP) Reference

This document is the standalone protocol reference for the Relay Link Protocol
used by `naia-relay`.

For normative system architecture and scope, see `SPEC.md`.

## Purpose

RLP is the relay-to-relay protocol used between:

- a **host relay** near the Tool Executor
- a **client relay** near the MCP client

Its job is to:

- bind a client relay to a host relay session
- synchronize mirrored registry state
- forward tool/resource/prompt operations across relay boundaries

## Design goals

- transport-independent semantics
- JSON v1 wire format
- explicit host/client roles
- correctness-first reconnect and resync behavior
- support for tools, resources, and prompts

## Transport support

In the current v1 executable/runtime, RLP runs over:

- `tcp`

RLP over `http` is out of scope in v1.

## Encoding and framing

### Encoding

RLP v1 uses JSON.

### Framing

In the current v1 executable/runtime, RLP over tcp uses UTF-8 newline-delimited JSON.

## Roles

RLP has two roles:

### Host relay

- owns authoritative state for a relay session
- serves one or more client relays
- forwards execution/read/get work toward the Tool Executor

### Client relay

- binds to one host relay session
- keeps a mirrored registry
- presents that state to an MCP client

## Envelope

Every RLP v1 message uses a common top-level envelope.

```json
{
  "protocol": "rlp",
  "version": "1.0",
  "message_type": "bind_session",
  "message_id": "msg_123",
  "relay_session_id": "sess_host_1",
  "source_relay_id": "relay_client_1",
  "target_relay_id": "relay_host_1",
  "request_id": "msg_122",
  "execution_id": "exec_123",
  "payload": {}
}
```

### Fields

- `protocol`
  - must be `rlp`
- `version`
  - v1 is `1.0`
- `message_type`
  - kind of message
- `message_id`
  - unique id for the current message
- `relay_session_id`
  - identifier of the host-served session being targeted
- `source_relay_id`
  - sender relay id
- `target_relay_id`
  - optional intended receiver id
- `request_id`
  - correlation id for request/response flows
- `execution_id`
  - required for execution-correlated flows
- `payload`
  - message-specific object

### Validation rules

- `protocol`, `version`, `message_type`, `message_id`, and `payload` are always required
- `relay_session_id` becomes mandatory once the target session is known
- `execution_id` is required for execution-related flows
- unsupported versions fail explicitly

## Message classes

RLP v1 uses:

- request
- response
- event

## Message catalog

### Session establishment

- `hello`
- `handshake`
- `bind_session`

### Mirrored registry synchronization

- `tool_snapshot`
- `tool_added`
- `tool_removed`
- `tool_updated`
- `resource_snapshot`
- `resource_added`
- `resource_removed`
- `resource_updated`
- `prompt_snapshot`
- `prompt_added`
- `prompt_removed`
- `prompt_updated`

### Forwarded operations

- `execute_tool`
- `execution_progress`
- `execution_result`
- `execution_error`
- `read_resource`
- `resource_result`
- `get_prompt`
- `prompt_result`

### Liveness and disconnect

- `heartbeat`
- `disconnect_notice`

## Success and error response shape

RLP request/response flows use the same standard status structure as TEP.

### Success

```json
{
  "status": "ok",
  "details": {}
}
```

### Error

```json
{
  "status": "error",
  "code": "machine_readable_code",
  "message": "Human-readable description",
  "details": {}
}
```

## Payload reference

## `hello` / `handshake`

Purpose:

- identify the relay instance
- declare coarse capabilities

Payload:

```json
{
  "relay_id": "relay_client_1",
  "role": "client",
  "capabilities": {
    "tool_sync": true,
    "tool_execution": true
  },
  "metadata": {}
}
```

## `bind_session`

Purpose:

- bind a client relay to a specific host relay session

Payload:

```json
{
  "relay_session_id": "sess_host_1",
  "session_token": "optional-secret",
  "client_instance_id": "relay_client_1"
}
```

Rules:

- `relay_session_id` is required
- `client_instance_id` is required
- `session_token` is optional unless the host requires it

On success:

- the host accepts the binding
- the host returns success details
- the client must rebuild from a fresh snapshot before serving new work

## `tool_snapshot`

Purpose:

- perform a full mirrored-registry rebuild

Payload:

```json
{
  "registry_revision": 12,
  "tools": [
    {
      "name": "demo",
      "title": "Demo Tool",
      "description": "Runs the demo action",
      "input_schema": {},
      "output_schema": {},
      "metadata": {}
    }
  ],
  "resources": [],
  "prompts": []
}
```

Notes:

- the current v1 snapshot shape includes tools, resources, and prompts together
- this is the primary correctness path for initial sync and resync

## `tool_added` / `tool_updated`

Payload:

```json
{
  "registry_revision": 13,
  "tool": {
    "name": "demo",
    "title": "Demo Tool",
    "description": "Runs the demo action",
    "input_schema": {},
    "output_schema": {},
    "metadata": {}
  }
}
```

## `tool_removed`

Payload:

```json
{
  "registry_revision": 14,
  "tool_name": "demo"
}
```

## `resource_snapshot`

Payload:

```json
{
  "registry_revision": 12,
  "resources": [
    {
      "uri": "file:///demo",
      "name": "demo",
      "description": "Demo resource",
      "mime_type": "text/plain",
      "metadata": {}
    }
  ]
}
```

## `resource_added` / `resource_updated`

Payload:

```json
{
  "registry_revision": 13,
  "resource": {
    "uri": "file:///demo",
    "name": "demo",
    "description": "Demo resource",
    "mime_type": "text/plain",
    "metadata": {}
  }
}
```

## `resource_removed`

Payload:

```json
{
  "registry_revision": 14,
  "uri": "file:///demo"
}
```

## `prompt_snapshot`

Payload:

```json
{
  "registry_revision": 12,
  "prompts": [
    {
      "name": "prompt",
      "description": "Prompt description",
      "arguments": [],
      "metadata": {}
    }
  ]
}
```

## `prompt_added` / `prompt_updated`

Payload:

```json
{
  "registry_revision": 13,
  "prompt": {
    "name": "prompt",
    "description": "Prompt description",
    "arguments": [],
    "metadata": {}
  }
}
```

## `prompt_removed`

Payload:

```json
{
  "registry_revision": 14,
  "name": "prompt"
}
```

## `execute_tool`

Purpose:

- forward a tool execution request from a client relay toward a host relay

Payload:

```json
{
  "tool_name": "demo",
  "arguments": {},
  "context": {},
  "stream": false
}
```

## `execution_progress`

Payload:

```json
{
  "tool_name": "demo",
  "progress": {
    "message": "working",
    "percentage": 50
  }
}
```

## `execution_result`

Payload:

```json
{
  "tool_name": "demo",
  "result": {},
  "is_error": false,
  "metadata": {}
}
```

## `execution_error`

Payload:

```json
{
  "tool_name": "demo",
  "code": "host_error",
  "message": "Execution failed",
  "details": {}
}
```

## `read_resource`

Payload:

```json
{
  "uri": "file:///demo",
  "arguments": {},
  "context": {}
}
```

## `resource_result`

Payload:

```json
{
  "uri": "file:///demo",
  "contents": [],
  "metadata": {}
}
```

## `get_prompt`

Payload:

```json
{
  "name": "prompt",
  "arguments": {},
  "context": {}
}
```

## `prompt_result`

Payload:

```json
{
  "name": "prompt",
  "messages": [],
  "metadata": {}
}
```

## `heartbeat`

Payload:

```json
{
  "timestamp": "2026-04-04T14:00:00Z"
}
```

## `disconnect_notice`

Payload:

```json
{
  "reason": "connection closing"
}
```

## Registry state model

### Host relay

The host relay is the source of truth for:

- tool definitions
- resource definitions
- prompt definitions
- registry revision ordering

### Client relay

The client relay maintains a mirrored registry for presentation to its MCP peer.

The mirror may become:

- fresh
- stale

When stale, the client relay must reject new forwarded operations until resync completes.

## Revision model

RLP uses a monotonic registry revision.

Rules:

- snapshots include the current `registry_revision`
- incremental mutation events include the resulting `registry_revision`
- if the client sees a revision gap, it must mark the mirror stale
- a fresh snapshot is preferred over trying to replay missing deltas

## Correlation rules

### Request/response correlation

- use `request_id` for ordinary request/response flows

### Execution correlation

- use `execution_id` for execute/progress/result/error flows

## Typical flows

## Flow: initial bind and snapshot

1. client relay sends `hello` or proceeds directly to `bind_session`
2. client relay sends `bind_session`
3. host relay validates:
   - session id
   - optional session token
4. host relay responds with success
5. host relay provides snapshot details
6. client relay rebuilds mirrored registry state
7. client relay begins serving MCP discovery and forwarded operations

## Flow: incremental sync

1. host relay state changes
2. host relay emits one of:
   - `tool_added`
   - `tool_removed`
   - `tool_updated`
   - resource/prompt equivalents
3. client relay applies the mutation if the revision is exactly expected

## Flow: forwarded tool execution

1. MCP client calls a tool on the client relay
2. client relay sends `execute_tool` upstream over RLP
3. host relay forwards to its executor-facing side
4. host relay returns:
   - `execution_result`, or
   - `execution_error`
5. client relay maps the result back to MCP

## Flow: reconnect and resnapshot

1. relay link disconnect occurs
2. client relay marks its mirror stale
3. client relay rejects new forwarded operations
4. client relay reconnects and rebinds
5. host relay sends a fresh snapshot
6. client relay rebuilds mirrored state
7. service resumes

## Validation and error expectations

The host relay should reject:

- wrong `relay_session_id`
- invalid required token when token protection is enabled
- malformed payloads
- unsupported versions

Typical error codes:

- `unknown_session`
- `invalid_token`
- `revision_gap`
- `unimplemented`

The runtime also uses structured local error categories such as:

- `timeout`
- `transport_failure`
- `relay_link_bind_failed`
- `stale_registry`

## Current implementation notes

The current implementation code lives in:

- `src/naia_relay/protocols/rlp/models.py`
- `src/naia_relay/protocols/rlp/handler.py`
- `src/naia_relay/runtime/relay.py`

The current implementation supports:

- binding to a host session
- full snapshot rebuild
- incremental tool/resource/prompt mutations
- revision-gap detection
- multi-client host tracking
- forwarded tool/resource/prompt operations through client runtime callbacks
- reconnect + resnapshot behavior

## Recommended deployment model

For the main Neovim/Codex workflow:

- Neovim owns a long-lived host relay
- each Codex session owns a short-lived client relay
- Codex talks MCP to its local client relay over stdio
- the client relay talks RLP to the host relay over tcp
- the host relay talks TEP to Neovim
