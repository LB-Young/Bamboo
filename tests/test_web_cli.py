"""CLI web command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from bamboo.run import app


class _ImmediateTimer:
    def __init__(self, delay, function, args=()):
        self.function = function
        self.args = args
        self.daemon = False

    def start(self) -> None:
        self.function(*self.args)


def test_web_command_starts_server_and_opens_browser(monkeypatch) -> None:
    opened_urls: list[str] = []
    run_calls: list[tuple[str, str, int, bool]] = []
    monkeypatch.setattr("bamboo.run.webbrowser.open", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr("bamboo.run.threading.Timer", _ImmediateTimer)
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app_ref, host, port, reload: run_calls.append((app_ref, host, port, reload)),
    )

    result = CliRunner().invoke(app, ["web"])

    assert result.exit_code == 0
    assert opened_urls == ["http://127.0.0.1:8899"]
    assert run_calls == [("bamboo.adapters.web.app:app", "127.0.0.1", 8899, False)]


def test_web_command_can_skip_browser(monkeypatch) -> None:
    opened_urls: list[str] = []
    run_calls: list[tuple[str, str, int, bool]] = []
    monkeypatch.setattr("bamboo.run.webbrowser.open", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app_ref, host, port, reload: run_calls.append((app_ref, host, port, reload)),
    )

    result = CliRunner().invoke(app, ["web", "--no-browser", "--port", "9000"])

    assert result.exit_code == 0
    assert opened_urls == []
    assert run_calls == [("bamboo.adapters.web.app:app", "127.0.0.1", 9000, False)]


def test_web_fancy_command_starts_fancy_server(monkeypatch) -> None:
    opened_urls: list[str] = []
    run_calls: list[tuple[str, str, int, bool]] = []
    monkeypatch.setattr("bamboo.run.webbrowser.open", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr("bamboo.run.threading.Timer", _ImmediateTimer)
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app_ref, host, port, reload: run_calls.append((app_ref, host, port, reload)),
    )

    result = CliRunner().invoke(app, ["web-fancy", "--port", "9010"])

    assert result.exit_code == 0
    assert opened_urls == ["http://127.0.0.1:9010"]
    assert run_calls == [("bamboo.adapters.web_fancy.app:app", "127.0.0.1", 9010, False)]
