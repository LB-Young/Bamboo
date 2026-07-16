"""BKN platform scope helpers."""

from __future__ import annotations

from pathlib import Path

from bamboo.bkn.models import BknScope
from bamboo.userspace.userspace import get_user_bkn_dir


def platform_scope(platform_id: str, *, bkn_root: Path | None = None) -> BknScope:
    """Create a platform scope rooted under ~/.bamboo/bkn/platforms."""
    return BknScope(platform_id=platform_id, root_dir=bkn_root or get_user_bkn_dir())
