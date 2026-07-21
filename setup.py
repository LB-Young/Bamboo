"""Setuptools entry point for Bamboo install-time hooks."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from setuptools import setup
from setuptools.command.install import install

try:
    from setuptools.command.develop import develop
except Exception:  # pragma: no cover - setuptools can omit legacy develop in some builds.
    develop = None  # type: ignore[assignment]

try:
    from setuptools.command.editable_wheel import editable_wheel
except Exception:  # pragma: no cover - older setuptools may not expose PEP 660 command.
    editable_wheel = None  # type: ignore[assignment]


def _install_playwright_chromium() -> None:
    if os.environ.get("BAMBOO_SKIP_PLAYWRIGHT_INSTALL", "").strip().lower() in {"1", "true", "yes"}:
        print("Bamboo: skipping Playwright Chromium install because BAMBOO_SKIP_PLAYWRIGHT_INSTALL is set.")
        return

    command = [sys.executable, "-m", "playwright", "install", "chromium"]
    print("Bamboo: installing Playwright Chromium runtime...")
    try:
        subprocess.check_call(command)
    except Exception as exc:
        message = (
            "Bamboo: failed to install Playwright Chromium runtime. "
            "The browser tool will not work until you run: "
            f"{sys.executable} -m playwright install chromium"
        )
        if os.environ.get("BAMBOO_STRICT_PLAYWRIGHT_INSTALL", "").strip().lower() in {"1", "true", "yes"}:
            raise RuntimeError(message) from exc
        print(f"{message}\nBamboo: continuing installation. Set BAMBOO_STRICT_PLAYWRIGHT_INSTALL=1 to fail on this.")


class _InstallWithPlaywright(install):
    def run(self) -> None:
        super().run()
        _install_playwright_chromium()


cmdclass: dict[str, Any] = {"install": _InstallWithPlaywright}

if develop is not None:

    class _DevelopWithPlaywright(develop):  # type: ignore[misc, valid-type]
        def run(self) -> None:
            super().run()
            _install_playwright_chromium()

    cmdclass["develop"] = _DevelopWithPlaywright

if editable_wheel is not None:

    class _EditableWheelWithPlaywright(editable_wheel):  # type: ignore[misc, valid-type]
        def run(self) -> None:
            super().run()
            _install_playwright_chromium()

    cmdclass["editable_wheel"] = _EditableWheelWithPlaywright


setup(cmdclass=cmdclass)
