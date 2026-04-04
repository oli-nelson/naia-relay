# naia-relay

Python implementation of a bidirectional MCP relay described in `SPEC.md`.

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
