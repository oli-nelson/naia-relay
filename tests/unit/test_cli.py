from naia_relay.cli import main


def test_cli_main_returns_success() -> None:
    assert main() == 0
