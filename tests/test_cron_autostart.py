"""Tests for embedded cron autostart."""

from __future__ import annotations

import bamboo.cron.autostart as autostart


class _FakeThread:
    started: list[dict] = []

    def __init__(self, *, target, kwargs, name, daemon):
        self.target = target
        self.kwargs = kwargs
        self.name = name
        self.daemon = daemon

    def start(self) -> None:
        self.started.append(
            {
                "target": self.target,
                "kwargs": self.kwargs,
                "name": self.name,
                "daemon": self.daemon,
            }
        )


def test_embedded_cron_autostart_is_idempotent(monkeypatch) -> None:
    _reset_autostart()
    _FakeThread.started = []
    monkeypatch.setattr(autostart.threading, "Thread", _FakeThread)

    first = autostart.start_embedded_cron(interval_seconds=30.0)
    second = autostart.start_embedded_cron(interval_seconds=30.0)

    assert first is True
    assert second is False
    assert len(_FakeThread.started) == 1
    assert _FakeThread.started[0]["name"] == "bamboo-cron-heartbeat"
    assert _FakeThread.started[0]["daemon"] is True
    assert _FakeThread.started[0]["kwargs"] == {"interval_seconds": 30.0}


def test_embedded_cron_autostart_can_be_disabled(monkeypatch) -> None:
    _reset_autostart()
    _FakeThread.started = []
    monkeypatch.setenv("BAMBOO_AUTO_CRON", "0")
    monkeypatch.setattr(autostart.threading, "Thread", _FakeThread)

    started = autostart.start_embedded_cron(interval_seconds=30.0)

    assert started is False
    assert _FakeThread.started == []


def _reset_autostart() -> None:
    autostart._STARTED = False
