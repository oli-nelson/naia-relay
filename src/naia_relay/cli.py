from __future__ import annotations

import argparse
from pathlib import Path


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
    parser.parse_args()
    return 0
