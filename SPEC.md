# naia-relay Specification

## 1. Purpose

`naia-relay` is a Python system that sits between:

- an **MCP client/agent** such as Codex, and
- a **Tool Executor** that provides and executes tools.

The relay is **bidirectional**, **transport-agnostic**, and **extensible**. Either side of the relay may communicate over any supported transport, initially:

- `stdio`
- `tcp` (loopback-oriented)
- `http`

Examples:

1. Tool Executor `<--(stdio)-->` naia-relay `<--(tcp)-->` Codex
2. Tool Executor `<--(tcp)-->` naia-relay `<--(stdio)-->` Codex
3. Tool Executor `<--(stdio)-->` naia-relay `<--(http)-->` Codex
4. Tool Executor `<--(http)-->` naia-relay `<--(stdio)-->` Codex

Relay-bridge examples:

5. Neovim `<--(stdio TEP)-->` host naia-relay `<--(tcp RLP)-->` client naia-relay `<--(stdio MCP)-->` Codex
6. Neovim `<--(stdio TEP)-->` host naia-relay `<--(stdio RLP)-->` client naia-relay `<--(stdio MCP)-->` Codex
7. Tool Executor `<--(tcp TEP)-->` host naia-relay `<--(tcp RLP)-->` client naia-relay `<--(stdio MCP)-->` Codex
8. One Neovim session `<--(stdio TEP)-->` one host naia-relay `<--(tcp RLP)-->` many client naia-relay instances, each `<--(stdio MCP)-->` one Codex instance

Future transports must be addable without changing protocol semantics, for example:

- Unix domain sockets
- named pipes
- platform-specific local IPC mechanisms

---

## 2. Goals

### 2.1 Primary goals

The system must:

1. Implement the full MCP surface required for an MCP server-facing relay, following the Anthropic MCP specification.
2. Expose tools to MCP clients even when the actual tool implementation lives behind a separate Tool Executor.
3. Decouple **protocol logic** from **transport logic**.
4. Allow each side of the relay to use an independently configured transport.
5. Support dynamic tool registration and execution through a custom Tool Executor protocol.
6. Be easy to extend with new transports and new executor capabilities.

### 2.2 Non-goals

The first version does not need to:

- support distributed multi-host deployment as a primary use case
- define a generic remote service discovery mechanism
- persist state across restarts unless explicitly configured later
- alter or reinterpret MCP semantics based on transport choice

---

## 3. Core Design Principles

1. **Transport independence**  
   Protocol messages are defined once and must behave identically regardless of whether they travel over stdio, TCP, or HTTP.

2. **Protocol separation**  
   The relay handles three protocols:
   - **MCP** for agent-facing communication
   - **Tool Executor Protocol (TEP)** for executor-facing communication
   - **Relay Link Protocol (RLP)** for relay-to-relay communication

3. **Adapter-based architecture**  
   Every transport is implemented as a transport adapter behind a common interface.

4. **Capability extensibility**  
   New transports, new executor commands, and new internal policies should be addable with minimal impact on existing code.

5. **Faithful MCP behavior**  
   The relay should behave like a compliant MCP endpoint from the MCP client’s perspective.

6. **Local-first operation**  
   Initial TCP support is loopback-oriented for safety and simplicity.

---

## 4. System Context

`naia-relay` acts as a bridge:

- **Northbound side**: MCP client/agent connection
- **Southbound side**: Tool Executor connection

The MCP client believes it is talking to an MCP-capable server.
The Tool Executor believes it is talking to a relay using the custom executor protocol.

The relay is responsible for:

- managing connections on both sides
- translating between MCP tool operations and executor operations
- maintaining tool registry state
- correlating requests and responses
- propagating results, errors, and lifecycle events

The relay may also operate in a **bridged topology** where one relay instance connects to another relay instance instead of connecting directly to a Tool Executor.

In that topology:

- a **host relay** stays attached to the Tool Executor for the lifetime of the editor/tool-host session
- a **client relay** stays attached to the MCP client for the lifetime of the MCP session
- the two relays communicate through a dedicated relay-to-relay protocol

---

## 5. High-Level Architecture

The system should be structured into the following logical components.

The implementation must support these operating roles:

- **direct relay**: MCP client on one side, Tool Executor on the other
- **host relay**: Tool Executor on one side, downstream relays on the other
- **client relay**: MCP client on one side, upstream host relay on the other

### 5.1 Relay Core

The Relay Core contains transport-independent business logic:

- session management
- protocol dispatch
- request/response correlation
- tool registry
- capability negotiation
- error mapping
- lifecycle orchestration
- role-aware routing between MCP, TEP, and relay-link sessions

### 5.2 MCP Protocol Layer

Responsible for:

- implementing MCP server-side behavior
- parsing and validating MCP messages
- exposing tools and related capabilities to the MCP client
- handling MCP requests, notifications, and responses

### 5.3 Tool Executor Protocol Layer

Responsible for:

- parsing and validating custom Tool Executor messages
- handling executor registration
- receiving tool definitions
- dispatching tool invocations to the executor
- receiving execution results and executor-side errors

### 5.4 Transport Adapters

Each transport adapter is responsible only for:

- establishing the underlying connection
- sending raw protocol frames/messages
- receiving raw protocol frames/messages
- connection lifecycle handling specific to that transport

Transport adapters must not embed MCP or executor protocol rules.

### 5.4.1 Relay Link Protocol Layer

Responsible for:

- host/client relay handshake
- relay session binding
- authoritative tool snapshot distribution
- tool added / removed / updated propagation
- relayed tool execution requests and results
- relay-level disconnect and liveness signaling

Like MCP and TEP, the Relay Link Protocol must remain transport-independent.

### 5.5 Tool Registry

Maintains active knowledge of:

- registered tools
- tool metadata/schema
- owning executor session
- version or revision metadata if introduced
- registration status and availability

### 5.6 Session Manager

Maintains:

- MCP-side session state
- executor-side session state
- connection identifiers
- pending request correlation tables
- shutdown state

---

## 6. Supported Protocols

## 6.1 MCP

The relay must implement MCP as defined by the Anthropic specification for the role it exposes to the MCP client.

At minimum, the relay design must support:

- JSON-RPC 2.0 message structure and semantics used by MCP
- lifecycle management, including initialization, capability negotiation, and connection/session termination
- tools, including discovery and invocation flows
- resources, including discovery and retrieval flows
- prompts, including discovery and retrieval flows
- notifications and request/response flows defined by MCP
- error propagation in MCP-compatible form
- any other mandatory MCP features required for compliance

Because this specification intends `naia-relay` to implement the MCP core feature set rather than a tools-only subset, the relay should explicitly account for the main MCP feature groups described by the MCP specification:

- **Base protocol** built on JSON-RPC 2.0
- **Lifecycle management**
- **Server features**, including tools, resources, and prompts
- **Client features** where applicable to the relay role, including roots and sampling
- **Utilities** where applicable to the relay role, such as logging and argument completion

For avoidance of doubt:

- when `naia-relay` is acting as the MCP server-facing peer for Codex or another MCP client, it must correctly implement the server-side behavior for the MCP core features it exposes
- if the chosen MCP topology requires client-side MCP responsibilities on another side of the relay in a future version, those responsibilities must also follow the MCP specification rather than ad hoc relay-specific behavior

### MCP v1 feature coverage

The v1 implementation must define explicit behavior for the main MCP feature groups.

Required v1 support:

- **Base protocol / lifecycle**: full support
- **Tools**: full support
- **Resources**: full support
- **Prompts**: full support
- **Logging utility**: support if required by the MCP peer role and SDK behavior

Deferred from v1 unless later promoted:

- **Sampling**: not implemented in v1; requests must fail with a clear MCP-compatible unsupported-feature error if encountered
- **Roots**: not implemented in v1 unless required by the selected MCP SDK for baseline interoperability; if not implemented, requests must fail with a clear MCP-compatible unsupported-feature error
- **Completions / argument completion**: not implemented in v1 unless required for baseline interoperability; if not implemented, requests must fail with a clear MCP-compatible unsupported-feature error

Relay mapping rules for v1:

- tools registered through TEP and mirrored through RLP must be exposed through MCP tools
- resources and prompts must be represented in the relay's internal registry model, not treated as out-of-band exceptions
- if a feature is unsupported in v1, the relay must fail explicitly rather than silently ignoring the request

### MCP behavior requirement

From the MCP client perspective, the relay must appear as a valid MCP peer.  
The client must not need to know:

- that tools are actually backed by a separate Tool Executor
- which transport the relay uses internally or externally

### MCP compliance rule

Where this specification is silent, the Anthropic MCP specification is authoritative for MCP semantics.

The implementation phase should treat the official MCP specification and architecture documentation as the source of truth for:

- required lifecycle behavior
- capability negotiation rules
- primitive semantics for tools, resources, and prompts
- client/server feature boundaries
- transport-layer requirements relevant to supported MCP transports

Official MCP references:

- MCP concepts / architecture overview: https://modelcontextprotocol.io/docs/concepts/architecture
- MCP specification architecture page: https://modelcontextprotocol.io/specification/2025-06-18/architecture

## 6.2 Tool Executor Protocol (TEP)

The Tool Executor Protocol is a custom protocol between the relay and one or more Tool Executors.

Its responsibilities are:

- executor identification / registration
- tool registration and deregistration
- resource registration and deregistration
- prompt registration and deregistration
- tool execution requests
- resource read requests
- prompt retrieval requests
- tool execution progress and completion
- error reporting
- heartbeat / liveness signaling
- optional capability declaration

TEP semantics must be independent of transport.

### TEP encoding

TEP must use JSON messages.

Rationale:

- JSON is simple and easy to generate and parse in Python
- JSON aligns well with schema-based tool definitions and structured execution results
- JSON works naturally across stdio, TCP, and HTTP transports
- JSON is easy to inspect during development and debugging

Unless a strong future requirement emerges, non-JSON TEP encodings are out of scope.

## 6.3 Relay Link Protocol (RLP)

The Relay Link Protocol is a custom protocol between a **client relay** and a **host relay**.

Its responsibilities are:

- relay identity and handshake
- protocol version negotiation
- session binding between a client relay and a host relay
- tool registry snapshot delivery
- resource registry snapshot delivery
- prompt registry snapshot delivery
- tool added / removed / updated propagation
- resource added / removed / updated propagation
- prompt added / removed / updated propagation
- relayed tool execution requests
- relayed resource read requests
- relayed prompt retrieval requests
- relayed progress, result, and error delivery
- disconnect and liveness handling

RLP exists so that relay-to-relay communication does not overload either MCP or TEP semantics.

### RLP encoding

RLP should use JSON messages.

### Initial transport support

RLP is initially limited to:

- `stdio`
- `tcp`

HTTP transport is out of scope for RLP in v1.

---

## 7. Transport Model

## 7.1 General Requirements

Each side of the relay must allow independent transport configuration, subject to protocol-specific transport limits.

Example configuration model:

- MCP side transport: `stdio | tcp | http`
- Executor side transport: `stdio | tcp | http`
- Relay-link side transport: `stdio | tcp`

This creates combinations such as:

- stdio ↔ stdio
- stdio ↔ tcp
- tcp ↔ http
- http ↔ stdio

The transport must not affect:

- protocol message meaning
- available protocol features
- request/response correlation rules
- tool schemas or execution semantics

Protocol-specific transport support:

- MCP: `stdio | tcp | http`
- TEP: `stdio | tcp | http`
- RLP: `stdio | tcp`

## 7.2 Transport Adapter Interface

Each transport adapter should implement a common internal interface conceptually similar to:

- `start()`
- `stop()`
- `send(message)`
- `receive()`
- `connection_info()`
- `is_connected()`

Adapters may differ internally, but must present equivalent behavior to the Relay Core.

## 7.3 stdio Adapter

The stdio adapter must:

- read inbound protocol messages from stdin
- write outbound protocol messages to stdout
- avoid protocol corruption from logging on stdout
- direct logs/diagnostics to stderr or structured logging sinks

Typical use cases:

- local subprocess integration
- CLI-hosted MCP peers

### stdio on both sides

`stdio` may be configured on either side, including both sides at once, but each stdio connection requires its own dedicated process I/O channel.

Therefore:

- it is valid for the relay design to support `stdio ↔ stdio`
- it is not valid to assume one shared stdin/stdout pair can serve both endpoints simultaneously

In practice, dual-stdio setups require a process topology where the relay has separate stdio relationships to two different peer processes.

## 7.4 TCP Adapter

The TCP adapter must:

- support loopback binding/connection as the default
- define framing rules independent of protocol semantics
- support clean reconnect/error handling behavior where applicable

Typical use cases:

- local process-to-process communication
- development and debugging

## 7.5 HTTP Adapter

The HTTP adapter must:

- support request/response transport of protocol messages
- define how bidirectional semantics are handled over HTTP
- preserve protocol-level correlation and ordering guarantees where required
- account for MCP transport-layer requirements such as authorization if HTTP is used for MCP

Because HTTP is not inherently symmetric in the same way as stdio or TCP, the implementation must define a concrete relay model, for example:

- long polling
- streaming responses
- paired inbound/outbound endpoints
- server-sent events
- WebSocket-like upgrade in a future adapter, if desired

The exact HTTP transport mechanics may evolve, but they must remain a transport concern, not a protocol concern.

### HTTP transport behavior for v1

The v1 implementation must use a conservative HTTP model:

- one JSON protocol message per HTTP request body
- one JSON protocol message per HTTP response body for non-streaming exchanges
- HTTP transport support is allowed for MCP and TEP
- HTTP transport is not allowed for RLP in v1

Bidirectional and asynchronous behavior over HTTP in v1 should use one of these explicitly implemented patterns:

- request/response only for operations that naturally fit a single exchange
- streaming HTTP responses for server-to-client incremental delivery where needed
- SSE may be used for server-to-client event streaming if chosen during implementation

Deferred from v1:

- WebSocket transport
- arbitrary bidirectional multiplexing over a single HTTP connection
- HTTP support for RLP

If streaming HTTP is implemented in v1, the implementation plan must define:

- which MCP or TEP messages may stream
- how request and execution correlation IDs are preserved
- how disconnect and timeout behavior maps onto HTTP connection closure

## 7.6 Future Transport Extensibility

Adding a new transport must require:

- implementing the common transport adapter contract
- registering the adapter with the relay
- adding configuration support

It must not require changing core MCP or TEP semantics.

---

## 8. Connection Topology and Lifecycle

## 8.1 Basic topology

The relay manages two logical endpoints:

- **Agent-facing endpoint** (MCP)
- **Executor-facing endpoint** (TEP)

In relay-bridge mode, the relay instead manages one of these endpoint pairs:

- **host relay**
  - executor-facing endpoint (TEP)
  - downstream relay endpoint (RLP listener)
- **client relay**
  - agent-facing endpoint (MCP)
  - upstream host relay endpoint (RLP connector)

## 8.1.1 Recommended session model

The recommended local session model is:

- Neovim starts and owns a long-lived **host relay**
- the host relay stays alive for the duration of the Neovim session
- the host relay maintains the authoritative tool registry for that Neovim session
- Neovim may update registered tools at any time through TEP
- each Codex instance starts its own short-lived **client relay**
- each client relay talks to Codex over `stdio`
- each client relay connects to exactly one host relay over RLP

This model supports:

- static Codex MCP configuration
- multiple concurrent Codex instances
- multiple concurrent Neovim sessions
- strict pairing between one Codex session and one Neovim-hosted tool universe

## 8.1.2 Session identity and pairing rules

The implementation must define the following identities:

- **host relay instance ID**: unique per host relay process
- **client relay instance ID**: unique per client relay process
- **executor session ID**: unique per Tool Executor session
- **relay session ID**: unique per host-relay-served tool universe

For the primary Neovim use case:

- Neovim should generate the initial session identity for its tool-host session
- the host relay binds to that session identity
- each client relay must present the intended `relay_session_id` during RLP binding

Optional hardening:

- a host relay may also require a per-session secret token during RLP bind
- if used, the token must be generated by the host-side launcher and passed only to authorized client relays

Required behavior:

- if a client relay attempts to bind to an unknown session, the host relay must reject the connection
- if a presented session token is required and invalid, the host relay must reject the connection
- a client relay may be bound to exactly one host relay session at a time
- a host relay session may serve multiple client relays concurrently

## 8.2 Startup lifecycle

On startup, the relay should:

1. load configuration
2. initialize transport adapters
3. start listeners or outbound connectors as configured
4. initialize protocol handlers
5. establish role-specific connections:
   - direct relay: MCP and TEP peers
   - host relay: TEP peer and RLP listener
   - client relay: MCP peer and upstream host relay via RLP
6. expose only currently available tools unless configured otherwise

## 8.3 Shutdown lifecycle

On shutdown, the relay should:

1. stop accepting new requests
2. optionally allow in-flight requests to drain
3. notify connected peers where supported
4. close transports cleanly
5. release session and registry state

## 8.4 Failure handling

The relay must define behavior for:

- MCP side disconnect
- executor side disconnect
- relay restart
- in-flight request cancellation or timeout
- partial availability of tools

Recommended default behavior:

- if executor disconnects, tools from that executor become unavailable
- if MCP client disconnects, pending client-originated requests are cancelled where possible
- if a host relay disconnects from a client relay, the mirrored tools on that client relay become unavailable
- if a client relay disconnects, the host relay remains available for other client relays

---

## 9. Tool Model

## 9.1 Tool ownership

Every tool is owned by exactly one active Tool Executor session.

In bridged mode, the host relay is the authoritative source of tool state for downstream client relays, but tool ownership still belongs to the underlying Tool Executor session.

## 9.2 Tool registration

A Tool Executor must be able to register one or more tools dynamically.

Tool definition should include at least:

- stable tool name
- human-readable description
- input schema
- optional output schema
- optional metadata/capabilities

The executor-facing model must also support MCP resources and prompts in v1.

### Resource definition should include at least:

- stable resource URI
- human-readable name or title
- optional description
- MIME type where applicable
- metadata/capabilities

### Prompt definition should include at least:

- stable prompt name
- human-readable description
- argument schema or argument definitions where applicable
- metadata/capabilities

## 9.3 Tool visibility

The relay exposes the current set of registered tools to the MCP client as MCP tools.

In bridged mode:

- the host relay maintains the authoritative registry
- the client relay maintains a mirrored registry derived from RLP
- the MCP client sees only the mirrored tool set from the connected host relay by default

If multiple executors are supported in the future, the relay must define name collision policy, for example:

- reject duplicates
- namespace tools
- last-writer-wins (not recommended)

Recommended initial policy: **reject duplicate tool names unless explicit namespacing is configured**.

## 9.4 Tool deregistration

When an executor disconnects or explicitly deregisters a tool:

- the tool must be removed from the active registry
- subsequent MCP calls to that tool must fail with a clear error

## 9.5 Tool update propagation semantics

Tool registration changes are dynamic.

In direct mode:

- the relay must expose the current tool set through MCP according to MCP semantics

In bridged mode:

- the host relay must propagate tool changes to connected client relays through RLP
- the client relay must update its mirrored registry on receipt of those changes

Required v1 behavior:

- on initial RLP bind, the host relay must send a full `tool_snapshot`
- after successful bind, the host relay must send incremental `tool_added`, `tool_removed`, and `tool_updated` events
- on RLP reconnect, the client relay must discard its mirrored registry and rebuild it from a fresh `tool_snapshot`

For MCP-facing behavior:

- if MCP supports tool-list-changed notifications in a way applicable to the chosen peer, the client relay should emit them
- otherwise, changed tool state must be reflected on the next MCP tool discovery/list operation

In-flight execution behavior:

- if a tool is deregistered after an execution has already started, that in-flight execution may complete
- subsequent new executions of that tool must fail after deregistration takes effect

---

## 10. Request Flow

## 10.1 Tool registration flow

1. Tool Executor connects via configured transport.
2. Tool Executor registers itself and declares capabilities.
3. Tool Executor registers one or more tools.
4. Relay validates and stores tool definitions.
5. Relay makes those tools available through MCP tool discovery.

## 10.1.1 Resource registration flow

1. Tool Executor connects via configured transport.
2. Tool Executor registers one or more resources.
3. Relay validates and stores resource definitions.
4. Relay makes those resources available through MCP resource discovery.

## 10.1.2 Prompt registration flow

1. Tool Executor connects via configured transport.
2. Tool Executor registers one or more prompts.
3. Relay validates and stores prompt definitions.
4. Relay makes those prompts available through MCP prompt discovery.

## 10.2 Tool invocation flow

1. MCP client invokes a tool through MCP.
2. Relay validates that the tool exists and is available.
3. Relay creates a correlated execution request.
4. Relay sends an execution request to the owning Tool Executor using TEP.
5. Tool Executor executes the tool.
6. Tool Executor returns progress, result, or error.
7. Relay maps the outcome back into MCP response semantics.

## 10.2.1 Bridged tool invocation flow

In bridged mode:

1. MCP client invokes a tool on the client relay.
2. Client relay validates the mirrored tool entry.
3. Client relay sends an execution request to the host relay over RLP.
4. Host relay validates the authoritative tool entry.
5. Host relay sends the execution request to the Tool Executor over TEP.
6. Tool Executor executes the tool.
7. Tool Executor returns progress, result, or error to the host relay.
8. Host relay forwards the outcome to the client relay over RLP.
9. Client relay maps the outcome back into MCP response semantics.

## 10.2.2 Resource read flow

1. MCP client requests a resource through MCP.
2. Relay validates that the resource exists and is available.
3. Relay creates a correlated read request.
4. In direct mode, relay forwards the read request to the owning executor over TEP.
5. In bridged mode, client relay forwards the read request to host relay over RLP, then host relay forwards it to the executor over TEP.
6. The returned resource payload is mapped back into MCP response semantics.

## 10.2.3 Prompt retrieval flow

1. MCP client requests a prompt through MCP.
2. Relay validates that the prompt exists and is available.
3. Relay creates a correlated prompt request.
4. In direct mode, relay forwards the prompt request to the owning executor over TEP.
5. In bridged mode, client relay forwards the prompt request to host relay over RLP, then host relay forwards it to the executor over TEP.
6. The returned prompt payload is mapped back into MCP response semantics.

## 10.3 Error flow

Errors may originate from:

- invalid MCP request
- relay validation failure
- transport failure
- executor rejection
- tool runtime failure
- timeout/cancellation

The relay must preserve as much structured error detail as possible while still conforming to MCP response rules.

---

## 11. Tool Executor Protocol (TEP) Requirements

This section defines required message categories, not a final wire encoding.

## 11.1 Message categories

TEP must support at least:

1. `register_executor`
2. `register_tools`
3. `deregister_tools`
4. `register_resources`
5. `deregister_resources`
6. `read_resource`
7. `resource_result`
8. `register_prompts`
9. `deregister_prompts`
10. `get_prompt`
11. `prompt_result`
12. `execute_tool`
13. `execution_progress`
14. `execution_result`
15. `execution_error`
16. `heartbeat`
17. `shutdown` or `disconnect_notice`

## 11.1.1 TEP v1 envelope

TEP v1 messages must use a common JSON envelope with these top-level fields:

- `protocol`: literal string `tep`
- `version`: protocol version string, initially `1.0`
- `message_type`: message kind
- `message_id`: unique ID for this message
- `session_id`: executor session identifier
- `request_id`: present on request/response pairs when applicable
- `execution_id`: present on tool execution flows when applicable
- `payload`: message-specific object payload

Rules:

- every TEP message must include `protocol`, `version`, `message_type`, `message_id`, and `payload`
- `request_id` is required for messages that answer a prior request
- `execution_id` is required for `execute_tool`, `execution_progress`, `execution_result`, and `execution_error`
- unknown top-level fields should be ignored unless explicitly forbidden by a future version

## 11.1.2 TEP message classes

TEP v1 messages fall into three classes:

- **request**: expects exactly one success or error response
- **response**: answers a prior request
- **event**: asynchronous notification with no direct response

Required classification:

- `register_executor`: request
- `register_tools`: request
- `deregister_tools`: request
- `register_resources`: request
- `deregister_resources`: request
- `read_resource`: request
- `resource_result`: response
- `register_prompts`: request
- `deregister_prompts`: request
- `get_prompt`: request
- `prompt_result`: response
- `execute_tool`: request
- `execution_progress`: event
- `execution_result`: response or terminal event correlated by `execution_id`
- `execution_error`: response or terminal event correlated by `execution_id`
- `heartbeat`: event
- `shutdown` / `disconnect_notice`: event

## 11.1.3 TEP success and error payloads

For request/response flows, TEP v1 must standardize:

- success responses with `payload.status: "ok"`
- error responses with `payload.status: "error"`

Error payloads must include:

- `code`: machine-readable error code
- `message`: human-readable error description
- optional `details`: structured object

## 11.1.4 TEP v1 payload schemas

The following payload structures are required in TEP v1.

### `register_executor`

```json
{
  "executor_id": "string",
  "display_name": "string",
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": true
  },
  "metadata": {}
}
```

Rules:

- `executor_id` is required and stable for the lifetime of the executor session
- `capabilities` keys may be extended in future versions

### `register_tools`

```json
{
  "tools": [
    {
      "name": "string",
      "title": "string",
      "description": "string",
      "input_schema": {},
      "output_schema": {},
      "metadata": {}
    }
  ]
}
```

Rules:

- `name`, `description`, and `input_schema` are required
- `title`, `output_schema`, and `metadata` are optional
- a single request may register one or more tools

### `deregister_tools`

```json
{
  "tool_names": ["string"]
}
```

### `register_resources`

```json
{
  "resources": [
    {
      "uri": "string",
      "name": "string",
      "description": "string",
      "mime_type": "string",
      "metadata": {}
    }
  ]
}
```

### `deregister_resources`

```json
{
  "resource_uris": ["string"]
}
```

### `read_resource`

```json
{
  "uri": "string",
  "arguments": {},
  "context": {}
}
```

### `resource_result`

```json
{
  "uri": "string",
  "contents": [],
  "metadata": {}
}
```

### `register_prompts`

```json
{
  "prompts": [
    {
      "name": "string",
      "description": "string",
      "arguments": [],
      "metadata": {}
    }
  ]
}
```

### `deregister_prompts`

```json
{
  "prompt_names": ["string"]
}
```

### `get_prompt`

```json
{
  "name": "string",
  "arguments": {},
  "context": {}
}
```

### `prompt_result`

```json
{
  "name": "string",
  "messages": [],
  "metadata": {}
}
```

### `execute_tool`

```json
{
  "tool_name": "string",
  "arguments": {},
  "context": {},
  "stream": false
}
```

Rules:

- `tool_name` and `arguments` are required
- `context` is optional and may carry relay or caller metadata
- `stream` indicates whether progress events are expected before completion

### `execution_progress`

```json
{
  "tool_name": "string",
  "progress": {
    "message": "string",
    "percentage": 50
  }
}
```

### `execution_result`

```json
{
  "tool_name": "string",
  "result": {},
  "is_error": false,
  "metadata": {}
}
```

### `execution_error`

```json
{
  "tool_name": "string",
  "code": "string",
  "message": "string",
  "details": {}
}
```

### `heartbeat`

```json
{
  "timestamp": "RFC3339 string"
}
```

### `shutdown` / `disconnect_notice`

```json
{
  "reason": "string"
}
```

## 11.2 Execution correlation

Each execution request must include a unique request/execution ID so that:

- concurrent tool calls are supported
- progress/result/error events can be matched correctly

## 11.3 Validation

The relay must validate:

- required fields
- schema shape
- duplicate IDs where relevant
- tool name conflicts
- malformed executor messages

## 11.4 Idempotency expectations

TEP should define which operations are idempotent, especially:

- executor registration retry
- tool registration retry
- deregistration retry

## 11.5 Versioning

TEP should include an explicit protocol version so the relay and Tool Executor can negotiate compatibility.

## 11.6 Recommended TEP deployment model

For the primary Neovim integration use case:

- Neovim acts as the Tool Executor
- Neovim may communicate with a long-lived host relay over `stdio`
- the host relay should remain alive for the duration of the Neovim session
- Neovim may register, update, and deregister tools dynamically throughout that session

---

## 12. Relay Link Protocol (RLP) Requirements

This section defines required message categories, not a final wire encoding.

## 12.1 Message categories

RLP must support at least:

1. `hello` or `handshake`
2. `bind_session`
3. `tool_snapshot`
4. `tool_added`
5. `tool_removed`
6. `tool_updated`
7. `resource_snapshot`
8. `resource_added`
9. `resource_removed`
10. `resource_updated`
11. `prompt_snapshot`
12. `prompt_added`
13. `prompt_removed`
14. `prompt_updated`
15. `read_resource`
16. `resource_result`
17. `get_prompt`
18. `prompt_result`
19. `execute_tool`
20. `execution_progress`
21. `execution_result`
22. `execution_error`
23. `heartbeat`
24. `disconnect_notice`

## 12.1.1 RLP v1 envelope

RLP v1 messages must use a common JSON envelope with these top-level fields:

- `protocol`: literal string `rlp`
- `version`: protocol version string, initially `1.0`
- `message_type`: message kind
- `message_id`: unique ID for this message
- `relay_session_id`: host-served relay session identifier
- `source_relay_id`: sender relay instance identifier
- `target_relay_id`: optional intended receiver identifier
- `request_id`: present on request/response pairs when applicable
- `execution_id`: present on tool execution flows when applicable
- `payload`: message-specific object payload

Rules:

- every RLP message must include `protocol`, `version`, `message_type`, `message_id`, and `payload`
- `relay_session_id` is required after session binding and should be included in bind-related messages as soon as known
- `execution_id` is required for execution-related flows

## 12.1.2 RLP message classes

RLP v1 messages fall into three classes:

- **request**
- **response**
- **event**

Required classification:

- `hello` / `handshake`: request/response
- `bind_session`: request/response
- `tool_snapshot`: event
- `tool_added`: event
- `tool_removed`: event
- `tool_updated`: event
- `resource_snapshot`: event
- `resource_added`: event
- `resource_removed`: event
- `resource_updated`: event
- `prompt_snapshot`: event
- `prompt_added`: event
- `prompt_removed`: event
- `prompt_updated`: event
- `read_resource`: request
- `resource_result`: response
- `get_prompt`: request
- `prompt_result`: response
- `execute_tool`: request
- `execution_progress`: event
- `execution_result`: response or terminal event correlated by `execution_id`
- `execution_error`: response or terminal event correlated by `execution_id`
- `heartbeat`: event
- `disconnect_notice`: event

## 12.1.3 RLP success and error payloads

For request/response flows, RLP v1 must standardize:

- success responses with `payload.status: "ok"`
- error responses with `payload.status: "error"`

Error payloads must include:

- `code`: machine-readable error code
- `message`: human-readable error description
- optional `details`: structured object

## 12.1.4 RLP v1 payload schemas

The following payload structures are required in RLP v1.

### `hello` / `handshake`

```json
{
  "relay_id": "string",
  "role": "host|client",
  "capabilities": {
    "tool_sync": true,
    "tool_execution": true
  },
  "metadata": {}
}
```

### `bind_session`

```json
{
  "relay_session_id": "string",
  "session_token": "string",
  "client_instance_id": "string"
}
```

Rules:

- `relay_session_id` is required
- `session_token` is optional unless the host requires it
- `client_instance_id` is required

### `tool_snapshot`

```json
{
  "registry_revision": 12,
  "tools": [
    {
      "name": "string",
      "title": "string",
      "description": "string",
      "input_schema": {},
      "output_schema": {},
      "metadata": {}
    }
  ],
  "resources": [],
  "prompts": []
}
```

Rules:

- `registry_revision` is required
- `tools` is required and may be empty
- `resources` and `prompts` are included so RLP can support MCP core primitives beyond tools in v1

### `resource_snapshot`

```json
{
  "registry_revision": 12,
  "resources": [
    {
      "uri": "string",
      "name": "string",
      "description": "string",
      "mime_type": "string",
      "metadata": {}
    }
  ]
}
```

### `resource_added` / `resource_updated`

```json
{
  "registry_revision": 13,
  "resource": {
    "uri": "string",
    "name": "string",
    "description": "string",
    "mime_type": "string",
    "metadata": {}
  }
}
```

### `resource_removed`

```json
{
  "registry_revision": 14,
  "uri": "string"
}
```

### `prompt_snapshot`

```json
{
  "registry_revision": 12,
  "prompts": [
    {
      "name": "string",
      "description": "string",
      "arguments": [],
      "metadata": {}
    }
  ]
}
```

### `prompt_added` / `prompt_updated`

```json
{
  "registry_revision": 13,
  "prompt": {
    "name": "string",
    "description": "string",
    "arguments": [],
    "metadata": {}
  }
}
```

### `prompt_removed`

```json
{
  "registry_revision": 14,
  "name": "string"
}
```

### `read_resource`

```json
{
  "uri": "string",
  "arguments": {},
  "context": {}
}
```

### `resource_result`

```json
{
  "uri": "string",
  "contents": [],
  "metadata": {}
}
```

### `get_prompt`

```json
{
  "name": "string",
  "arguments": {},
  "context": {}
}
```

### `prompt_result`

```json
{
  "name": "string",
  "messages": [],
  "metadata": {}
}
```

### `tool_added` / `tool_updated`

```json
{
  "registry_revision": 13,
  "tool": {
    "name": "string",
    "title": "string",
    "description": "string",
    "input_schema": {},
    "output_schema": {},
    "metadata": {}
  }
}
```

### `tool_removed`

```json
{
  "registry_revision": 14,
  "tool_name": "string"
}
```

### `execute_tool`

```json
{
  "tool_name": "string",
  "arguments": {},
  "context": {},
  "stream": false
}
```

### `execution_progress`

```json
{
  "tool_name": "string",
  "progress": {
    "message": "string",
    "percentage": 50
  }
}
```

### `execution_result`

```json
{
  "tool_name": "string",
  "result": {},
  "is_error": false,
  "metadata": {}
}
```

### `execution_error`

```json
{
  "tool_name": "string",
  "code": "string",
  "message": "string",
  "details": {}
}
```

### `heartbeat`

```json
{
  "timestamp": "RFC3339 string"
}
```

### `disconnect_notice`

```json
{
  "reason": "string"
}
```

## 12.2 RLP roles

RLP defines two roles:

- **host relay**
- **client relay**

The host relay must be able to serve multiple client relay connections.

The client relay must connect to exactly one host relay per MCP session unless explicitly configured otherwise in a future version.

## 12.3 Tool state model

The host relay is the source of truth for:

- active tool set
- tool metadata
- tool availability

The client relay maintains a mirrored view of that state for presentation to the MCP client.

## 12.4 Session binding

RLP should support explicit session identity so that a client relay can bind to the intended host relay session.

Recommended model:

- the host relay publishes a per-session local endpoint
- the client relay is configured with that endpoint
- optional session identifiers or tokens may be used to harden pairing

Binding payload requirements:

- the client relay must provide the intended `relay_session_id`
- the host relay must respond with accept/reject semantics
- if the host requires a secret token, the bind request must include it in payload
- on bind success, the host relay must immediately send a full `tool_snapshot`

## 12.5 Versioning

RLP should include an explicit protocol version so client and host relays can negotiate compatibility.

## 12.6 Reconnect and resynchronization

RLP v1 must prefer correctness over partial replay.

Required reconnect behavior:

- if the RLP connection drops, the client relay must treat its mirrored registry as stale
- the client relay must reject new tool executions until resynchronization succeeds
- after reconnect and successful bind, the host relay must send a complete fresh `tool_snapshot`
- the client relay must rebuild mirrored state from that snapshot before serving new MCP tool executions

Versioning of tool state:

- the host relay should maintain a monotonically increasing registry revision number
- `tool_snapshot` should include the current revision
- incremental tool events should include the resulting revision after the change
- if a client relay detects a revision gap, it must request or wait for a fresh full snapshot rather than trying to guess missed updates

---

## 12. Wire Format

The protocol wire format should be consistent across transports where practical.

Recommended initial approach:

- use JSON messages for MCP, TEP, and RLP
- preserve a clean separation between:
  - message envelope / framing
  - protocol payload

### Requirement

Framing and delivery concerns belong to the transport adapter, not the protocol layer.

### v1 framing rules

The v1 implementation must use these concrete framing rules:

- stdio: UTF-8 newline-delimited JSON, one complete JSON object per line
- TCP for TEP/RLP: UTF-8 newline-delimited JSON, one complete JSON object per line
- HTTP for MCP/TEP: one JSON message per HTTP request body unless a documented streaming mode is explicitly enabled

Additional requirements:

- all JSON text must be UTF-8 encoded
- a single message must fit on one logical frame/unit for its transport
- the implementation must define a configurable maximum message size
- oversized or malformed frames must be rejected with a clear error and logged
- log output must never be written to stdout when stdout is carrying protocol traffic

Examples:

- newline-delimited JSON over stdio or TCP
- HTTP POST body carrying a single JSON message
- streaming JSON messages over an HTTP stream

The exact framing can vary by transport, but the logical message model must remain stable.

---

## 13. Configuration

The relay must be configurable without code changes.

The relay configuration format must be YAML.

## 13.1 Configuration domains

Configuration should cover:

- relay operating role
- MCP-side transport type and settings
- executor-side transport type and settings
- relay-link transport type and settings
- logging
- timeouts
- buffer/message size limits
- retry/reconnect policy
- tool namespace policy
- security restrictions

## 13.1.1 Role-specific configuration validation

Configuration validation must enforce these role rules:

- `role: direct` requires `mcp` and `executor`
- `role: host` requires `executor` and `relay_link`
- `role: client` requires `mcp` and `relay_link`

Invalid combinations must fail startup with a clear configuration error.

Recommended v1 restrictions:

- `role: direct` should reject `relay_link`
- `role: host` should reject `mcp`
- `role: client` should reject `executor`

Protocol-specific transport validation must also be enforced:

- `relay_link.transport` must be `stdio` or `tcp`
- `http` must be rejected for RLP in v1

## 13.2 Configuration sources and precedence

The relay must support exactly the following configuration input mechanisms:

1. YAML file path passed by command line argument
2. YAML string passed by command line argument
3. YAML file path passed through `NAIA_RELAY_CONFIG_FILE`
4. YAML string passed through `NAIA_RELAY_CONFIG_YAML`

These sources are mutually exclusive at the point of use.

### Precedence

Command line arguments take priority over environment variables.

Recommended precedence order:

1. CLI YAML file path
2. CLI YAML string
3. `NAIA_RELAY_CONFIG_FILE`
4. `NAIA_RELAY_CONFIG_YAML`

### Conflict rules

The relay must fail fast with a clear configuration error if:

- both CLI YAML file path and CLI YAML string are provided
- both `NAIA_RELAY_CONFIG_FILE` and `NAIA_RELAY_CONFIG_YAML` are set
- a CLI configuration source is provided and it conflicts with another CLI configuration source

If a CLI source is provided, environment variables must not silently override it.

If no supported configuration source is provided, startup must fail with a clear error.

## 13.3 Example conceptual configuration

```yaml
role: client

mcp:
  transport: stdio

relay_link:
  transport: tcp
  host: 127.0.0.1
  port: 9001

relay:
  request_timeout_seconds: 60
  reject_duplicate_tool_names: true
  log_level: info
```

This example is illustrative only, but YAML is the required configuration format.

Example host relay configuration:

```yaml
role: host

executor:
  transport: stdio

relay_link:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 9001
```

## 13.4 Suggested command line interface

The exact CLI syntax may evolve, but it should support concepts equivalent to:

- `naia-relay --config-file /path/to/config.yaml`
- `naia-relay --config-yaml "<yaml string>"`

The two CLI forms must be mutually exclusive.

## 13.5 Configuration loading behavior

Configuration loading should follow this sequence:

1. inspect CLI arguments
2. if a CLI config source is present, validate exclusivity and load it
3. otherwise inspect environment variables
4. if an environment config source is present, validate exclusivity and load it
5. parse YAML
6. validate the resulting configuration schema
7. start the relay only if validation succeeds

---

## 14. Concurrency and Ordering

The relay must support concurrent tool executions.

### Requirements

- multiple in-flight MCP requests may exist at once
- multiple executor operations may exist at once
- correlation IDs must uniquely bind responses to requests
- the relay must not confuse results across concurrent executions

### Ordering

Ordering guarantees should be minimal and explicit:

- request/response correlation is required
- global message ordering across unrelated requests is not required
- per-request event ordering should be preserved where meaningful

Recommended implementation model: Python `asyncio`.

---

## 15. Timeouts, Cancellation, and Backpressure

## 15.1 Timeouts

The relay should support configurable timeouts for:

- connection establishment
- initialization/registration
- tool execution
- heartbeat/liveness

## 15.2 Cancellation

If MCP supports cancellation semantics for applicable operations, the relay should propagate cancellation to the Tool Executor where possible.

## 15.3 Backpressure

The relay should define limits for:

- maximum in-flight requests
- maximum message size
- queue depth
- slow consumer behavior

When limits are exceeded, failures should be explicit and observable.

---

## 16. Error Handling

## 16.1 Error classes

The relay should distinguish:

- protocol errors
- transport errors
- validation errors
- execution/runtime errors
- timeout errors
- internal relay errors

## 16.2 Error mapping

The relay must map executor-side errors into MCP-compatible errors without losing useful detail.

Where possible include:

- machine-readable error code
- human-readable message
- correlated request ID
- optional structured details

## 16.3 Observability of failures

All significant failures should be logged with enough context to diagnose:

- side (`mcp` or `executor`)
- relay role (`direct`, `host`, or `client`)
- transport type
- session ID
- request/execution ID
- tool name, if applicable

---

## 17. Security Considerations

Initial security expectations:

- default TCP binding should prefer loopback
- HTTP exposure should be explicit, not accidental
- logs must avoid leaking sensitive tool arguments/results where configured
- malformed or oversized messages must be safely rejected

Future security features may include:

- authentication between relay and executor
- authentication between client and host relays
- TLS for HTTP/TCP
- allowlists for tools or transports
- per-tool authorization

---

## 18. Observability

The relay should provide:

- structured logs
- configurable log levels
- connection lifecycle logs
- request/execution tracing identifiers
- metrics hooks if added later

Useful metrics include:

- active connections
- registered tools count
- in-flight executions
- execution latency
- timeout count
- disconnect count
- attached client relay count per host relay

---

## 19. Extensibility Requirements

The implementation must be designed so that future additions are straightforward, including:

- new transports
- new executor message types
- multiple Tool Executors
- richer relay topologies
- tool namespacing/routing policies
- authentication and authorization
- richer streaming/progress semantics

Extensibility should be achieved through:

- clear Python interfaces / abstract base classes / protocols
- separation of protocol handlers from transport implementations
- internal message models independent of wire-specific details

---

## 20. Recommended Python Architecture

The implementation should be written in Python and should prefer an asynchronous architecture.

Recommended major modules:

- `naia_relay.core`
- `naia_relay.transports`
- `naia_relay.protocols.mcp`
- `naia_relay.protocols.executor`
- `naia_relay.protocols.rlp`
- `naia_relay.registry`
- `naia_relay.config`
- `naia_relay.logging`

Recommended implementation approach:

- `asyncio` for concurrency
- `pydantic` or equivalent for message/config validation
- clear adapter and protocol interfaces
- comprehensive integration tests per transport combination

---

## 21. Testing Requirements

The system should be tested at multiple levels.

## 21.1 Unit tests

Cover:

- message validation
- adapter behavior
- registry updates
- request correlation
- error mapping

## 21.2 Integration tests

Cover transport combinations such as:

- stdio ↔ stdio
- stdio ↔ tcp
- tcp ↔ stdio
- stdio ↔ http
- http ↔ stdio
- tcp ↔ http
- host relay over stdio TEP + client relay over tcp RLP
- host relay with multiple concurrent client relays

## 21.3 Protocol compliance tests

The relay should be tested for MCP compliance and for correct TEP and RLP behavior under malformed and normal traffic.

## 21.4 Failure scenario tests

Cover:

- executor disconnect during execution
- MCP disconnect during execution
- host relay disconnect while client relay is active
- client relay disconnect while host relay remains active
- malformed messages
- timeout handling
- duplicate tool registration
- reconnect and re-registration

---

## 22. Open Design Decisions

The following items should be finalized during detailed design:

1. Whether multiple Tool Executors are supported in v1
2. Whether tool registration is fully dynamic only or also supports static bootstrap definitions
3. Whether results/progress streams require a unified internal event model

---

## 23. Minimum Viable Product Scope

The MVP should include:

- Python implementation
- pluggable transport adapter system
- stdio adapter
- loopback TCP adapter
- HTTP adapter
- relay operating roles: direct, host, and client
- MCP-facing relay behavior sufficient for compliant tool discovery and invocation
- TEP executor registration and tool execution flow
- RLP host/client relay bridging over stdio or loopback TCP
- dynamic tool registry
- request correlation and timeout handling
- structured logging

---

## 24. Summary

`naia-relay` is a Python-based, transport-agnostic MCP relay that bridges MCP clients such as Codex to external Tool Executors through a custom executor protocol, and may also bridge through another relay instance using a dedicated relay-link protocol.

Its defining characteristics are:

- bidirectional communication
- independent transport choice on each side
- strict separation of transport and protocol concerns
- full MCP behavior on the agent-facing side
- dynamic tool registration and execution on the executor-facing side
- support for long-lived host relays and short-lived client relays
- architecture designed for future transports and capabilities

The central architectural rule is:

> **Protocols define meaning. Transports only define delivery.**
