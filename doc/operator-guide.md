# Operator Guide

This guide is for running `naia-relay` locally as an executable.

## Installation

### Editable development install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Install into the current environment

```bash
pip install .
```

### Isolated install with pipx

```bash
pipx install .
```

After installation, the executable is:

```bash
naia-relay
```

## Configuration sources

`naia-relay` loads YAML configuration from exactly one of:

- `--config-file /path/to/config.yaml`
- `--config-yaml "<yaml string>"`
- `NAIA_RELAY_CONFIG_FILE`
- `NAIA_RELAY_CONFIG_YAML`

Rules:

- CLI sources override environment sources
- file-path and inline-YAML sources are mutually exclusive
- conflicting sources fail fast

## CLI

Show help:

```bash
naia-relay --help
```

Validate a config by starting and stopping once:

```bash
naia-relay --config-file examples/direct/config.yaml --once
```

Run continuously:

```bash
naia-relay --config-file examples/direct/config.yaml
```

Write readiness metadata to a file:

```bash
naia-relay --config-file examples/neovim-host/config.yaml --ready-file /tmp/naia-relay-ready.json
```

## Transport support

### MCP side

Supported in v1:

- `stdio`
- `tcp`
- `http`

### Executor side

Supported in v1:

- `stdio`
- `tcp`
- `http`

### Relay link side

Supported in v1:

- `stdio`
- `tcp`

Not supported in v1:

- `http`

## Stdio protocol mapping

The protocol carried over stdio depends on the peer:

- Tool Executor ↔ relay over stdio
  - TEP
  - JSON messages using newline-delimited framing
- relay ↔ relay over stdio
  - RLP
  - JSON messages using newline-delimited framing
- Codex / MCP client ↔ relay over stdio
  - MCP
  - official MCP stdio framing: UTF-8 newline-delimited JSON

## Important stdio limitation

`naia-relay` does not support a single direct-mode process using stdio for both:

- MCP client traffic, and
- Tool Executor traffic

at the same time on one shared stdin/stdout pair.

Supported stdio-based shapes include:

- host mode: executor `stdio` + relay-link `tcp`
- client mode: MCP `stdio` + relay-link `tcp`
- bridged topologies where host and client each own their own separate stdio link

## Example configs

### Direct role

Use:

- `examples/direct/config.yaml`
- `examples/scripts/run-direct.sh`

### Host role

Use:

- `examples/host/config.yaml`
- `examples/scripts/run-host.sh`

### Client role

Use:

- `examples/client/config.yaml`
- `examples/scripts/run-client.sh`

### Neovim host relay

Use:

- `examples/neovim-host/config.yaml`
- `examples/scripts/run-neovim-host.sh`

This is the long-lived relay that stays attached to the Neovim Tool Executor.

### Codex client relay

Use:

- `examples/codex-client/config.yaml`
- `examples/scripts/run-codex-client.sh`

This is the short-lived relay started for a Codex session. It uses MCP over
`stdio` and connects upstream to the long-lived host relay over RLP.

## Example shell scripts

The repository includes runnable shell wrappers in `examples/scripts/`:

- `run-direct.sh`
- `run-host.sh`
- `run-client.sh`
- `run-neovim-host.sh`
- `run-codex-client.sh`

Examples:

```bash
examples/scripts/run-direct.sh --once
examples/scripts/run-host.sh
examples/scripts/run-client.sh
examples/scripts/run-neovim-host.sh
examples/scripts/run-codex-client.sh
```

## Readiness file support

Use a readiness file when a parent process needs startup metadata such as a
dynamically assigned TCP port.

Supported inputs:

- CLI: `--ready-file`
- environment: `NAIA_RELAY_READY_FILE`

See `doc/readiness-file.md` for the file format.

## Logging

Set the relay log level in YAML:

```yaml
relay:
  log_level: debug
```

The runtime logs include:

- role
- protocol side
- transport summary
- session id
- request id
- execution id

## Fresh local run checklist

1. create and activate `.venv`
2. install with `pip install -e ".[dev]"`
3. choose an example config from `examples/`
4. validate it with `naia-relay --config-file ... --once`
5. run the full suite with `ruff check . && pytest`
