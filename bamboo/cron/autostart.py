"""Embedded cron heartbeat for long-running Bamboo processes."""

from __future__ import annotations

import os
import threading

import anyio

from bamboo.cron.models import HeartbeatConfig
from bamboo.cron.scheduler import CronScheduler
from bamboo.cron.store import CronStore
from bamboo.helpers.logging import get_logger

_START_LOCK = threading.Lock()
_STARTED = False


def start_embedded_cron(*, interval_seconds: float = 30.0) -> bool:
    """Start one daemon cron heartbeat in the current process.

    Returns True only when this call starts a new heartbeat. The heartbeat is
    process-local: it keeps running while the Bamboo CLI/Web/TUI process lives.
    """
    if _auto_cron_disabled():
        return False
    global _STARTED
    with _START_LOCK:
        if _STARTED:
            return False
        thread = threading.Thread(
            target=_run_embedded_cron,
            kwargs={"interval_seconds": interval_seconds},
            name="bamboo-cron-heartbeat",
            daemon=True,
        )
        thread.start()
        _STARTED = True
        return True


def _run_embedded_cron(*, interval_seconds: float) -> None:
    log = get_logger("cron.autostart")

    async def _run() -> None:
        store = CronStore()
        store.ensure()
        scheduler = CronScheduler(store=store)
        await scheduler.run_forever(heartbeat=HeartbeatConfig(interval_seconds=interval_seconds))

    try:
        anyio.run(_run)
    except BaseException as exc:  # pragma: no cover - daemon safety net
        log.warning("embedded cron heartbeat stopped: {error}", error=exc)


def _auto_cron_disabled() -> bool:
    value = os.environ.get("BAMBOO_AUTO_CRON", "").strip().lower()
    return value in {"0", "false", "no", "off", "disabled"}
