#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

READY_FILE="${NAIA_RELAY_READY_FILE:-/tmp/naia-relay-ready.json}"

exec naia-relay \
  --config-file examples/neovim-host/config.yaml \
  --ready-file "$READY_FILE" \
  "$@"
