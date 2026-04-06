# Integrations Guide

This guide shows how `naia-relay` fits into common real-world integrations.

## 1. Codex + host relay

Typical shape:

```text
Tool Executor <--stdio TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> Codex
```

Recommended pattern:

- keep the host relay long-lived
- run the client relay in `role: client`
- point Codex at `naia-relay` as a local MCP server over stdio

Relevant docs:

- [../README.md](../README.md)
- [operator-guide.md](operator-guide.md)

## 2. OpenCode + host relay

Typical shape:

```text
Tool Executor <--stdio TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> OpenCode
```

Recommended pattern:

- configure OpenCode with a local MCP server
- launch `naia-relay` in client mode
- use `--config-file` for stable config rather than large inline YAML strings

## 3. Claude Code + host relay

Typical shape:

```text
Tool Executor <--stdio TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> Claude Code
```

Recommended pattern:

- add `naia-relay` as a local stdio MCP server
- keep the client relay config file separate and reusable

## 4. Neovim as a Tool Executor

Typical shape:

```text
Neovim <--stdio TEP--> host relay
```

Neovim or another editor/tool host is responsible for:

- `register_executor`
- `register_tools`
- receiving `execute_tool`
- sending back `execution_result` / `execution_error`

If using dynamic host ports:

- use `bind_port: 0`
- provide `--ready-file`
- have the parent process read the resolved endpoint from the readiness file

## 5. Minimal working topologies

### Direct

```text
MCP client <--stdio MCP--> naia-relay <--tcp TEP--> Tool Executor
```

Use:

- `examples/direct/config.yaml`
- `examples/scripts/run-direct.sh`

### Host

```text
Tool Executor <--stdio TEP--> host relay <--tcp RLP listener-->
```

Use:

- `examples/host/config.yaml`
- `examples/neovim-host/config.yaml`
- `examples/scripts/run-host.sh`
- `examples/scripts/run-neovim-host.sh`

### Client

```text
<--tcp RLP--> client relay <--stdio MCP--> MCP client
```

Use:

- `examples/client/config.yaml`
- `examples/codex-client/config.yaml`
- `examples/scripts/run-client.sh`
- `examples/scripts/run-codex-client.sh`

## 6. Common integration advice

- prefer config files over large inline YAML strings when possible
- prefer absolute executable paths in editor/agent integrations when debugging
- confirm the actual `naia-relay` binary being launched
- if startup depends on a host relay, verify the host is already running
- if tools are visible but do not execute, inspect the executor-facing TEP flow

See also:

- [troubleshooting.md](troubleshooting.md)
- [readiness-file.md](readiness-file.md)
- [tep-protocol.md](tep-protocol.md)
- [rlp-protocol.md](rlp-protocol.md)
