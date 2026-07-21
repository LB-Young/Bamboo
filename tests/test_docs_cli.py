"""CLI docs command tests."""

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


def test_docs_command_starts_server_and_opens_docs_url(monkeypatch) -> None:
    opened_urls: list[str] = []
    run_calls: list[tuple[str, str, int, bool]] = []
    cron_started: list[bool] = []

    def fake_open(url: str) -> bool:
        opened_urls.append(url)
        return True

    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: cron_started.append(True))
    monkeypatch.setattr("bamboo.run.webbrowser.open", fake_open)
    monkeypatch.setattr("bamboo.run.threading.Timer", _ImmediateTimer)
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app_ref, host, port, reload: run_calls.append((app_ref, host, port, reload)),
    )

    result = CliRunner().invoke(app, ["docs"])

    assert result.exit_code == 0
    assert cron_started == [True]
    assert opened_urls == ["http://127.0.0.1:8899/docs"]
    assert run_calls == [("bamboo.adapters.web.app:app", "127.0.0.1", 8899, False)]
    assert "http://127.0.0.1:8899/docs" in result.output


def test_docs_command_accepts_custom_host_and_port(monkeypatch) -> None:
    opened_urls: list[str] = []
    run_calls: list[tuple[str, str, int, bool]] = []
    cron_started: list[bool] = []
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: cron_started.append(True))
    monkeypatch.setattr("bamboo.run.webbrowser.open", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr("bamboo.run.threading.Timer", _ImmediateTimer)
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app_ref, host, port, reload: run_calls.append((app_ref, host, port, reload)),
    )

    result = CliRunner().invoke(app, ["docs", "--host", "0.0.0.0", "--port", "9000"])

    assert result.exit_code == 0
    assert cron_started == [True]
    assert opened_urls == ["http://0.0.0.0:9000/docs"]
    assert run_calls == [("bamboo.adapters.web.app:app", "0.0.0.0", 9000, False)]


def test_docs_command_can_open_existing_server_without_starting_one(monkeypatch) -> None:
    opened_urls: list[str] = []
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: (_ for _ in ()).throw(AssertionError("unexpected cron")))
    monkeypatch.setattr("bamboo.run.webbrowser.open", lambda url: opened_urls.append(url) or True)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected server")))

    result = CliRunner().invoke(app, ["docs", "--no-server"])

    assert result.exit_code == 0
    assert opened_urls == ["http://127.0.0.1:8899/docs"]
