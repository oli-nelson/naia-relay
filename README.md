# naia-relay

`naia-relay` is a flexible Python relay for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) that lets agents, tool executors, and other relays talk to each other across multiple transports.

At a high level, it bridges three protocols:

- **MCP** for agent-facing communication
  - <https://modelcontextprotocol.io/specification/2025-06-18/>
  - this is the protocol used by MCP clients such as Codex
  - from the agent's perspective, `naia-relay` behaves like an MCP-capable peer
- **TEP** (Tool Executor Protocol) for executor-facing communication
  - this is the protocol used by tool hosts such as Neovim to register tools, receive execution requests, and return results
- **RLP** (Relay Link Protocol) for relay-to-relay communication
  - this is the protocol used when one relay instance mirrors or forwards state and execution through another relay instance

That means `naia-relay` can sit between:

- an MCP client and a tool executor directly, or
- a long-lived host relay and one or more short-lived client relays

It is built for setups like:

- **Codex ↔ your local tools**
- **Neovim ↔ host relay ↔ client relay ↔ Codex**
- **one long-lived tool host with many short-lived agent sessions**

`naia-relay` keeps protocol semantics separate from transport details, so the same logical system can be wired together with:

- `stdio`
- `tcp`
- `http` (where supported)

If you want the shortest path into the rest of the docs, start with:

- [Operator guide](doc/operator-guide.md)
- [Getting started walkthrough](doc/getting-started.md)
- [Integrations guide](doc/integrations.md)
- [Troubleshooting](doc/troubleshooting.md)

---

## Project status

`naia-relay` is usable today for local direct and bridged relay setups, especially:

- MCP client ↔ relay ↔ local tool executor
- Neovim-like tool host ↔ host relay ↔ client relay ↔ agent

Current strengths:

- direct mode
- host/client bridged mode
- MCP over stdio and HTTP in the executable runtime
- TEP over stdio and TCP in the executable runtime
- RLP over TCP in the executable runtime
- dynamic tool registration and bridged execution forwarding
- transport adapter building blocks for `stdio`, `tcp`, and `http`

Current v1 limitations:

- no RLP over HTTP
- unsupported MCP features include sampling, roots, and completion
- direct mode cannot use stdio for both MCP and TEP on the same stdin/stdout pair

See also:

- [Unsupported / deferred v1 features](doc/unsupported-v1.md)
- [Troubleshooting](doc/troubleshooting.md)

---

## Who this is for

`naia-relay` is a good fit if you need:

- a stable MCP-facing process for an agent
- tools that actually live inside another local process
- a long-lived tool host with short-lived agent sessions
- a clean split between protocols and transports

It is probably **not** the right fit if you only need:

- a single in-process tool adapter with no relay boundary
- remote/distributed deployment as the primary use case
- full MCP feature coverage beyond the currently implemented v1 scope

---

## Feature summary

- bridges **MCP**, **TEP**, and **RLP**
- supports **direct**, **host**, and **client** roles
- clean separation between protocol semantics and transport adapters
- dynamic tool, resource, and prompt registration
- readiness-file support for dynamic listener discovery
- subprocess and integration test coverage for core local topologies

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

From a local clone:

```bash
pipx install .
```

Directly from GitHub:

```bash
pipx install git+https://github.com/oli-nelson/naia-relay.git
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

## Current runtime transport support

The repository includes transport adapters and protocol helpers for more
combinations than the executable currently serves directly.

The most important currently runnable paths are:

| Side | Current executable/runtime support |
| --- | --- |
| MCP | `stdio`, `http` |
| TEP | `stdio`, `tcp` |
| RLP | `tcp` |

Notes:

- `MCP stdio` is the main agent-facing runtime path used by Codex-like clients.
- `MCP http` is available as a simple request/response runtime path.
- `TEP stdio` and `TEP tcp` are the main executor-facing runtime paths.
- `RLP tcp` is the main relay-to-relay runtime path.
- Other transport adapters exist in the codebase, but should be treated as
  lower-level implementation building blocks until they are wired into the
  executable runtime more completely.

See also:

- [Operator guide](doc/operator-guide.md)
- [MCP compatibility](doc/mcp-compatibility.md)
- [Unsupported / deferred v1 features](doc/unsupported-v1.md)

---

## How it works

`naia-relay` can run in three roles.

### Direct mode

One relay bridges an MCP client directly to a Tool Executor.

```text
MCP client <--stdio MCP--> naia-relay <--tcp TEP--> Tool Executor
```

Use this when you just want one relay process in the middle.

### Host mode

A long-lived host relay stays attached to a Tool Executor and owns the authoritative tool registry for that session.

```text
Tool Executor <--stdio TEP--> host naia-relay
```

The host relay then exposes that state to downstream client relays over RLP.

### Client mode

A client relay stays attached to an MCP client and connects upstream to a host relay.

```text
host naia-relay <--tcp RLP--> client naia-relay <--stdio MCP--> MCP client
```

This is especially useful when:

- the MCP client must keep a stable config
- the tool host is long-lived
- agent sessions come and go

### Example bridged topology

```text
Neovim <--stdio TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> Codex
```

Another valid bridged example is:

```text
Tool Executor <--tcp TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> Codex
```

For the current executable/runtime support matrix, see:

- [MCP compatibility](doc/mcp-compatibility.md)
- [Operator guide](doc/operator-guide.md)

---

## How tool registration and execution work

On the executor-facing side, the relay uses **TEP**.

This flow applies whether the executor is attached to:

- a **direct** relay, or
- a **host** relay

Typical flow:

1. the Tool Executor connects to `naia-relay` over TEP
2. it sends `register_executor`
3. it sends `register_tools` with tool schemas
4. the relay exposes those tools upstream over MCP
5. when an agent calls a tool, the relay sends `execute_tool` back to the executor
6. the executor runs the real local logic
7. the executor replies with `execution_result` or `execution_error`

In practice, this lets an editor or automation runtime:

- dynamically register tools as they become available
- receive tool invocations from upstream agents
- execute the real local implementation
- return MCP-shaped output through the relay chain

---

## Transport notes

Current executable/runtime support:

- **MCP side:** `stdio`, `http`
- **TEP side:** `stdio`, `tcp`
- **RLP side:** `tcp`

Important:

- **MCP over stdio** uses official MCP newline-delimited JSON framing
- **MCP over HTTP** accepts POST requests on `/` and `/mcp`
- **TEP over stdio** uses newline-delimited JSON
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

- [`examples/configs/direct.yaml`](examples/configs/direct.yaml)
- [`examples/configs/host.yaml`](examples/configs/host.yaml)
- [`examples/configs/client.yaml`](examples/configs/client.yaml)
- [`examples/python/http_print_message_tool.py`](examples/python/http_print_message_tool.py) —
  launches `naia-relay`, registers a simple tool over stdio, and exposes MCP over HTTP
- [`examples/tool-executors/README.md`](examples/tool-executors/README.md) — host-side
  tool executor examples in Python, C#, and Rust for stdio and TCP TEP

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

## Client setup examples

Here are practical examples of how popular MCP-capable clients can launch
`naia-relay` in **client** mode.

In each case, the client starts `naia-relay` over stdio, and `naia-relay`
connects upstream to a host relay over RLP.

Shared client YAML:

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

### Codex

Codex supports MCP servers through the CLI and `~/.codex/config.toml`.

For `naia-relay`, a typical local stdio-server setup is:

```toml
[mcp_servers.naia]
command = "naia-relay"
args = ["--config-file", "/absolute/path/to/naia-relay-client.yaml"]
```

You can also provide the client config through an external environment variable:

```toml
[mcp_servers.naia]
command = "naia-relay"
env_vars = ["NAIA_RELAY_CONFIG_YAML"]
```

OpenAI docs:

- <https://developers.openai.com/learn/docs-mcp>

### OpenCode

OpenCode supports both local and remote MCP servers. For a local `naia-relay`
client process, use `type: "local"` and provide the command as an array.

Example `opencode.json` / `opencode.jsonc` entry:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "naia": {
      "type": "local",
      "command": ["naia-relay", "--config-file", "/absolute/path/to/naia-relay-client.yaml"],
      "enabled": true
    }
  }
}
```

OpenCode config docs:

- <https://opencode.ai/docs/config/>

### Claude Code

```bash
claude mcp add --transport stdio --scope user naia -- \
  naia-relay --config-file /absolute/path/to/naia-relay-client.yaml
```

Claude Code MCP docs:

- <https://docs.anthropic.com/en/docs/claude-code/mcp>

---

## Readiness files

For setups where a parent process needs to learn runtime metadata such as a dynamically assigned TCP port, `naia-relay` can write a readiness file:

```bash
naia-relay --config-file examples/configs/host.yaml --ready-file /tmp/naia-relay-ready.json
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
- [Troubleshooting](doc/troubleshooting.md)
- [Integrations guide](doc/integrations.md)

Protocol references:

- [TEP protocol reference](doc/tep-protocol.md)
- [RLP protocol reference](doc/rlp-protocol.md)

Project design docs:

- [Specification](SPEC.md)
- [Implementation plan](PLAN.md)

Contribution and maintenance:

- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

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

## Reporting issues

If you hit a problem, include as much of the following as you can:

- relay role and transport config
- exact command used to launch `naia-relay`
- whether the issue is in direct or bridged mode
- stderr output
- readiness file contents if relevant
- whether tools are:
  - not visible
  - visible but not executable
  - returning the wrong result

For common failure modes, start with:

- [Troubleshooting](doc/troubleshooting.md)
