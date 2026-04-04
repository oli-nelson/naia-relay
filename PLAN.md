# naia-relay Implementation Plan

This implementation plan is based on and should be read alongside `SPEC.md`. If there is any conflict, `SPEC.md` is the source of truth for system behavior and scope.

This plan breaks the full implementation into phases that are small enough for an AI agent to execute safely while still following the system's logical build order.

## Baseline implementation choices

These choices should be treated as the default build target unless a later phase explicitly changes them.

### Python version

- [ ] Target Python `3.12` as the primary runtime version
- [ ] Keep the code compatible with Python `3.11+` unless a dependency forces a narrower range

### Recommended Python modules and libraries

Core runtime:

- [ ] `asyncio` for concurrency and task orchestration
- [ ] `typing` / `dataclasses` or `pydantic` models for typed internal structures
- [ ] `json` for protocol encoding/decoding
- [ ] `logging` for structured log integration
- [ ] `uuid` for message/session/request identifiers
- [ ] `pathlib` for filesystem-safe path handling
- [ ] `argparse` or `typer` for the CLI

Recommended third-party dependencies:

- [ ] `pydantic` for config and protocol validation
- [ ] `PyYAML` for YAML parsing
- [ ] an MCP Python SDK or equivalent MCP implementation library chosen during Phase 7
- [ ] an async HTTP library such as `aiohttp` or `httpx` + an ASGI/HTTP server stack for HTTP transport
- [ ] `pytest` for tests
- [ ] `pytest-asyncio` for async test coverage

Optional but recommended developer tooling:

- [ ] `ruff` for linting and formatting
- [ ] `mypy` for static type checking

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

- [ ] Use a `src/` layout
- [ ] Keep protocol handlers separate from transport adapters
- [ ] Keep config models separate from runtime wiring
- [ ] Keep unit, integration, and end-to-end tests in separate directories
- [ ] Put runnable example YAML configs under `examples/`

### Global installation and executable strategy

The user should be able to install a globally invokable `naia-relay` executable.

Recommended packaging outcome:

- [ ] Publish a console script entrypoint named `naia-relay`
- [ ] Ensure `pip install .` provides the `naia-relay` command in the active environment
- [ ] Ensure `pipx install .` works for isolated global-style installation during development
- [ ] Ensure editable install mode `pip install -e .` works for local iteration

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

- [ ] `pyproject.toml` defines the console script entrypoint
- [ ] optional dependency groups exist for development tooling
- [ ] the install path does not require users to run the package as `python -m naia_relay`

Execution rules for this plan:

- Complete phases in order unless a later phase explicitly says it can begin earlier.
- Do not start a new phase until all tasks, tests, and definition-of-done checkboxes in the current phase are complete.
- Keep commits scoped to a single task or a small cluster of tightly related tasks.
- Prefer vertical slices that leave the repo in a runnable, testable state after each phase.

---

## Phase 0 — Repository bootstrap and engineering scaffolding

Goal: create the Python project skeleton, base tooling, and test harness so all later phases land into a stable structure.

### Tasks

- [ ] Create the Python package layout for `naia_relay`
- [ ] Add packaging metadata and dependency management configuration
- [ ] Add a CLI entrypoint for `naia-relay`
- [ ] Add a test runner configuration
- [ ] Add linting and formatting configuration
- [ ] Add a minimal logging setup usable from the CLI
- [ ] Add base exception types and shared utility modules
- [ ] Add CI-ready test command(s) documented in the repo

### Test requirements

- [ ] Project installs in a fresh environment
- [ ] CLI entrypoint runs and exits successfully with `--help`
- [ ] Test runner executes at least one placeholder smoke test
- [ ] Lint and formatting commands run successfully on the initial scaffold

### Definition of done

- [ ] Repo contains a clean Python application skeleton for the relay
- [ ] A developer or agent can run tests locally with one documented command
- [ ] Future phases can add modules without restructuring the project

---

## Phase 1 — Configuration system and role validation

Goal: implement YAML-based configuration loading, precedence rules, schema validation, and role-specific validation.

### Tasks

- [ ] Implement config loading from `--config-file`
- [ ] Implement config loading from `--config-yaml`
- [ ] Implement config loading from `NAIA_RELAY_CONFIG_FILE`
- [ ] Implement config loading from `NAIA_RELAY_CONFIG_YAML`
- [ ] Enforce mutual exclusivity between file-path and inline-YAML sources
- [ ] Enforce CLI-over-environment precedence
- [ ] Fail fast when no supported config source is provided
- [ ] Define typed config models for `direct`, `host`, and `client` roles
- [ ] Implement role-specific validation for required and forbidden sections
- [ ] Enforce protocol-specific transport restrictions, especially RLP `stdio|tcp` only
- [ ] Add config normalization for transport defaults, host defaults, and timeout defaults
- [ ] Add human-readable configuration error messages

### Test requirements

- [ ] CLI file config loads successfully
- [ ] CLI YAML string loads successfully
- [ ] Environment file config loads successfully
- [ ] Environment YAML string loads successfully
- [ ] CLI source overrides environment source
- [ ] CLI file plus CLI YAML string fails with clear error
- [ ] Environment file plus environment YAML string fails with clear error
- [ ] Missing config source fails with clear error
- [ ] `role: direct` rejects missing `mcp` or `executor`
- [ ] `role: host` rejects missing `executor` or `relay_link`
- [ ] `role: client` rejects missing `mcp` or `relay_link`
- [ ] RLP over HTTP is rejected

### Definition of done

- [ ] Relay startup is fully driven by validated YAML config
- [ ] Role and transport validation rules match the spec
- [ ] Config failures are deterministic and easy to diagnose

---

## Phase 2 — Shared core models, registries, and runtime primitives

Goal: implement the transport-independent runtime foundation used by every protocol and relay role.

### Tasks

- [ ] Define shared message model primitives for correlation IDs, session IDs, relay IDs, and revisions
- [ ] Implement a session manager for MCP, TEP, and RLP session state
- [ ] Implement a request tracker for in-flight request/response correlation
- [ ] Implement an execution tracker for in-flight tool execution lifecycle
- [ ] Implement a unified registry model for tools, resources, and prompts
- [ ] Support authoritative and mirrored registry modes
- [ ] Add registry revision tracking for bridged synchronization
- [ ] Implement name/URI uniqueness validation rules
- [ ] Add shared error model types for protocol, validation, transport, timeout, and runtime errors
- [ ] Add serialization helpers shared across protocols

### Test requirements

- [ ] Session IDs and correlation IDs are generated and tracked correctly
- [ ] In-flight request correlation works for concurrent requests
- [ ] Tool registration updates authoritative registry state correctly
- [ ] Resource registration updates authoritative registry state correctly
- [ ] Prompt registration updates authoritative registry state correctly
- [ ] Mirrored registry rebuild from snapshot works correctly
- [ ] Duplicate tool names are rejected
- [ ] Duplicate resource URIs are rejected
- [ ] Duplicate prompt names are rejected
- [ ] Registry revision increments correctly after each mutation

### Definition of done

- [ ] Core runtime state exists independently of transports and protocol handlers
- [ ] The registry model supports tools, resources, and prompts
- [ ] Later protocol layers can rely on stable shared primitives

---

## Phase 3 — Transport adapter framework and stdio/tcp adapters

Goal: implement the common transport adapter interface and the v1 transports that all phases depend on.

### Tasks

- [ ] Define the internal transport adapter interface
- [ ] Implement a framing layer for UTF-8 newline-delimited JSON
- [ ] Implement the stdio adapter
- [ ] Ensure stdout is reserved for protocol traffic and logs go elsewhere
- [ ] Implement the TCP adapter with loopback-safe defaults
- [ ] Implement connection lifecycle hooks for open, close, and failure states
- [ ] Implement configurable max message size enforcement
- [ ] Implement malformed frame rejection behavior
- [ ] Expose transport connection metadata to higher layers

### Test requirements

- [ ] stdio adapter can send and receive framed JSON messages
- [ ] TCP adapter can send and receive framed JSON messages
- [ ] Oversized frames are rejected cleanly
- [ ] Malformed JSON frames are rejected cleanly
- [ ] stdio logging does not corrupt stdout protocol traffic
- [ ] TCP adapter handles peer disconnects without crashing the process

### Definition of done

- [ ] A transport-agnostic protocol handler can run on top of stdio or TCP
- [ ] v1 framing behavior matches the spec exactly
- [ ] Adapter failures surface as structured errors

---

## Phase 4 — HTTP transport adapter

Goal: implement the conservative v1 HTTP transport for MCP and TEP.

### Tasks

- [ ] Implement an HTTP server/client transport abstraction as needed by relay role
- [ ] Support one JSON message per request body
- [ ] Support one JSON message per response body for non-streaming exchanges
- [ ] Add optional streaming response support if required by selected MCP/TEP flows
- [ ] Map HTTP connection failures and timeouts into transport errors
- [ ] Add authorization hooks/config placeholders for MCP-over-HTTP
- [ ] Explicitly block HTTP configuration for RLP

### Test requirements

- [ ] MCP-over-HTTP request/response flow works for a non-streaming operation
- [ ] TEP-over-HTTP request/response flow works for a non-streaming operation
- [ ] Invalid HTTP payloads fail cleanly
- [ ] HTTP timeout behavior is surfaced correctly
- [ ] RLP configured with HTTP fails validation

### Definition of done

- [ ] HTTP works as a supported v1 transport for MCP and TEP
- [ ] HTTP behavior remains transport-only and does not alter protocol semantics
- [ ] The implementation preserves correlation and error handling over HTTP

---

## Phase 5 — TEP protocol implementation

Goal: implement the full v1 Tool Executor Protocol, including tools, resources, prompts, reads, prompt retrieval, execution, progress, and lifecycle messages.

### Tasks

- [ ] Implement TEP envelope parsing and validation
- [ ] Implement TEP message classification: request, response, event
- [ ] Implement `register_executor`
- [ ] Implement `register_tools`
- [ ] Implement `deregister_tools`
- [ ] Implement `register_resources`
- [ ] Implement `deregister_resources`
- [ ] Implement `read_resource`
- [ ] Implement `resource_result`
- [ ] Implement `register_prompts`
- [ ] Implement `deregister_prompts`
- [ ] Implement `get_prompt`
- [ ] Implement `prompt_result`
- [ ] Implement `execute_tool`
- [ ] Implement `execution_progress`
- [ ] Implement `execution_result`
- [ ] Implement `execution_error`
- [ ] Implement `heartbeat`
- [ ] Implement `shutdown` / `disconnect_notice`
- [ ] Map TEP operations into authoritative registry mutations and executor actions
- [ ] Enforce TEP validation and structured error responses
- [ ] Implement TEP protocol version checks

### Test requirements

- [ ] Valid TEP envelope is accepted
- [ ] Invalid TEP envelope is rejected
- [ ] Executor registration succeeds
- [ ] Tool registration and deregistration succeed
- [ ] Resource registration and deregistration succeed
- [ ] Prompt registration and deregistration succeed
- [ ] Resource read request/response succeeds
- [ ] Prompt retrieval request/response succeeds
- [ ] Tool execution request/progress/result succeeds
- [ ] Tool execution error is returned in correct structure
- [ ] Duplicate registrations fail as expected
- [ ] Unsupported version fails cleanly
- [ ] Heartbeat handling works
- [ ] Disconnect notice updates executor availability state correctly

### Definition of done

- [ ] Relay can fully communicate with a Tool Executor using TEP v1
- [ ] TEP-backed tools, resources, and prompts are represented in authoritative registry state
- [ ] Execution and non-execution flows behave correctly under concurrency

---

## Phase 6 — RLP protocol implementation

Goal: implement the full v1 Relay Link Protocol for host/client relay bridging and mirrored registry synchronization.

### Tasks

- [ ] Implement RLP envelope parsing and validation
- [ ] Implement RLP message classification: request, response, event
- [ ] Implement `hello` / `handshake`
- [ ] Implement `bind_session`
- [ ] Implement session/token verification rules
- [ ] Implement `tool_snapshot`
- [ ] Implement `tool_added`
- [ ] Implement `tool_removed`
- [ ] Implement `tool_updated`
- [ ] Implement `resource_snapshot`
- [ ] Implement `resource_added`
- [ ] Implement `resource_removed`
- [ ] Implement `resource_updated`
- [ ] Implement `prompt_snapshot`
- [ ] Implement `prompt_added`
- [ ] Implement `prompt_removed`
- [ ] Implement `prompt_updated`
- [ ] Implement `read_resource`
- [ ] Implement `resource_result`
- [ ] Implement `get_prompt`
- [ ] Implement `prompt_result`
- [ ] Implement `execute_tool`
- [ ] Implement `execution_progress`
- [ ] Implement `execution_result`
- [ ] Implement `execution_error`
- [ ] Implement `heartbeat`
- [ ] Implement `disconnect_notice`
- [ ] Implement initial full snapshot on successful bind
- [ ] Implement incremental mirrored registry updates
- [ ] Implement reconnect and resynchronization behavior
- [ ] Implement revision-gap detection and forced resnapshot behavior
- [ ] Implement support for one host relay serving multiple client relays
- [ ] Implement RLP protocol version checks

### Test requirements

- [ ] Valid RLP envelope is accepted
- [ ] Invalid RLP envelope is rejected
- [ ] Host/client handshake succeeds
- [ ] Session bind succeeds for correct session ID
- [ ] Session bind fails for unknown session ID
- [ ] Session bind fails for invalid token when token is required
- [ ] Initial `tool_snapshot` syncs correctly
- [ ] Resource snapshot syncs correctly
- [ ] Prompt snapshot syncs correctly
- [ ] Incremental tool updates sync correctly
- [ ] Incremental resource updates sync correctly
- [ ] Incremental prompt updates sync correctly
- [ ] Tool execution forwarding works end to end over RLP
- [ ] Resource read forwarding works end to end over RLP
- [ ] Prompt retrieval forwarding works end to end over RLP
- [ ] RLP reconnect causes stale mirror invalidation
- [ ] Fresh snapshot rebuild after reconnect works
- [ ] Revision-gap detection triggers full resync
- [ ] One host relay can serve multiple client relays concurrently

### Definition of done

- [ ] Client relay can mirror host relay state reliably
- [ ] RLP correctness favors full resync over ambiguous partial replay
- [ ] Bridged execution, resource, and prompt flows work end to end

---

## Phase 7 — MCP server-side implementation

Goal: implement the MCP-facing behavior required by the spec, backed by direct or mirrored registry state.

### Tasks

- [ ] Select the MCP SDK/library approach and wire it into the project
- [ ] Implement JSON-RPC 2.0 handling required by MCP
- [ ] Implement MCP lifecycle initialization and capability negotiation
- [ ] Implement MCP tools/list and tools/call handling
- [ ] Implement MCP resources/list and resources/read handling
- [ ] Implement MCP prompts/list and prompts/get handling
- [ ] Implement MCP notifications required by the selected SDK and supported features
- [ ] Implement explicit unsupported-feature responses for sampling in v1
- [ ] Implement explicit unsupported-feature responses for roots in v1 unless required by the SDK baseline
- [ ] Implement explicit unsupported-feature responses for completions in v1 unless required by the SDK baseline
- [ ] Implement logging utility support if required by the selected SDK or peer role
- [ ] Map direct-mode MCP operations to TEP-backed authoritative state
- [ ] Map client-relay MCP operations to RLP-backed mirrored/forwarded state
- [ ] Ensure MCP-facing behavior hides underlying relay topology from the client

### Test requirements

- [ ] MCP initialization succeeds with advertised capabilities
- [ ] MCP tool listing reflects current registry state
- [ ] MCP tool call succeeds in direct mode
- [ ] MCP tool call succeeds in bridged mode
- [ ] MCP resources/list succeeds
- [ ] MCP resources/read succeeds
- [ ] MCP prompts/list succeeds
- [ ] MCP prompts/get succeeds
- [ ] Unsupported sampling request fails explicitly
- [ ] Unsupported roots request fails explicitly if roots remain out of scope
- [ ] Unsupported completions request fails explicitly if completions remain out of scope
- [ ] Tool/resource/prompt changes are reflected in subsequent MCP discovery
- [ ] MCP error mapping preserves useful structured details

### Definition of done

- [ ] Relay appears as a valid MCP peer for supported v1 features
- [ ] MCP behavior is consistent in direct and bridged topologies
- [ ] Unsupported v1 MCP features fail explicitly and predictably

---

## Phase 8 — Relay role orchestration and runtime wiring

Goal: connect transports, protocols, registries, and runtime state into the three executable relay roles.

### Tasks

- [ ] Implement direct relay wiring: MCP ↔ core ↔ TEP
- [ ] Implement host relay wiring: TEP ↔ core ↔ RLP listener
- [ ] Implement client relay wiring: MCP ↔ core ↔ RLP connector
- [ ] Implement startup sequencing per role
- [ ] Implement shutdown sequencing per role
- [ ] Implement session creation and relay/executor identity propagation
- [ ] Implement role-aware routing for tool execution, resource reads, and prompt retrieval
- [ ] Implement mirrored-registry read-only protections in client relay
- [ ] Implement clear operational logs for role, transport, and session identity
- [ ] Add CLI startup path that launches the correct runtime from config

### Test requirements

- [ ] Direct relay starts successfully with valid config
- [ ] Host relay starts successfully with valid config
- [ ] Client relay starts successfully with valid config
- [ ] Direct relay routes tool execution correctly
- [ ] Host relay accepts client relay connections correctly
- [ ] Client relay binds to intended host relay session correctly
- [ ] Client relay rejects operations while mirror is stale
- [ ] Shutdown drains or closes in-flight work according to implementation policy

### Definition of done

- [ ] All three runtime roles are executable from the CLI
- [ ] Startup, routing, and shutdown behavior match the spec
- [ ] The system can now run end-to-end in real topologies

---

## Phase 9 — Timeouts, retries, disconnects, and backpressure

Goal: add the resilience behavior required by the spec so the runtime handles failures safely and observably.

### Tasks

- [ ] Implement connection-establishment timeouts
- [ ] Implement initialization and registration timeouts
- [ ] Implement tool execution timeouts
- [ ] Implement heartbeat liveness timeouts
- [ ] Implement retry/reconnect behavior where config permits it
- [ ] Invalidate mirrored state on RLP disconnect
- [ ] Reject new client-relay executions until resync completes
- [ ] Implement backpressure limits for in-flight requests
- [ ] Implement queue-depth limits
- [ ] Implement slow-consumer handling behavior
- [ ] Map transport and timeout failures into structured protocol errors

### Test requirements

- [ ] Connection timeout is enforced
- [ ] Registration timeout is enforced
- [ ] Execution timeout is enforced
- [ ] Heartbeat timeout is enforced
- [ ] RLP reconnect path restores service after resync
- [ ] Client relay rejects new execution requests while stale
- [ ] Backpressure limit is enforced
- [ ] Slow-consumer path does not corrupt protocol state

### Definition of done

- [ ] Relay handles expected failure modes without undefined behavior
- [ ] Timeout and reconnect behavior matches the spec
- [ ] Overload behavior is explicit and test-covered

---

## Phase 10 — Observability, diagnostics, and operator ergonomics

Goal: make the relay debuggable and operable in real workflows.

### Tasks

- [ ] Implement structured logging fields for role, protocol side, transport, session, and request/execution IDs
- [ ] Add startup summaries showing active role and transports
- [ ] Add clear error logs for malformed messages and validation failures
- [ ] Add disconnect/reconnect lifecycle logs
- [ ] Add optional metrics hooks or counters for key runtime events
- [ ] Add attached-client count tracking on host relay
- [ ] Add debug logging controls via configuration
- [ ] Document expected operator-visible logs and failure signals

### Test requirements

- [ ] Logs include role and session identity
- [ ] Logs include request/execution correlation identifiers
- [ ] Validation failures are visible in logs
- [ ] Disconnect/reconnect events are visible in logs
- [ ] Metrics/counters update for basic runtime activity if implemented

### Definition of done

- [ ] Operators can understand what the relay is doing from logs alone
- [ ] Failure diagnosis does not require ad hoc print debugging
- [ ] Runtime diagnostics are good enough for iterative development and support

---

## Phase 11 — End-to-end integration matrix and conformance hardening

Goal: prove the whole system works across the transport and topology combinations promised by the spec.

### Tasks

- [ ] Build direct-mode end-to-end integration fixtures
- [ ] Build bridged-mode end-to-end integration fixtures
- [ ] Add fixtures for tool, resource, and prompt registration
- [ ] Add fixtures for execution, resource reads, and prompt retrieval
- [ ] Add transport-matrix tests for stdio, TCP, and HTTP where supported
- [ ] Add malformed-message conformance tests for MCP, TEP, and RLP
- [ ] Add multi-client host-relay concurrency tests
- [ ] Add reconnect/resnapshot integration tests
- [ ] Add unsupported-MCP-feature behavior tests
- [ ] Add regression tests for previously discovered bugs during development

### Test requirements

- [ ] Direct: stdio MCP ↔ stdio TEP passes end to end
- [ ] Direct: stdio MCP ↔ TCP TEP passes end to end
- [ ] Direct: TCP MCP ↔ stdio TEP passes end to end
- [ ] Direct: stdio MCP ↔ HTTP TEP passes end to end
- [ ] Direct: HTTP MCP ↔ stdio TEP passes end to end
- [ ] Bridged: stdio TEP host ↔ TCP RLP client ↔ stdio MCP passes end to end
- [ ] Bridged: stdio TEP host ↔ stdio RLP client ↔ stdio MCP passes end to end if stdio RLP is implemented in v1
- [ ] Host relay supports multiple concurrent client relays
- [ ] Tool sync works end to end
- [ ] Resource sync works end to end
- [ ] Prompt sync works end to end
- [ ] Tool execution works end to end
- [ ] Resource read works end to end
- [ ] Prompt retrieval works end to end
- [ ] Disconnect/reconnect and resnapshot work end to end

### Definition of done

- [ ] The advertised v1 transport and topology matrix is test-backed
- [ ] End-to-end tests cover tools, resources, and prompts
- [ ] The implementation is ready for real-world trial use

---

## Phase 12 — Final hardening, documentation, and release readiness

Goal: prepare the repo for sustained iteration after the first implementation lands.

### Tasks

- [ ] Write developer documentation for relay roles and local topologies
- [ ] Write operator documentation for config sources and transport choices
- [ ] Add example configs for direct, host, and client roles
- [ ] Add example configs for Neovim host relay and Codex client relay
- [ ] Document unsupported v1 features and expected errors
- [ ] Review the codebase for TODOs or shortcuts left from earlier phases
- [ ] Remove or gate debug-only code paths
- [ ] Perform a final dependency and packaging review

### Test requirements

- [ ] All automated tests pass in one clean run
- [ ] Example configs are syntactically valid
- [ ] Documentation matches actual CLI and config behavior
- [ ] A fresh developer can run the relay locally using the docs

### Definition of done

- [ ] Repo is in a handoff-ready state for future implementation or usage
- [ ] Docs, examples, and code behavior match
- [ ] The initial implementation of the full spec is complete enough for iterative adoption

---

## Suggested milestone checkpoints

- [ ] Milestone A complete: Phases 0–3
- [ ] Milestone B complete: Phases 4–6
- [ ] Milestone C complete: Phases 7–9
- [ ] Milestone D complete: Phases 10–12

---

## Final completion criteria

- [ ] All phases are complete
- [ ] All phase test checklists are complete
- [ ] All definitions of done are complete
- [ ] The implementation covers the full current `SPEC.md`
