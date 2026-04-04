from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from naia_relay.config.models import RelayAppConfig, parse_config
from naia_relay.errors import ConfigurationError

ENV_CONFIG_FILE = "NAIA_RELAY_CONFIG_FILE"
ENV_CONFIG_YAML = "NAIA_RELAY_CONFIG_YAML"


@dataclass(frozen=True)
class ConfigSource:
    kind: str
    value: str


def _pick_source(
    cli_config_file: Path | None,
    cli_config_yaml: str | None,
    environ: dict[str, str] | None = None,
) -> ConfigSource:
    env = environ or dict(os.environ)

    if cli_config_file and cli_config_yaml:
        raise ConfigurationError(
            "Provide only one CLI config source: --config-file or --config-yaml."
        )

    if cli_config_file:
        return ConfigSource(kind="cli_file", value=str(cli_config_file))

    if cli_config_yaml:
        return ConfigSource(kind="cli_yaml", value=cli_config_yaml)

    env_file = env.get(ENV_CONFIG_FILE)
    env_yaml = env.get(ENV_CONFIG_YAML)

    if env_file and env_yaml:
        raise ConfigurationError(
            f"Provide only one environment config source: {ENV_CONFIG_FILE} or {ENV_CONFIG_YAML}."
        )

    if env_file:
        return ConfigSource(kind="env_file", value=env_file)

    if env_yaml:
        return ConfigSource(kind="env_yaml", value=env_yaml)

    raise ConfigurationError(
        "No configuration source provided. Use --config-file, --config-yaml, "
        f"{ENV_CONFIG_FILE}, or {ENV_CONFIG_YAML}."
    )


def _load_yaml_text(source: ConfigSource) -> str:
    if source.kind in {"cli_yaml", "env_yaml"}:
        return source.value
    path = Path(source.value).expanduser()
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    return path.read_text(encoding="utf-8")


def _parse_yaml_document(text: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover
        raise ConfigurationError(f"Invalid YAML configuration: {exc}") from exc

    if loaded is None:
        raise ConfigurationError("Configuration YAML is empty.")
    if not isinstance(loaded, dict):
        raise ConfigurationError("Configuration YAML must evaluate to a mapping/object.")
    return loaded


def load_config(
    cli_config_file: Path | None = None,
    cli_config_yaml: str | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[RelayAppConfig, ConfigSource]:
    source = _pick_source(cli_config_file, cli_config_yaml, environ)
    config_text = _load_yaml_text(source)
    config_data = _parse_yaml_document(config_text)
    return parse_config(config_data), source
