# Troubleshooting

This guide covers the most common local setup failures for `naia-relay`.

For setup patterns and example client integrations, see:

- [operator-guide.md](operator-guide.md)
- [integrations.md](integrations.md)

## 1. MCP client says the server timed out during startup

Check:

- is the correct `naia-relay` binary being launched?
- is the config source valid?
- is the host relay already running if the client relay depends on it?

Useful checks:

```bash
naia-relay --config-file /path/to/config.yaml --once
naia-relay --help
```

If you are using a global install and a repo checkout, make sure you are testing
the same binary that your client is launching.

## 2. Host relay starts, but the client relay sees no tools

Check:

- did the executor send `register_executor`?
- did it send `register_tools`?
- is the host relay actually reading TEP on stdio or TCP as configured?
- did the client relay bind successfully to the host relay?

Useful signals:

- host relay stderr logs
- client relay stderr logs
- readiness file contents

If tools are visible over RLP/MCP, registration is probably working.

## 3. Tools are visible, but calling them does not execute the real tool

This usually means one of:

- the host relay is not actually connected to the executor-facing TEP transport
- the executor is not replying with `execution_result` / `execution_error`
- the executor returned a malformed TEP payload

Check:

- does the executor receive `execute_tool`?
- does it send back `execution_result` with the same `execution_id`?
- does stderr mention TEP validation errors?

## 4. Neovim/Lua sender crashes on registration with validation errors

Lua JSON encoders can serialize an empty table as `[]` instead of `{}`.

`naia-relay` is tolerant of empty-list-as-empty-object for common bag fields,
but you should still prefer correct object encoding where possible.

If you see validation errors mentioning:

- `metadata`
- `details`
- `arguments`
- `context`

check whether your sender encoded an empty Lua table as an array.

## 5. MCP over stdio does not handshake correctly

Remember:

- MCP over stdio uses newline-delimited JSON
- logs should go to stderr, not stdout

If stdout contains logs or other non-protocol text, the MCP client may fail to
initialize.

## 6. Direct mode with stdio on both sides fails

This is intentionally unsupported in the current implementation.

A single direct-mode process cannot use one stdin/stdout pair for both:

- MCP traffic
- TEP traffic

Use one of:

- direct mode with one side on TCP or HTTP
- host/client bridged mode

## 7. Readiness file never appears

Check:

- was `--ready-file` provided?
- did startup fail before listener bind completed?
- is the configured path writable?

For host mode with `bind_port: 0`, readiness file output is often the easiest
way to discover the resolved TCP port.

## 8. Client relay cannot bind to the host relay

Check:

- host relay is running
- host relay listener address/port are correct
- client relay is using the right `relay_link.host`
- client relay is using the right `relay_link.port`
- session identity / relay identity are being negotiated correctly

Useful checks:

```bash
cat /tmp/naia-relay-ready.json
```

and verify the client config matches the host relay listener.

## 9. Global install works differently from repo checkout

This is a common source of confusion.

Check:

- which `naia-relay` is on `PATH`
- whether `pipx` points to an older install
- whether your editor/agent launches the same binary you tested manually

Useful commands:

```bash
which naia-relay
naia-relay --help
python -m naia_relay.cli --help
```

## 10. Structured validation errors

For TEP payload validation failures, `naia-relay` now tries to return a
structured error response instead of crashing the stdio loop.

Look for:

- `payload.status = "error"`
- `payload.code = "invalid_payload"`
- `payload.details.validation_errors`

These fields are meant to help executor implementers correct their input.
