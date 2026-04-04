from __future__ import annotations

from pathlib import Path

import pytest

from naia_relay.config import load_config
from naia_relay.errors import ConfigurationError


def test_load_config_from_cli_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: stdio\n",
        encoding="utf-8",
    )

    config, source = load_config(cli_config_file=path)

    assert config.role == "direct"
    assert source.kind == "cli_file"


def test_load_config_from_environment_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: stdio\n",
        encoding="utf-8",
    )

    config, source = load_config(environ={"NAIA_RELAY_CONFIG_FILE": str(path)})

    assert config.role == "direct"
    assert source.kind == "env_file"


def test_load_config_from_cli_yaml() -> None:
    config, source = load_config(
        cli_config_yaml=(
            "role: client\n"
            "mcp:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  port: 9001\n"
        )
    )

    assert config.role == "client"
    assert source.kind == "cli_yaml"


def test_load_config_from_environment_yaml() -> None:
    config, source = load_config(
        environ={
            "NAIA_RELAY_CONFIG_YAML": (
                "role: client\n"
                "mcp:\n  transport: stdio\n"
                "relay_link:\n  transport: tcp\n  port: 9001\n"
            )
        }
    )

    assert config.role == "client"
    assert source.kind == "env_yaml"


def test_cli_precedence_over_environment(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: stdio\n",
        encoding="utf-8",
    )

    config, source = load_config(
        cli_config_file=path,
        environ={
            "NAIA_RELAY_CONFIG_YAML": (
                "role: client\n"
                "mcp:\n  transport: stdio\n"
                "relay_link:\n  transport: tcp\n  port: 9001\n"
            )
        },
    )

    assert config.role == "direct"
    assert source.kind == "cli_file"


def test_conflicting_cli_sources_fail(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: stdio\n")

    with pytest.raises(ConfigurationError):
        load_config(cli_config_file=path, cli_config_yaml="role: client")


def test_conflicting_environment_sources_fail() -> None:
    with pytest.raises(ConfigurationError):
        load_config(
            environ={
                "NAIA_RELAY_CONFIG_FILE": "/tmp/example.yaml",
                "NAIA_RELAY_CONFIG_YAML": "role: client",
            }
        )


def test_missing_sources_fail() -> None:
    with pytest.raises(ConfigurationError):
        load_config(environ={})


def test_direct_requires_mcp_and_executor() -> None:
    with pytest.raises(ConfigurationError):
        load_config(cli_config_yaml="role: direct\nmcp:\n  transport: stdio\n")


def test_host_requires_executor_and_relay_link() -> None:
    with pytest.raises(ConfigurationError):
        load_config(cli_config_yaml="role: host\nexecutor:\n  transport: stdio\n")


def test_client_requires_mcp_and_relay_link() -> None:
    with pytest.raises(ConfigurationError):
        load_config(cli_config_yaml="role: client\nmcp:\n  transport: stdio\n")


def test_host_rejects_mcp_section() -> None:
    with pytest.raises(ConfigurationError):
        load_config(
            cli_config_yaml=(
                "role: host\n"
                "mcp:\n  transport: stdio\n"
                "executor:\n  transport: stdio\n"
                "relay_link:\n  transport: tcp\n  bind_port: 9001\n"
            )
        )


def test_client_rejects_executor_section() -> None:
    with pytest.raises(ConfigurationError):
        load_config(
            cli_config_yaml=(
                "role: client\n"
                "mcp:\n  transport: stdio\n"
                "executor:\n  transport: stdio\n"
                "relay_link:\n  transport: tcp\n  port: 9001\n"
            )
        )


def test_relay_link_http_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        load_config(
            cli_config_yaml=(
                "role: client\n"
                "mcp:\n  transport: stdio\n"
                "relay_link:\n  transport: http\n  port: 9001\n"
            )
        )


def test_host_relay_link_bind_port_zero_is_allowed() -> None:
    config, _ = load_config(
        cli_config_yaml=(
            "role: host\n"
            "executor:\n  transport: stdio\n"
            "relay_link:\n  transport: tcp\n  bind_host: 127.0.0.1\n  bind_port: 0\n"
        )
    )

    assert config.role == "host"
    assert config.relay_link.bind_port == 0
