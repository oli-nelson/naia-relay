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

## Runtime architecture

### Transport adapters

Transport adapters are intentionally separate from protocol semantics:

- `stdio`
- `tcp`
- `http` for MCP and TEP only

Adapters live under `src/naia_relay/transports/`.

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
  - reserved for future external-process end-to-end coverage

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

## Local examples

See the `examples/` folder for:

- `examples/direct/config.yaml`
- `examples/host/config.yaml`
- `examples/client/config.yaml`
- `examples/neovim-host/config.yaml`
- `examples/codex-client/config.yaml`
