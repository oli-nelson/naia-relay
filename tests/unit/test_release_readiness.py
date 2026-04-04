from __future__ import annotations

from pathlib import Path

from naia_relay.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_example_configs_are_valid_yaml_for_the_loader() -> None:
    example_files = sorted((REPO_ROOT / "examples").rglob("*.yaml"))
    assert example_files

    for path in example_files:
        config, _ = load_config(cli_config_file=path)
        assert config.role in {"direct", "host", "client"}


def test_example_shell_scripts_exist_for_supported_modes() -> None:
    scripts = {
        "examples/scripts/run-direct.sh",
        "examples/scripts/run-host.sh",
        "examples/scripts/run-client.sh",
        "examples/scripts/run-neovim-host.sh",
        "examples/scripts/run-codex-client.sh",
    }

    for relative_path in scripts:
        assert (REPO_ROOT / relative_path).exists()


def test_documentation_mentions_real_cli_and_example_paths() -> None:
    operator_doc = (REPO_ROOT / "doc" / "operator-guide.md").read_text(encoding="utf-8")
    developer_doc = (REPO_ROOT / "doc" / "developer-guide.md").read_text(encoding="utf-8")
    docs_index = (REPO_ROOT / "doc" / "README.md").read_text(encoding="utf-8")
    tep_doc = (REPO_ROOT / "doc" / "tep-protocol.md").read_text(encoding="utf-8")
    rlp_doc = (REPO_ROOT / "doc" / "rlp-protocol.md").read_text(encoding="utf-8")
    readiness_doc = (REPO_ROOT / "doc" / "readiness-file.md").read_text(encoding="utf-8")

    assert "naia-relay --help" in operator_doc
    assert "--config-file" in operator_doc
    assert 'pip install -e ".[dev]"' in operator_doc
    assert "examples/neovim-host/config.yaml" in operator_doc
    assert "examples/codex-client/config.yaml" in operator_doc
    assert "examples/scripts/run-direct.sh" in operator_doc
    assert "tests/integration/" in developer_doc
    assert "SPEC.md" in docs_index
    assert "register_tools" in tep_doc
    assert "execute_tool" in tep_doc
    assert "bind_session" in rlp_doc
    assert "tool_snapshot" in rlp_doc
    assert "--ready-file" in operator_doc
    assert "NAIA_RELAY_READY_FILE" in readiness_doc
