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


def test_documentation_mentions_real_cli_and_example_paths() -> None:
    operator_doc = (REPO_ROOT / "doc" / "operator-guide.md").read_text(encoding="utf-8")
    developer_doc = (REPO_ROOT / "doc" / "developer-guide.md").read_text(encoding="utf-8")
    docs_index = (REPO_ROOT / "doc" / "README.md").read_text(encoding="utf-8")

    assert "naia-relay --help" in operator_doc
    assert "--config-file" in operator_doc
    assert 'pip install -e ".[dev]"' in operator_doc
    assert "examples/neovim-host/config.yaml" in operator_doc
    assert "examples/codex-client/config.yaml" in operator_doc
    assert "tests/integration/" in developer_doc
    assert "SPEC.md" in docs_index
