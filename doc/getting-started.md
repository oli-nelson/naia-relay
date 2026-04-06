# Getting Started

This walkthrough starts with the simplest useful setup:

```text
Tool Executor <--stdio TEP--> naia-relay <--http MCP--> MCP client
```

That keeps everything in a single relay process and proves the core path first:

1. a Tool Executor registers a tool over **TEP**
2. `naia-relay` exposes that tool over **MCP**
3. an MCP client discovers and calls it over **HTTP**

If you later need a long-lived host relay plus short-lived client relays, move on
to the bridged docs after this guide.

## What you'll run

This guide uses the included example:

- [`examples/python/http_print_message_tool.py`](../examples/python/http_print_message_tool.py)

That script:

- launches `naia-relay` in **direct** mode
- connects to it over **stdio TEP**
- registers a `print_message` tool
- exposes MCP over **HTTP** on `127.0.0.1:8181`

## 1. Start the example

From the repo root:

```bash
python3 examples/python/http_print_message_tool.py
```

Expected output:

```text
HTTP MCP server listening on http://127.0.0.1:8181/mcp
Registered tool: print_message
```

At this point the flow looks like:

```text
example Tool Executor <--stdio TEP--> naia-relay <--http MCP--> your MCP client
```

## 2. Verify MCP initialization

In a second terminal, send an MCP `initialize` request:

```bash
curl -s http://127.0.0.1:8181/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {}
    }
  }'
```

You should get a JSON-RPC response with a `result` containing:

- `protocolVersion`
- `capabilities`
- `serverInfo`

## 3. Verify tool discovery

List tools:

```bash
curl -s http://127.0.0.1:8181/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

You should see a tool named `print_message`.

## 4. Call the tool

Invoke the registered tool:

```bash
curl -s http://127.0.0.1:8181/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "print_message",
      "arguments": {
        "message": "hello from MCP"
      }
    }
  }'
```

Expected behavior:

- the example process prints something like:

  ```text
  print_message tool invoked with: hello from MCP
  ```

- the HTTP response contains MCP tool result content with the echoed message

## 5. Point a real MCP client at it

Any MCP client that supports HTTP MCP can now talk to:

- `http://127.0.0.1:8181/mcp`

For client-specific setup examples, see:

- [integrations.md](integrations.md)

## What just happened

The example script starts `naia-relay` with this direct-mode shape:

```yaml
role: direct

mcp:
  transport: http
  host: 127.0.0.1
  port: 8181

executor:
  transport: stdio
```

So:

- the **executor side** is local stdio TEP
- the **client side** is HTTP MCP
- there is no host/client relay split yet

## When to use the more complex bridged setup

Use the two-relay host/client topology when you need things like:

- a long-lived tool host
- a stable MCP client config across many agent sessions
- relay-to-relay forwarding over **RLP**

That topology looks like:

```text
Tool Executor <--stdio|tcp TEP--> host relay <--tcp RLP--> client relay <--stdio|http MCP--> MCP client
```

For that flow, continue with:

- [operator-guide.md](operator-guide.md)
- [integrations.md](integrations.md)
- [readiness-file.md](readiness-file.md)

## If something fails

Check:

- the example process output
- `naia-relay` stderr logs
- whether port `8181` is already in use

See also:

- [troubleshooting.md](troubleshooting.md)
- [mcp-compatibility.md](mcp-compatibility.md)
- [../examples/tool-executors/README.md](../examples/tool-executors/README.md)
