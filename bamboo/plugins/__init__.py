"""Bamboo plugin manifest installer."""

from bamboo.plugins.installer import PluginInstaller
from bamboo.plugins.manifest import load_plugin_manifest
from bamboo.plugins.models import (
    PluginInstallResult,
    PluginLockEntry,
    PluginManifest,
    PluginRemoveResult,
    PluginScanResult,
)
from bamboo.plugins.registry import PluginRegistry

__all__ = [
    "PluginInstallResult",
    "PluginInstaller",
    "PluginLockEntry",
    "PluginManifest",
    "PluginRegistry",
    "PluginRemoveResult",
    "PluginScanResult",
    "load_plugin_manifest",
]
