from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from naia_relay.config import load_config
from naia_relay.errors import ConfigurationError
from naia_relay.logging import configure_logging
from naia_relay.runtime import run_from_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="naia-relay",
        description="Bidirectional MCP relay scaffold.",
    )
    parser.add_argument("--config-file", type=Path, help="Path to YAML config file.")
    parser.add_argument("--config-yaml", help="Inline YAML config string.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Start and stop the configured runtime once for validation.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config, _ = load_config(args.config_file, args.config_yaml)
        configure_logging(config.relay.log_level)
        asyncio.run(run_from_config(config, once=args.once))
    except ConfigurationError as exc:
        logging.getLogger(__name__).error("Configuration error: %s", exc)
        return 2
    return 0
