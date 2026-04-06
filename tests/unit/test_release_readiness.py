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


def test_tool_executor_examples_exist_for_supported_languages() -> None:
    example_paths = {
        "examples/tool-executors/README.md",
        "examples/tool-executors/python/host_stdio_executor.py",
        "examples/tool-executors/python/host_tcp_executor.py",
        "examples/tool-executors/csharp/HostStdioExecutor/Program.cs",
        "examples/tool-executors/csharp/HostTcpExecutor/Program.cs",
        "examples/tool-executors/rust/Cargo.toml",
        "examples/tool-executors/rust/src/bin/host_stdio_executor.rs",
        "examples/tool-executors/rust/src/bin/host_tcp_executor.rs",
    }

    for relative_path in example_paths:
        assert (REPO_ROOT / relative_path).exists()


def test_documentation_mentions_real_cli_and_example_paths() -> None:
    operator_doc = (REPO_ROOT / "doc" / "operator-guide.md").read_text(encoding="utf-8")
    developer_doc = (REPO_ROOT / "doc" / "developer-guide.md").read_text(encoding="utf-8")
    docs_index = (REPO_ROOT / "doc" / "README.md").read_text(encoding="utf-8")
    integrations_doc = (REPO_ROOT / "doc" / "integrations.md").read_text(encoding="utf-8")
    troubleshooting_doc = (REPO_ROOT / "doc" / "troubleshooting.md").read_text(encoding="utf-8")
    contributing_doc = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    changelog_doc = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    tep_doc = (REPO_ROOT / "doc" / "tep-protocol.md").read_text(encoding="utf-8")
    rlp_doc = (REPO_ROOT / "doc" / "rlp-protocol.md").read_text(encoding="utf-8")
    readiness_doc = (REPO_ROOT / "doc" / "readiness-file.md").read_text(encoding="utf-8")

    assert "naia-relay --help" in operator_doc
    assert "--config-file" in operator_doc
    assert 'pip install -e ".[dev]"' in operator_doc
    assert "examples/neovim-host/config.yaml" in operator_doc
    assert "examples/codex-client/config.yaml" in operator_doc
    assert "examples/scripts/run-direct.sh" in operator_doc
    assert "examples/tool-executors/README.md" in (
        REPO_ROOT / "README.md"
    ).read_text(encoding="utf-8")
    assert "tests/integration/" in developer_doc
    assert "SPEC.md" in docs_index
    assert "troubleshooting.md" in docs_index
    assert "integrations.md" in docs_index
    assert "Codex + host relay" in integrations_doc
    assert (
        "Tools are visible, but calling them does not execute the real tool"
        in troubleshooting_doc
    )
    assert "ruff check ." in contributing_doc
    assert "## Unreleased" in changelog_doc
    assert "register_tools" in tep_doc
    assert "execute_tool" in tep_doc
    assert "bind_session" in rlp_doc
    assert "tool_snapshot" in rlp_doc
    assert "--ready-file" in operator_doc
    assert "NAIA_RELAY_READY_FILE" in readiness_doc
