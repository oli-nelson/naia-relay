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

## Example configs

### Direct role

Use:

- `examples/direct/config.yaml`

### Host role

Use:

- `examples/host/config.yaml`

### Client role

Use:

- `examples/client/config.yaml`

### Neovim host relay

Use:

- `examples/neovim-host/config.yaml`

This is the long-lived relay that stays attached to the Neovim Tool Executor.

### Codex client relay

Use:

- `examples/codex-client/config.yaml`

This is the short-lived relay started for a Codex session. It uses MCP over
`stdio` and connects upstream to the long-lived host relay over RLP.

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
