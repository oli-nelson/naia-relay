from pathlib import Path

from naia_relay.cli import main


def test_cli_main_returns_success(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: stdio\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["naia-relay", "--config-file", str(path)])

    assert main() == 0
