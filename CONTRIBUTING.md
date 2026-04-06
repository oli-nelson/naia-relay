# Contributing

Thanks for your interest in contributing to `naia-relay`.

## Before you start

Please read:

- [README.md](README.md)
- [SPEC.md](SPEC.md)
- [PLAN.md](PLAN.md)
- [doc/developer-guide.md](doc/developer-guide.md)

`SPEC.md` is the behavioral source of truth when there is a conflict.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Validation

Run before submitting changes:

```bash
ruff check .
pytest
```

## Contribution guidelines

- keep protocol semantics separate from transport behavior
- preserve direct/host/client role boundaries
- add or update tests for behavior changes
- update docs when changing externally visible behavior
- prefer small, reviewable commits

## Good bug reports

Please include:

- exact config used
- relay role(s) involved
- direct vs bridged topology
- stderr output
- relevant readiness file contents
- reproduction steps

## Documentation updates

If you change:

- config behavior
- protocol behavior
- startup/runtime behavior
- public examples

please update the relevant docs in:

- `README.md`
- `doc/`
- `SPEC.md` where appropriate

For public-facing changes, prefer:

- concise README updates for discoverability
- operator docs for practical usage
- protocol docs for wire-level behavior
