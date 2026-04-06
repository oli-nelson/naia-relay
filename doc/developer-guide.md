# Developer Guide

This guide is for contributors working on the Python implementation of `naia-relay`.

## Project layout

```text
naia-relay/
├── SPEC.md
├── PLAN.md
├── doc/
├── examples/
├── src/naia_relay/
│   ├── cli.py
│   ├── config/
│   ├── core/
│   ├── errors/
│   ├── logging/
│   ├── protocols/
│   │   ├── mcp/
│   │   ├── rlp/
│   │   └── tep/
│   ├── registry/
│   ├── runtime/
│   └── transports/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## Relay roles

`naia-relay` has three executable roles:

- `direct`
  - MCP-facing side on one side
  - TEP-facing side on the other
- `host`
  - TEP-facing side toward a Tool Executor
  - RLP-facing side toward one or more downstream client relays
- `client`
  - MCP-facing side toward a tool-using agent
  - RLP-facing side toward a host relay

## Local topology models

### Direct mode

```text
MCP client <-> naia-relay <-> Tool Executor
```

Typical uses:

- Codex ↔ relay ↔ a single local tool executor
- standalone smoke tests

### Bridged mode

```text
Tool Executor <-> host relay <-> client relay <-> MCP client
```

Typical uses:

- Neovim owns a long-lived host relay
- one or more Codex sessions spawn short-lived client relays

## End-to-end request flow

### Direct tool execution

```text
MCP tools/call
  -> direct relay MCP handler
  -> direct relay executor-facing TEP request
  -> Tool Executor runs the tool
  -> TEP execution_result / execution_error
  -> MCP tool result
```

### Bridged tool execution

```text
MCP tools/call
  -> client relay
  -> RLP execute_tool
  -> host relay
  -> TEP execute_tool
  -> Tool Executor runs the tool
  -> TEP execution_result / execution_error
  -> host relay
  -> RLP response
  -> client relay
  -> MCP tool result
```

### Tool discovery

```text
Tool Executor register_tools
  -> host/direct relay authoritative registry
  -> RLP snapshot/update propagation when bridged
  -> MCP tools/list
```

## Runtime architecture

### Transport adapters

Transport adapters are intentionally separate from protocol semantics:

- `stdio`
- `tcp`
- `http` for MCP and TEP only

Adapters live under `src/naia_relay/transports/`.

Transport adapters are responsible for:

- framing
- byte transport
- connection lifecycle

Protocol handlers are responsible for:

- message validation
- payload semantics
- request/response behavior
- registry mutation and execution flow

### Protocol handlers

Handlers live under `src/naia_relay/protocols/`:

- `mcp` — JSON-RPC / MCP-facing behavior
- `tep` — Tool Executor Protocol
- `rlp` — Relay Link Protocol

### Shared state

Shared runtime state lives under:

- `core/` for ids, sessions, serialization, and request/execution tracking
- `registry/` for tools, resources, prompts, revisions, and stale mirrored state
- `runtime/` for role-specific orchestration

## Tests

The repository uses three layers of tests:

- `tests/unit/`
  - focused component tests
  - handler, config, registry, runtime, and observability coverage
- `tests/integration/`
  - transport-aware topology tests
  - direct and bridged end-to-end flows across supported transport combinations
- `tests/e2e/`
  - subprocess-level runtime loop coverage for MCP stdio and TEP stdio

## Developer workflow

Create a local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the full validation suite:

```bash
ruff check .
pytest
```

## Working conventions

- update `PLAN.md` checkboxes only when work is truly completed
- keep `SPEC.md` as the behavioral source of truth
- commit at clean phase or checkpoint boundaries
- prefer transport-agnostic behavior in protocol and registry code
- do not assume direct mode can use stdio on both sides simultaneously

## Local examples

See the `examples/` folder for:

- `examples/direct/config.yaml`
- `examples/host/config.yaml`
- `examples/client/config.yaml`
- `examples/neovim-host/config.yaml`
- `examples/codex-client/config.yaml`

See also:

- [integrations.md](integrations.md)
- [troubleshooting.md](troubleshooting.md)
- [../SPEC.md](../SPEC.md)
