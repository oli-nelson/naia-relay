from pathlib import Path

from naia_relay.cli import main, resolve_ready_file


def test_cli_main_returns_success(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: stdio\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["naia-relay", "--config-file", str(path), "--once"])

    assert main() == 0


def test_resolve_ready_file_prefers_cli_over_environment(tmp_path: Path) -> None:
    cli_path = tmp_path / "cli-ready.json"
    env_path = tmp_path / "env-ready.json"

    resolved = resolve_ready_file(
        cli_path,
        environ={"NAIA_RELAY_READY_FILE": str(env_path)},
    )

    assert resolved == cli_path


def test_resolve_ready_file_uses_environment_when_cli_is_absent(tmp_path: Path) -> None:
    env_path = tmp_path / "env-ready.json"

    resolved = resolve_ready_file(
        None,
        environ={"NAIA_RELAY_READY_FILE": str(env_path)},
    )

    assert resolved == env_path
