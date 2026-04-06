# Tool Executor Examples

These examples show how a Tool Executor can talk to `naia-relay` in **host**
mode using the Tool Executor Protocol (TEP).

Each language includes two examples:

- **stdio** — executor talks to the host relay over stdio
- **tcp** — executor talks TEP over a TCP socket

The examples all:

1. send `register_executor`
2. send `register_tools`
3. wait for `execute_tool`
4. return `execution_result`

## Example tool

All examples register one tool named `echo` with this behavior:

- input:
  - `{ "message": "hello" }`
- output:
  - MCP-shaped content containing the message

## Host relay configuration

### Host relay with stdio executor transport

```yaml
role: host
executor:
  transport: stdio
relay_link:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 61280
```

Run the relay:

```bash
naia-relay --config-yaml '
role: host
executor:
  transport: stdio
relay_link:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 61280
'
```

Then pipe one of the stdio executor examples into it.

### Host relay with TCP executor transport

```yaml
role: host
executor:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 7001
relay_link:
  transport: tcp
  bind_host: 127.0.0.1
  bind_port: 61280
```

Run the relay:

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
  bind_port: 61280
'
```

Then start one of the TCP executor examples and point it at `127.0.0.1:7001`.

## Files

### Python

- `python/host_stdio_executor.py`
- `python/host_tcp_executor.py`

### C#

- `csharp/HostStdioExecutor/`
- `csharp/HostTcpExecutor/`

### Rust

- `rust/Cargo.toml`
- `rust/src/bin/host_stdio_executor.rs`
- `rust/src/bin/host_tcp_executor.rs`

## Notes

- The stdio examples are useful for host setups where:
  - `role: host`
  - `executor.transport: stdio`
- The TCP examples are useful for host setups where:
  - `role: host`
  - `executor.transport: tcp`
  - `executor.bind_host` / `executor.bind_port` are used so the relay listens
    for the executor connection
- All examples use newline-delimited JSON TEP framing.
