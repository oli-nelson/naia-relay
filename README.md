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
