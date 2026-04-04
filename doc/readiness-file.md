# Readiness File Format

`naia-relay` can write a control-plane readiness file after startup.

This mechanism is intended for parent processes such as Neovim that need to
learn runtime metadata without using protocol traffic streams.

## How to enable it

You can provide the readiness-file path in either of these ways:

- CLI argument: `--ready-file /path/to/ready.json`
- environment variable: `NAIA_RELAY_READY_FILE=/path/to/ready.json`

If both are provided, the CLI argument wins.

## Current behavior

After startup completes, the relay writes a JSON document to the configured
path.

The file is written atomically by first writing a temporary file and then
replacing the target path.

## Current primary use case

The main intended use case is:

- a long-lived host relay
- `relay_link.transport: tcp`
- `relay_link.bind_port: 0`

In that case, the host relay binds to an OS-assigned ephemeral port and writes
the resolved port to the readiness file.

## JSON shape

Current file format:

```json
{
  "event": "listener_ready",
  "role": "host",
  "relay_id": "relay_abc123",
  "session_id": "sess_abc123",
  "listeners": {
    "relay_link": {
      "transport": "tcp",
      "host": "127.0.0.1",
      "port": 54321
    }
  }
}
```

## Fields

- `event`
  - currently `listener_ready`
- `role`
  - relay role such as `host`, `client`, or `direct`
- `relay_id`
  - runtime-generated relay instance identifier
- `session_id`
  - runtime-generated session identifier
- `listeners`
  - map of listener names to resolved endpoint details

### `listeners.relay_link`

When present, contains:

- `transport`
- `host`
- `port`

## Notes

- this file is a control-plane mechanism, not part of MCP, TEP, or RLP traffic
- stdout remains reserved for protocol traffic when stdio transports are in use
- stderr is not used for endpoint announcement

## Example parent-process flow

1. Neovim chooses a file path such as `/tmp/naia-relay-ready.json`
2. Neovim spawns `naia-relay` with:
   - `--config-file ...`
   - `--ready-file /tmp/naia-relay-ready.json`
3. the relay starts
4. the relay binds the listener and writes the file
5. Neovim reads the JSON and learns the actual port
