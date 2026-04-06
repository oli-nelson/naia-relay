# Getting Started

This walkthrough gives you a minimal local setup that proves the core relay path
 works:

1. start a host relay
2. start a simple Tool Executor
3. start a client relay
4. confirm that tools can be discovered and executed through the bridge

The example uses:

- host relay over `TEP tcp` + `RLP tcp`
- client relay over `MCP stdio` + `RLP tcp`
- the Python TCP example executor from `examples/tool-executors/`

## 1. Start the host relay

Use an inline host config so the executor can connect over TCP:

```bash
naia-relay --config-yaml '
role: host
executor:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 7001
relay_link:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 9001
' --ready-file /tmp/naia-relay-ready.json
```

This gives you:

- a long-lived host relay
- a readiness file containing the resolved RLP listener endpoint

If you want to inspect the readiness file:

```bash
cat /tmp/naia-relay-ready.json
```

## 2. Attach a Tool Executor to the host

In a second terminal, connect the example TCP executor:

```bash
python3 examples/tool-executors/python/host_tcp_executor.py --host 127.0.0.1 --port 7001
```

For a simpler protocol reference and more examples, see:

- [../examples/tool-executors/README.md](../examples/tool-executors/README.md)

## 3. Start a client relay

Use the built-in client example config:

```bash
naia-relay --config-file examples/client/config.yaml
```

This gives you:

- an MCP-facing relay over `stdio`
- an upstream connection to the host relay over `RLP tcp`

## 4. Point your MCP client at the client relay

Typical local MCP clients launch `naia-relay` as a command and use:

- `mcp.transport: stdio`
- `relay_link.transport: tcp`

For client-specific setup examples, see:

- [integrations.md](integrations.md)

## 5. Verify the path end to end

At this point the flow should look like:

```text
Tool Executor <--tcp TEP--> host relay <--tcp RLP--> client relay <--stdio MCP--> MCP client
```

Expected behavior:

- the MCP client can list tools
- the example `echo` tool should appear
- calling `echo` should return text produced by the example executor

## If something fails

The fastest places to look are:

- the host relay stderr logs
- the client relay stderr logs
- the readiness file contents

See also:

- [troubleshooting.md](troubleshooting.md)
- [operator-guide.md](operator-guide.md)
