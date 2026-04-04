# Tool Executor Protocol (TEP) Reference

This document is the standalone protocol reference for the Tool Executor
Protocol used by `naia-relay`.

For normative product scope and architecture, see `SPEC.md`.

## Purpose

TEP is the executor-facing protocol between a relay and a Tool Executor.

Typical examples:

- Neovim registering tools with a host relay
- a relay asking the executor to run a tool
- a relay asking the executor to read a resource
- a relay asking the executor to materialize a prompt

## Design goals

- transport-independent semantics
- JSON v1 wire format
- explicit request/response and event flows
- support for tools, resources, and prompts
- support for concurrent in-flight executions

## Transport independence

TEP semantics must not change based on transport.

In v1, TEP can run over:

- `stdio`
- `tcp`
- `http`

Transport adapters are responsible for framing and delivery, not protocol
meaning.

## Encoding and framing

### Encoding

TEP v1 uses JSON.

### Framing

In the current v1 implementation:

- stdio: UTF-8 newline-delimited JSON
- tcp: UTF-8 newline-delimited JSON
- http: one JSON message per request body unless a documented streaming mode is enabled

## Envelope

Every TEP v1 message uses a common top-level JSON envelope.

```json
{
  "protocol": "tep",
  "version": "1.0",
  "message_type": "register_tools",
  "message_id": "msg_123",
  "session_id": "sess_executor_1",
  "request_id": "msg_122",
  "execution_id": "exec_123",
  "payload": {}
}
```

### Fields

- `protocol`
  - must be the literal string `tep`
- `version`
  - protocol version string
  - v1 is `1.0`
- `message_type`
  - the message kind
- `message_id`
  - unique id for the current message
- `session_id`
  - executor session identifier
- `request_id`
  - correlation id for request/response flows when applicable
- `execution_id`
  - required for execution-correlated flows
- `payload`
  - message-specific object

### Validation rules

- `protocol`, `version`, `message_type`, `message_id`, and `payload` are always required
- `execution_id` is required for:
  - `execute_tool`
  - `execution_progress`
  - `execution_result`
  - `execution_error`
- unknown or malformed envelopes are protocol errors
- unsupported `version` values must fail explicitly

## Message classes

TEP messages fall into three classes.

### Request

Expects one success or error response.

### Response

Answers a prior request.

### Event

Asynchronous notification without a direct response.

## Message catalog

### Executor/session lifecycle

- `register_executor`
- `heartbeat`
- `shutdown`
- `disconnect_notice`

### Tool registry

- `register_tools`
- `deregister_tools`

### Resource registry and reads

- `register_resources`
- `deregister_resources`
- `read_resource`
- `resource_result`

### Prompt registry and retrieval

- `register_prompts`
- `deregister_prompts`
- `get_prompt`
- `prompt_result`

### Tool execution

- `execute_tool`
- `execution_progress`
- `execution_result`
- `execution_error`

## Success and error response shape

For request/response flows, the relay and executor use a standard status payload.

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

## `register_executor`

Purpose:

- identify the executor for the current session
- declare high-level capabilities

Payload:

```json
{
  "executor_id": "nvim",
  "display_name": "Neovim",
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": true
  },
  "metadata": {}
}
```

Rules:

- `executor_id` is required
- `display_name` is optional but recommended
- `capabilities` may be extended in future versions

## `register_tools`

Purpose:

- add one or more tools to the authoritative executor-backed registry

Payload:

```json
{
  "tools": [
    {
      "name": "demo",
      "title": "Demo Tool",
      "description": "Runs the demo action",
      "input_schema": {},
      "output_schema": {},
      "metadata": {}
    }
  ]
}
```

Rules:

- `name`, `description`, and `input_schema` are required
- duplicate tool names are rejected
- one request may register multiple tools

## `deregister_tools`

Purpose:

- remove one or more tools from the authoritative registry

Payload:

```json
{
  "tool_names": ["demo"]
}
```

## `register_resources`

Purpose:

- register executor-backed resources

Payload:

```json
{
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

Rules:

- duplicate resource URIs are rejected

## `deregister_resources`

Payload:

```json
{
  "resource_uris": ["file:///demo"]
}
```

## `read_resource`

Purpose:

- request that the executor produce the current content for a resource

Payload:

```json
{
  "uri": "file:///demo",
  "arguments": {},
  "context": {}
}
```

Notes:

- `arguments` are caller-supplied parameters
- `context` may carry relay metadata or caller context

## `resource_result`

Purpose:

- return resource contents for a prior `read_resource`

Payload:

```json
{
  "uri": "file:///demo",
  "contents": [],
  "metadata": {}
}
```

## `register_prompts`

Purpose:

- register prompts exposed by the executor

Payload:

```json
{
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

## `deregister_prompts`

Payload:

```json
{
  "prompt_names": ["prompt"]
}
```

## `get_prompt`

Purpose:

- ask the executor to materialize a prompt

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

## `execute_tool`

Purpose:

- ask the executor to run a tool

Payload:

```json
{
  "tool_name": "demo",
  "arguments": {},
  "context": {},
  "stream": false
}
```

Rules:

- `tool_name` is required
- `arguments` is required
- `stream: true` means progress events may be emitted before completion

## `execution_progress`

Purpose:

- report non-terminal execution progress

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

Purpose:

- report successful or terminal non-error completion

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

Purpose:

- report terminal execution failure

Payload:

```json
{
  "tool_name": "demo",
  "code": "executor_error",
  "message": "Tool execution failed",
  "details": {}
}
```

## `heartbeat`

Purpose:

- keep the session alive
- prove liveness

Payload:

```json
{
  "timestamp": "2026-04-04T14:00:00Z"
}
```

## `shutdown` / `disconnect_notice`

Purpose:

- indicate graceful or abrupt end of executor availability

Payload:

```json
{
  "reason": "session ending"
}
```

## Correlation rules

### Request/response correlation

- use `request_id` to associate a response with a request
- if omitted on the request, implementations commonly echo the original `message_id`

### Execution correlation

- every execution flow must use `execution_id`
- progress/result/error messages for the same tool call must share that `execution_id`

## Typical flows

## Flow: register executor and tools

1. executor sends `register_executor`
2. executor sends `register_tools`
3. relay stores the tools in the authoritative registry
4. relay answers each request with `status: "ok"` or an error

## Flow: execute a tool

1. relay sends `execute_tool`
2. executor optionally emits `execution_progress`
3. executor emits either:
   - `execution_result`, or
   - `execution_error`

## Flow: read a resource

1. relay sends `read_resource`
2. executor replies with `resource_result`

## Flow: get a prompt

1. relay sends `get_prompt`
2. executor replies with `prompt_result`

## Validation and error expectations

The relay should reject:

- malformed envelopes
- unsupported versions
- missing required fields
- duplicate registrations
- invalid execution-correlation state

Typical error conditions:

- duplicate tool/resource/prompt registration
- unsupported message type
- unimplemented executor callback
- malformed payload

## Idempotency guidance

The spec calls out idempotency as an important behavior to define clearly.

At minimum, implementations should consider:

- executor registration retry behavior
- registration retry behavior
- deregistration retry behavior

## Current implementation notes

The current implementation code lives in:

- `src/naia_relay/protocols/tep/models.py`
- `src/naia_relay/protocols/tep/handler.py`

The handler currently:

- validates the TEP envelope
- validates payload schemas with Pydantic
- mutates the authoritative registry for tool/resource/prompt registration
- forwards execute/read/get requests through runtime callbacks
- records terminal progress/result/error payloads
- tracks executor availability after `disconnect_notice`

## Recommended deployment model

For the main Neovim workflow:

- Neovim acts as the Tool Executor
- Neovim talks TEP to a long-lived host relay
- that host relay owns authoritative registry state for the session
- downstream client relays mirror the resulting state via RLP
