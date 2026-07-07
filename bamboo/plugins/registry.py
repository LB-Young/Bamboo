"""Read installed Bamboo plugin lock entries."""

from __future__ import annotations

from pathlib import Path

from bamboo.plugins.installer import PluginInstaller
from bamboo.plugins.models import PluginLockEntry


class PluginRegistry:
    """Registry backed by the plugin installer lockfile."""

    def __init__(self, *, userspace_dir: Path | None = None) -> None:
        self.installer = PluginInstaller(userspace_dir=userspace_dir)

    def list(self) -> list[PluginLockEntry]:
        """Return installed plugins."""
        return self.installer.list()

    def get(self, name: str) -> PluginLockEntry | None:
        """Return one installed plugin."""
        return self.installer.show(name)
