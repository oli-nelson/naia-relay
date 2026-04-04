import os
import subprocess
import sys
import time
from pathlib import Path

from naia_relay.cli import main, resolve_ready_file


def test_cli_main_returns_success(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: tcp\n  port: 9002\n",
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


def test_python_module_entrypoint_stays_alive_for_stdio_server(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "role: direct\nmcp:\n  transport: stdio\nexecutor:\n  transport: tcp\n  port: 9002\n",
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "naia_relay.cli", "--config-file", str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")},
    )
    try:
        time.sleep(0.2)
        assert proc.poll() is None
    finally:
        proc.terminate()
        proc.communicate(timeout=2)
