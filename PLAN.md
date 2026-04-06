# naia-relay Implementation Plan

This implementation plan is based on and should be read alongside `SPEC.md`. If there is any conflict, `SPEC.md` is the source of truth for system behavior and scope.

This plan breaks the full implementation into phases that are small enough for an AI agent to execute safely while still following the system's logical build order.

## Baseline implementation choices

These choices should be treated as the default build target unless a later phase explicitly changes them.

### Python version

- [ ] Target Python `3.12` as the primary runtime version
- [x] Keep the code compatible with Python `3.11+` unless a dependency forces a narrower range

### Recommended Python modules and libraries

Core runtime:

- [x] `asyncio` for concurrency and task orchestration
- [x] `typing` / `dataclasses` or `pydantic` models for typed internal structures
- [x] `json` for protocol encoding/decoding
- [x] `logging` for structured log integration
- [x] `uuid` for message/session/request identifiers
- [x] `pathlib` for filesystem-safe path handling
- [x] `argparse` or `typer` for the CLI

Recommended third-party dependencies:

- [x] `pydantic` for config and protocol validation
- [x] `PyYAML` for YAML parsing
- [ ] an MCP Python SDK or equivalent MCP implementation library chosen during Phase 7
- [x] an async HTTP library such as `aiohttp` or `httpx` + an ASGI/HTTP server stack for HTTP transport
- [x] `pytest` for tests
- [x] `pytest-asyncio` for async test coverage

Optional but recommended developer tooling:

- [x] `ruff` for linting and formatting
- [x] `mypy` for static type checking

### Recommended project folder structure

The implementation should converge on a structure close to:

```text
naia-relay/
├── SPEC.md
├── PLAN.md
├── pyproject.toml
├── README.md
├── src/
│   └── naia_relay/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config/
│       ├── core/
│       ├── transports/
│       ├── protocols/
│       │   ├── mcp/
│       │   ├── tep/
│       │   └── rlp/
│       ├── registry/
│       ├── runtime/
│       ├── logging/
│       └── errors/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── examples/
    ├── direct/
    ├── host/
    └── client/
```

Structure rules:

- [x] Use a `src/` layout
- [x] Keep protocol handlers separate from transport adapters
- [x] Keep config models separate from runtime wiring
- [x] Keep unit, integration, and end-to-end tests in separate directories
- [x] Put runnable example YAML configs under `examples/`

### Global installation and executable strategy

The user should be able to install a globally invokable `naia-relay` executable.

Recommended packaging outcome:

- [x] Publish a console script entrypoint named `naia-relay`
- [x] Ensure `pip install .` provides the `naia-relay` command in the active environment
- [ ] Ensure `pipx install .` works for isolated global-style installation during development
- [x] Ensure editable install mode `pip install -e .` works for local iteration

Recommended user installation guidance to document later:

```bash
# isolated global-style install
pipx install .

# or install into the current environment
pip install .

# or local editable development install
pip install -e ".[dev]"
```

Packaging requirements:

- [x] `pyproject.toml` defines the console script entrypoint
- [x] optional dependency groups exist for development tooling
- [x] the install path does not require users to run the package as `python -m naia_relay`

Execution rules for this plan:

- Complete phases in order unless a later phase explicitly says it can begin earlier.
- Do not start a new phase until all tasks, tests, and definition-of-done checkboxes in the current phase are complete.
- Keep commits scoped to a single task or a small cluster of tightly related tasks.
- Prefer vertical slices that leave the repo in a runnable, testable state after each phase.

---

## Phase 0 — Repository bootstrap and engineering scaffolding

Goal: create the Python project skeleton, base tooling, and test harness so all later phases land into a stable structure.

### Tasks

- [x] Create the Python package layout for `naia_relay`
- [x] Add packaging metadata and dependency management configuration
- [x] Add a CLI entrypoint for `naia-relay`
- [x] Add a test runner configuration
- [x] Add linting and formatting configuration
- [x] Add a minimal logging setup usable from the CLI
- [x] Add base exception types and shared utility modules
- [x] Add CI-ready test command(s) documented in the repo

### Test requirements

- [x] Project installs in a fresh environment
- [x] CLI entrypoint runs and exits successfully with `--help`
- [x] Test runner executes at least one placeholder smoke test
- [x] Lint and formatting commands run successfully on the initial scaffold

### Definition of done

- [x] Repo contains a clean Python application skeleton for the relay
- [x] A developer or agent can run tests locally with one documented command
- [x] Future phases can add modules without restructuring the project

---

## Phase 1 — Configuration system and role validation

Goal: implement YAML-based configuration loading, precedence rules, schema validation, and role-specific validation.

### Tasks

- [x] Implement config loading from `--config-file`
- [x] Implement config loading from `--config-yaml`
- [x] Implement config loading from `NAIA_RELAY_CONFIG_FILE`
- [x] Implement config loading from `NAIA_RELAY_CONFIG_YAML`
- [x] Enforce mutual exclusivity between file-path and inline-YAML sources
- [x] Enforce CLI-over-environment precedence
- [x] Fail fast when no supported config source is provided
- [x] Define typed config models for `direct`, `host`, and `client` roles
- [x] Implement role-specific validation for required and forbidden sections
- [x] Enforce protocol-specific transport restrictions, especially RLP `stdio|tcp` only
- [x] Add config normalization for transport defaults, host defaults, and timeout defaults
- [x] Add human-readable configuration error messages

### Test requirements

- [x] CLI file config loads successfully
- [x] CLI YAML string loads successfully
- [x] Environment file config loads successfully
- [x] Environment YAML string loads successfully
- [x] CLI source overrides environment source
- [x] CLI file plus CLI YAML string fails with clear error
- [x] Environment file plus environment YAML string fails with clear error
- [x] Missing config source fails with clear error
- [x] `role: direct` rejects missing `mcp` or `executor`
- [x] `role: host` rejects missing `executor` or `relay_link`
- [x] `role: client` rejects missing `mcp` or `relay_link`
- [x] RLP over HTTP is rejected

### Definition of done

- [x] Relay startup is fully driven by validated YAML config
- [x] Role and transport validation rules match the spec
- [x] Config failures are deterministic and easy to diagnose

---

## Phase 2 — Shared core models, registries, and runtime primitives

Goal: implement the transport-independent runtime foundation used by every protocol and relay role.

### Tasks

- [x] Define shared message model primitives for correlation IDs, session IDs, relay IDs, and revisions
- [x] Implement a session manager for MCP, TEP, and RLP session state
- [x] Implement a request tracker for in-flight request/response correlation
- [x] Implement an execution tracker for in-flight tool execution lifecycle
- [x] Implement a unified registry model for tools, resources, and prompts
- [x] Support authoritative and mirrored registry modes
- [x] Add registry revision tracking for bridged synchronization
- [x] Implement name/URI uniqueness validation rules
- [x] Add shared error model types for protocol, validation, transport, timeout, and runtime errors
- [x] Add serialization helpers shared across protocols

### Test requirements

- [x] Session IDs and correlation IDs are generated and tracked correctly
- [x] In-flight request correlation works for concurrent requests
- [x] Tool registration updates authoritative registry state correctly
- [x] Resource registration updates authoritative registry state correctly
- [x] Prompt registration updates authoritative registry state correctly
- [x] Mirrored registry rebuild from snapshot works correctly
- [x] Duplicate tool names are rejected
- [x] Duplicate resource URIs are rejected
- [x] Duplicate prompt names are rejected
- [x] Registry revision increments correctly after each mutation

### Definition of done

- [x] Core runtime state exists independently of transports and protocol handlers
- [x] The registry model supports tools, resources, and prompts
- [x] Later protocol layers can rely on stable shared primitives

---

## Phase 3 — Transport adapter framework and stdio/tcp adapters

Goal: implement the common transport adapter interface and the v1 transports that all phases depend on.

### Tasks

- [x] Define the internal transport adapter interface
- [x] Implement a framing layer for UTF-8 newline-delimited JSON
- [x] Implement the stdio adapter
- [x] Ensure stdout is reserved for protocol traffic and logs go elsewhere
- [x] Implement the TCP adapter with loopback-safe defaults
- [x] Implement connection lifecycle hooks for open, close, and failure states
- [x] Implement configurable max message size enforcement
- [x] Implement malformed frame rejection behavior
- [x] Expose transport connection metadata to higher layers

### Test requirements

- [x] stdio adapter can send and receive framed JSON messages
- [x] TCP adapter can send and receive framed JSON messages
- [x] Oversized frames are rejected cleanly
- [x] Malformed JSON frames are rejected cleanly
- [x] stdio logging does not corrupt stdout protocol traffic
- [x] TCP adapter handles peer disconnects without crashing the process

### Definition of done

- [x] A transport-agnostic protocol handler can run on top of stdio or TCP
- [x] v1 framing behavior matches the spec exactly
- [x] Adapter failures surface as structured errors

---

## Phase 4 — HTTP transport adapter

Goal: implement the conservative v1 HTTP transport for MCP and TEP.

### Tasks

- [x] Implement an HTTP server/client transport abstraction as needed by relay role
- [x] Support one JSON message per request body
- [x] Support one JSON message per response body for non-streaming exchanges
- [x] Add optional streaming response support if required by selected MCP/TEP flows
- [x] Map HTTP connection failures and timeouts into transport errors
- [x] Add authorization hooks/config placeholders for MCP-over-HTTP
- [x] Explicitly block HTTP configuration for RLP

### Test requirements

- [x] MCP-over-HTTP request/response flow works for a non-streaming operation
- [x] TEP-over-HTTP request/response flow works for a non-streaming operation
- [x] Invalid HTTP payloads fail cleanly
- [x] HTTP timeout behavior is surfaced correctly
- [x] RLP configured with HTTP fails validation

### Definition of done

- [x] HTTP works as a supported v1 transport for MCP and TEP
- [x] HTTP behavior remains transport-only and does not alter protocol semantics
- [x] The implementation preserves correlation and error handling over HTTP

---

## Phase 5 — TEP protocol implementation

Goal: implement the full v1 Tool Executor Protocol, including tools, resources, prompts, reads, prompt retrieval, execution, progress, and lifecycle messages.

### Tasks

- [x] Implement TEP envelope parsing and validation
- [x] Implement TEP message classification: request, response, event
- [x] Implement `register_executor`
- [x] Implement `register_tools`
- [x] Implement `deregister_tools`
- [x] Implement `register_resources`
- [x] Implement `deregister_resources`
- [x] Implement `read_resource`
- [x] Implement `resource_result`
- [x] Implement `register_prompts`
- [x] Implement `deregister_prompts`
- [x] Implement `get_prompt`
- [x] Implement `prompt_result`
- [x] Implement `execute_tool`
- [x] Implement `execution_progress`
- [x] Implement `execution_result`
- [x] Implement `execution_error`
- [x] Implement `heartbeat`
- [x] Implement `shutdown` / `disconnect_notice`
- [x] Map TEP operations into authoritative registry mutations and executor actions
- [x] Enforce TEP validation and structured error responses
- [x] Implement TEP protocol version checks

### Test requirements

- [x] Valid TEP envelope is accepted
- [x] Invalid TEP envelope is rejected
- [x] Executor registration succeeds
- [x] Tool registration and deregistration succeed
- [x] Resource registration and deregistration succeed
- [x] Prompt registration and deregistration succeed
- [x] Resource read request/response succeeds
- [x] Prompt retrieval request/response succeeds
- [x] Tool execution request/progress/result succeeds
- [x] Tool execution error is returned in correct structure
- [x] Duplicate registrations fail as expected
- [x] Unsupported version fails cleanly
- [x] Heartbeat handling works
- [x] Disconnect notice updates executor availability state correctly

### Definition of done

- [x] Relay can fully communicate with a Tool Executor using TEP v1
- [x] TEP-backed tools, resources, and prompts are represented in authoritative registry state
- [x] Execution and non-execution flows behave correctly under concurrency

---

## Phase 6 — RLP protocol implementation

Goal: implement the full v1 Relay Link Protocol for host/client relay bridging and mirrored registry synchronization.

### Tasks

- [x] Implement RLP envelope parsing and validation
- [x] Implement RLP message classification: request, response, event
- [x] Implement `hello` / `handshake`
- [x] Implement `bind_session`
- [x] Implement session/token verification rules
- [x] Implement `tool_snapshot`
- [x] Implement `tool_added`
- [x] Implement `tool_removed`
- [x] Implement `tool_updated`
- [x] Implement `resource_snapshot`
- [x] Implement `resource_added`
- [x] Implement `resource_removed`
- [x] Implement `resource_updated`
- [x] Implement `prompt_snapshot`
- [x] Implement `prompt_added`
- [x] Implement `prompt_removed`
- [x] Implement `prompt_updated`
- [x] Implement `read_resource`
- [x] Implement `resource_result`
- [x] Implement `get_prompt`
- [x] Implement `prompt_result`
- [x] Implement `execute_tool`
- [x] Implement `execution_progress`
- [x] Implement `execution_result`
- [x] Implement `execution_error`
- [x] Implement `heartbeat`
- [x] Implement `disconnect_notice`
- [x] Implement initial full snapshot on successful bind
- [x] Implement incremental mirrored registry updates
- [x] Implement reconnect and resynchronization behavior
- [x] Implement revision-gap detection and forced resnapshot behavior
- [x] Implement support for one host relay serving multiple client relays
- [x] Implement RLP protocol version checks

### Test requirements

- [x] Valid RLP envelope is accepted
- [x] Invalid RLP envelope is rejected
- [x] Host/client handshake succeeds
- [x] Session bind succeeds for correct session ID
- [x] Session bind fails for unknown session ID
- [x] Session bind fails for invalid token when token is required
- [x] Initial `tool_snapshot` syncs correctly
- [x] Resource snapshot syncs correctly
- [x] Prompt snapshot syncs correctly
- [x] Incremental tool updates sync correctly
- [x] Incremental resource updates sync correctly
- [x] Incremental prompt updates sync correctly
- [x] Tool execution forwarding works end to end over RLP
- [x] Resource read forwarding works end to end over RLP
- [x] Prompt retrieval forwarding works end to end over RLP
- [x] RLP reconnect causes stale mirror invalidation
- [x] Fresh snapshot rebuild after reconnect works
- [x] Revision-gap detection triggers full resync
- [x] One host relay can serve multiple client relays concurrently

### Definition of done

- [x] Client relay can mirror host relay state reliably
- [x] RLP correctness favors full resync over ambiguous partial replay
- [x] Bridged execution, resource, and prompt flows work end to end

---

## Phase 7 — MCP server-side implementation

Goal: implement the MCP-facing behavior required by the spec, backed by direct or mirrored registry state.

### Tasks

- [x] Select the MCP SDK/library approach and wire it into the project
- [x] Implement JSON-RPC 2.0 handling required by MCP
- [x] Implement MCP lifecycle initialization and capability negotiation
- [x] Implement MCP tools/list and tools/call handling
- [x] Implement MCP resources/list and resources/read handling
- [x] Implement MCP prompts/list and prompts/get handling
- [x] Implement MCP notifications required by the selected SDK and supported features
- [x] Implement explicit unsupported-feature responses for sampling in v1
- [x] Implement explicit unsupported-feature responses for roots in v1 unless required by the SDK baseline
- [x] Implement explicit unsupported-feature responses for completions in v1 unless required by the SDK baseline
- [x] Implement logging utility support if required by the selected SDK or peer role
- [x] Map direct-mode MCP operations to TEP-backed authoritative state
- [x] Map client-relay MCP operations to RLP-backed mirrored/forwarded state
- [x] Ensure MCP-facing behavior hides underlying relay topology from the client

### Test requirements

- [x] MCP initialization succeeds with advertised capabilities
- [x] MCP tool listing reflects current registry state
- [x] MCP tool call succeeds in direct mode
- [x] MCP tool call succeeds in bridged mode
- [x] MCP resources/list succeeds
- [x] MCP resources/read succeeds
- [x] MCP prompts/list succeeds
- [x] MCP prompts/get succeeds
- [x] Unsupported sampling request fails explicitly
- [x] Unsupported roots request fails explicitly if roots remain out of scope
- [x] Unsupported completions request fails explicitly if completions remain out of scope
- [x] Tool/resource/prompt changes are reflected in subsequent MCP discovery
- [x] MCP error mapping preserves useful structured details

### Definition of done

- [x] Relay appears as a valid MCP peer for supported v1 features
- [x] MCP behavior is consistent in direct and bridged topologies
- [x] Unsupported v1 MCP features fail explicitly and predictably

---

## Phase 8 — Relay role orchestration and runtime wiring

Goal: connect transports, protocols, registries, and runtime state into the three executable relay roles.

### Tasks

- [x] Implement direct relay wiring: MCP ↔ core ↔ TEP
- [x] Implement host relay wiring: TEP ↔ core ↔ RLP listener
- [x] Implement client relay wiring: MCP ↔ core ↔ RLP connector
- [x] Implement startup sequencing per role
- [x] Implement shutdown sequencing per role
- [x] Implement session creation and relay/executor identity propagation
- [x] Implement role-aware routing for tool execution, resource reads, and prompt retrieval
- [x] Implement mirrored-registry read-only protections in client relay
- [x] Implement clear operational logs for role, transport, and session identity
- [x] Add CLI startup path that launches the correct runtime from config

### Test requirements

- [x] Direct relay starts successfully with valid config
- [x] Host relay starts successfully with valid config
- [x] Client relay starts successfully with valid config
- [x] Direct relay routes tool execution correctly
- [x] Host relay accepts client relay connections correctly
- [x] Client relay binds to intended host relay session correctly
- [x] Client relay rejects operations while mirror is stale
- [x] Shutdown drains or closes in-flight work according to implementation policy

### Definition of done

- [x] All three runtime roles are executable from the CLI
- [x] Startup, routing, and shutdown behavior match the spec
- [x] The system can now run end-to-end in real topologies

---

## Phase 9 — Timeouts, retries, disconnects, and backpressure

Goal: add the resilience behavior required by the spec so the runtime handles failures safely and observably.

### Tasks

- [x] Implement connection-establishment timeouts
- [x] Implement initialization and registration timeouts
- [x] Implement tool execution timeouts
- [x] Implement heartbeat liveness timeouts
- [x] Implement retry/reconnect behavior where config permits it
- [x] Invalidate mirrored state on RLP disconnect
- [x] Reject new client-relay executions until resync completes
- [x] Implement backpressure limits for in-flight requests
- [x] Implement queue-depth limits
- [x] Implement slow-consumer handling behavior
- [x] Map transport and timeout failures into structured protocol errors

### Test requirements

- [x] Connection timeout is enforced
- [x] Registration timeout is enforced
- [x] Execution timeout is enforced
- [x] Heartbeat timeout is enforced
- [x] RLP reconnect path restores service after resync
- [x] Client relay rejects new execution requests while stale
- [x] Backpressure limit is enforced
- [x] Slow-consumer path does not corrupt protocol state

### Definition of done

- [x] Relay handles expected failure modes without undefined behavior
- [x] Timeout and reconnect behavior matches the spec
- [x] Overload behavior is explicit and test-covered

---

## Phase 10 — Observability, diagnostics, and operator ergonomics

Goal: make the relay debuggable and operable in real workflows.

### Tasks

- [x] Implement structured logging fields for role, protocol side, transport, session, and request/execution IDs
- [x] Add startup summaries showing active role and transports
- [x] Add clear error logs for malformed messages and validation failures
- [x] Add disconnect/reconnect lifecycle logs
- [x] Add optional metrics hooks or counters for key runtime events
- [x] Add attached-client count tracking on host relay
- [x] Add debug logging controls via configuration
- [x] Document expected operator-visible logs and failure signals

### Test requirements

- [x] Logs include role and session identity
- [x] Logs include request/execution correlation identifiers
- [x] Validation failures are visible in logs
- [x] Disconnect/reconnect events are visible in logs
- [x] Metrics/counters update for basic runtime activity if implemented

### Definition of done

- [x] Operators can understand what the relay is doing from logs alone
- [x] Failure diagnosis does not require ad hoc print debugging
- [x] Runtime diagnostics are good enough for iterative development and support

---

## Phase 11 — End-to-end integration matrix and conformance hardening

Goal: prove the whole system works across the transport and topology combinations promised by the spec.

### Tasks

- [x] Build direct-mode end-to-end integration fixtures
- [x] Build bridged-mode end-to-end integration fixtures
- [x] Add fixtures for tool, resource, and prompt registration
- [x] Add fixtures for execution, resource reads, and prompt retrieval
- [x] Add transport-matrix tests for stdio, TCP, and HTTP where supported
- [x] Add malformed-message conformance tests for MCP, TEP, and RLP
- [x] Add multi-client host-relay concurrency tests
- [x] Add reconnect/resnapshot integration tests
- [x] Add unsupported-MCP-feature behavior tests
- [x] Add regression tests for previously discovered bugs during development

### Test requirements

- [x] Direct: stdio MCP ↔ TCP TEP passes end to end
- [x] Direct: TCP MCP ↔ stdio TEP passes end to end
- [x] Direct: stdio MCP ↔ HTTP TEP passes end to end
- [x] Direct: HTTP MCP ↔ stdio TEP passes end to end
- [x] Bridged: stdio TEP host ↔ TCP RLP client ↔ stdio MCP passes end to end
- [x] Bridged: stdio TEP host ↔ stdio RLP client ↔ stdio MCP passes end to end if stdio RLP is implemented in v1
- [x] Host relay supports multiple concurrent client relays
- [x] Tool sync works end to end
- [x] Resource sync works end to end
- [x] Prompt sync works end to end
- [x] Tool execution works end to end
- [x] Resource read works end to end
- [x] Prompt retrieval works end to end
- [x] Disconnect/reconnect and resnapshot work end to end
- [x] Direct dual-stdio configuration is rejected explicitly

### Definition of done

- [x] The advertised v1 transport and topology matrix is test-backed
- [x] End-to-end tests cover tools, resources, and prompts
- [x] The implementation is ready for real-world trial use

---

## Phase 12 — Final hardening, documentation, and release readiness

Goal: prepare the repo for sustained iteration after the first implementation lands.

### Tasks

- [x] Write developer documentation for relay roles and local topologies
- [x] Write operator documentation for config sources and transport choices
- [x] Add example configs for direct, host, and client roles
- [x] Add example configs for Neovim host relay and Codex client relay
- [x] Document unsupported v1 features and expected errors
- [x] Review the codebase for TODOs or shortcuts left from earlier phases
- [x] Remove or gate debug-only code paths
- [x] Perform a final dependency and packaging review

### Test requirements

- [x] All automated tests pass in one clean run
- [x] Example configs are syntactically valid
- [x] Documentation matches actual CLI and config behavior
- [x] A fresh developer can run the relay locally using the docs

### Definition of done

- [x] Repo is in a handoff-ready state for future implementation or usage
- [x] Docs, examples, and code behavior match
- [x] The initial implementation of the full spec is complete enough for iterative adoption

---

## Suggested milestone checkpoints

- [x] Milestone A complete: Phases 0–3
- [x] Milestone B complete: Phases 4–6
- [x] Milestone C complete: Phases 7–9
- [x] Milestone D complete: Phases 10–12

---

## Final completion criteria

- [x] All phases are complete
- [x] All phase test checklists are complete
- [x] All definitions of done are complete
- [x] The implementation covers the full current `SPEC.md`
