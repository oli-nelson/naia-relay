# Operator Guide

This guide is for running `naia-relay` locally as an executable.

## Most common deployment patterns

### Direct relay

```text
MCP client <--stdio MCP--> naia-relay <--tcp TEP--> Tool Executor
```

Use this when you want one relay process in the middle.

### Long-lived host + short-lived clients

```text
Neovim <--stdio TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> Codex
```

Use this when:

- the tool host is long-lived
- the MCP client must keep stable config
- agent sessions come and go

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

Quick smoke test for a client config:

```bash
naia-relay --config-file examples/client/config.yaml --once
```

Write readiness metadata to a file:

```bash
naia-relay --config-file examples/host/config.yaml --ready-file /tmp/naia-relay-ready.json
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

### Tool executor examples

Use:

- `examples/tool-executors/README.md`

This folder contains minimal host-side TEP executors in Python, C#, and Rust
for both `stdio` and `tcp`.

## Minimal working examples

### Validate a direct relay config

```bash
naia-relay --config-file examples/direct/config.yaml --once
```

### Run a host relay for a Neovim-like executor

```bash
naia-relay --config-file examples/host/config.yaml --ready-file /tmp/naia-relay-ready.json
```

### Run a client relay for a local MCP client

```bash
naia-relay --config-file examples/client/config.yaml
```

## Example shell scripts

The repository includes runnable shell wrappers in `examples/scripts/`:

- `run-direct.sh`
- `run-host.sh`
- `run-client.sh`

Examples:

```bash
examples/scripts/run-direct.sh --once
examples/scripts/run-host.sh
examples/scripts/run-client.sh
```

See also:

- [integrations.md](integrations.md)
- [troubleshooting.md](troubleshooting.md)

## Readiness file support

Use a readiness file when a parent process needs startup metadata such as a
dynamically assigned TCP port.

Supported inputs:

- CLI: `--ready-file`
- environment: `NAIA_RELAY_READY_FILE`

See `doc/readiness-file.md` for the file format.

## Quick verification workflow

1. validate config once:

```bash
naia-relay --config-file /path/to/config.yaml --once
```

2. run the relay normally
3. confirm stderr logs show startup summary
4. if using host mode with dynamic TCP binding, inspect the readiness file
5. if using a bridged setup, confirm the client relay binds successfully

## Debugging startup failures

If startup fails:

- capture stderr
- confirm the binary on `PATH` is the one you intended to run
- verify the config source being used
- try `--once` first to isolate configuration/startup issues from runtime traffic

See also:

- `doc/troubleshooting.md`

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
