# naia-relay

Python implementation of a bidirectional MCP relay described in `SPEC.md`.

See `doc/` for the current developer and operator documentation set:

- `doc/README.md`
- `doc/developer-guide.md`
- `doc/operator-guide.md`
- `doc/unsupported-v1.md`
- `doc/tep-protocol.md`
- `doc/rlp-protocol.md`
- `doc/readiness-file.md`

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
naia-relay --help
pytest
```

## Configuration

The relay loads YAML configuration from one of:

- `--config-file /path/to/config.yaml`
- `--config-yaml "<yaml string>"`
- `NAIA_RELAY_CONFIG_FILE`
- `NAIA_RELAY_CONFIG_YAML`

See `SPEC.md` and `PLAN.md` for design and implementation details.

## Important transport note

`stdio` is protocol-dependent:

- MCP over stdio uses official MCP newline-delimited JSON framing
- TEP over stdio uses newline-delimited JSON
- RLP over stdio uses newline-delimited JSON

`naia-relay` does **not** support a single direct-mode process using stdio for
both the MCP side and the executor side at the same time.

## Operator-visible logs

The relay emits logs with role and session context so local operators can tell:

- which relay role is starting or stopping
- which transports are active for that process
- which session a request belongs to
- when validation failures, disconnects, and reconnect attempts occur

Set `relay.log_level` in YAML to control verbosity, for example:

```yaml
relay:
  log_level: debug
```
