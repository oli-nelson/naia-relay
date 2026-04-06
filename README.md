# naia-relay

`naia-relay` is a flexible Python relay for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) that lets agents, tool executors, and other relays talk to each other across multiple transports.

It is built for setups like:

- **Codex ↔ your local tools**
- **Neovim ↔ host relay ↔ client relay ↔ Codex**
- **one long-lived tool host with many short-lived agent sessions**

`naia-relay` keeps protocol semantics separate from transport details, so the same logical system can be wired together with:

- `stdio`
- `tcp`
- `http` (where supported)

---

## Why this exists

Many MCP environments need a stable MCP server process on the agent side, while the actual tools live somewhere else:

- inside an editor
- inside a local automation runtime
- inside another relay process

`naia-relay` solves that by bridging:

- **MCP** on the agent-facing side
- **TEP** (Tool Executor Protocol) on the executor-facing side
- **RLP** (Relay Link Protocol) between relay instances

That means agents can see and call tools over MCP even when the real tool implementation lives behind a separate executor process such as Neovim.

---

## Quickstart

### Install globally with `pipx`

```bash
pipx install .
```

After installation:

```bash
naia-relay --help
```

If you are installing from a clone of this repository and want to refresh your global install after local changes:

```bash
pipx install .
# or reinstall/upgrade in your preferred pipx workflow
```

---

## How it works

`naia-relay` can run in three roles.

### Direct mode

One relay bridges an MCP client directly to a Tool Executor.

```text
MCP client <-> naia-relay <-> Tool Executor
```

Use this when you just want one relay process in the middle.

### Host mode

A long-lived host relay stays attached to a Tool Executor and owns the authoritative tool registry for that session.

```text
Tool Executor <-> host naia-relay
```

The host relay then exposes that state to downstream client relays over RLP.

### Client mode

A client relay stays attached to an MCP client and connects upstream to a host relay.

```text
host naia-relay <-> client naia-relay <-> MCP client
```

This is especially useful when:

- the MCP client must keep a stable config
- the tool host is long-lived
- agent sessions come and go

### Example bridged topology

```text
Neovim <--stdio TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> Codex
```

---

## Transport notes

Supported transports in v1:

- **MCP side:** `stdio`, `tcp`, `http`
- **TEP side:** `stdio`, `tcp`, `http`
- **RLP side:** `stdio`, `tcp`

Important:

- **MCP over stdio** uses official MCP newline-delimited JSON framing
- **TEP over stdio** uses newline-delimited JSON
- **RLP over stdio** uses newline-delimited JSON
- a single **direct-mode** process does **not** support using stdio for both MCP and TEP on the same shared stdin/stdout pair

---

## Example configuration

### Direct mode

```yaml
role: direct

mcp:
  transport: stdio

executor:
  transport: tcp
  host: 127.0.0.1
  port: 9001

relay:
  log_level: info
  request_timeout_seconds: 60
```

### Host mode

```yaml
role: host

executor:
  transport: stdio

relay_link:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 0

relay:
  log_level: info
```

### Client mode

```yaml
role: client

mcp:
  transport: stdio

relay_link:
  transport: tcp
  host: 127.0.0.1
  port: 61280

relay:
  log_level: info
```

More example configs live in:

- [`examples/direct/config.yaml`](examples/direct/config.yaml)
- [`examples/host/config.yaml`](examples/host/config.yaml)
- [`examples/client/config.yaml`](examples/client/config.yaml)
- [`examples/neovim-host/config.yaml`](examples/neovim-host/config.yaml)
- [`examples/codex-client/config.yaml`](examples/codex-client/config.yaml)

---

## How to provide config

`naia-relay` accepts YAML config from exactly one source:

### CLI file path

```bash
naia-relay --config-file /path/to/config.yaml
```

### CLI inline YAML

```bash
naia-relay --config-yaml $'role: client\nmcp:\n  transport: stdio\nrelay_link:\n  transport: tcp\n  host: 127.0.0.1\n  port: 61280\n'
```

### Environment: config file

```bash
export NAIA_RELAY_CONFIG_FILE=/path/to/config.yaml
naia-relay
```

### Environment: inline YAML

```bash
export NAIA_RELAY_CONFIG_YAML=$'role: client\nmcp:\n  transport: stdio\nrelay_link:\n  transport: tcp\n  host: 127.0.0.1\n  port: 61280\n'
naia-relay
```

Rules:

- CLI sources take priority over environment sources
- file-path and inline-YAML forms are mutually exclusive
- conflicting config sources fail fast

---

## Readiness files

For setups where a parent process needs to learn runtime metadata such as a dynamically assigned TCP port, `naia-relay` can write a readiness file:

```bash
naia-relay --config-file examples/neovim-host/config.yaml --ready-file /tmp/naia-relay-ready.json
```

This is especially useful for host mode with `bind_port: 0`.

See:

- [`doc/readiness-file.md`](doc/readiness-file.md)

---

## Documentation

General docs:

- [Documentation index](doc/README.md)
- [Operator guide](doc/operator-guide.md)
- [Developer guide](doc/developer-guide.md)
- [Unsupported / deferred v1 features](doc/unsupported-v1.md)

Protocol references:

- [TEP protocol reference](doc/tep-protocol.md)
- [RLP protocol reference](doc/rlp-protocol.md)

Project design docs:

- [Specification](SPEC.md)
- [Implementation plan](PLAN.md)

---

## Development

Create a local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run checks:

```bash
ruff check .
pytest
```
