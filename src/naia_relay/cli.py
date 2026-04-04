from __future__ import annotations

import argparse
import logging
from pathlib import Path

from naia_relay.config import load_config
from naia_relay.errors import ConfigurationError
from naia_relay.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="naia-relay",
        description="Bidirectional MCP relay scaffold.",
    )
    parser.add_argument("--config-file", type=Path, help="Path to YAML config file.")
    parser.add_argument("--config-yaml", help="Inline YAML config string.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging()

    try:
        load_config(args.config_file, args.config_yaml)
    except ConfigurationError as exc:
        logging.getLogger(__name__).error("Configuration error: %s", exc)
        return 2
    return 0
