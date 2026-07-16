"""Render BKN snapshots for prompts or tool results."""

from __future__ import annotations

from html import escape

from bamboo.bkn.models import BknSnapshot


def render_bkn_snapshot(snapshot: BknSnapshot) -> str:
    """Render a BknSnapshot as stable Markdown."""
    lines = [
        "# BKN Context",
        "",
        f"- Platform: `{snapshot.platform_id}`",
        f"- Manifest Status: `{snapshot.manifest_status}`",
    ]
    if snapshot.skeleton:
        lines.extend(["", "## Skeleton"])
        lines.extend(f"- {item}" for item in snapshot.skeleton)
    if snapshot.static_attrs:
        lines.extend(["", "## Attributes"])
        for node_id, attrs in sorted(snapshot.static_attrs.items()):
            values = ", ".join(f"{key}={escape(str(value))}" for key, value in sorted(attrs.items()))
            lines.append(f"- `{node_id}`: {values}")
    if snapshot.operator_outputs:
        lines.extend(["", "## Operators"])
        for node_id, outputs in sorted(snapshot.operator_outputs.items()):
            values = ", ".join(f"{key}={escape(str(value))}" for key, value in sorted(outputs.items()))
            lines.append(f"- `{node_id}`: {values}")
    if snapshot.available_actions:
        lines.extend(["", "## Available Actions"])
        lines.extend(f"- `{action.name}`: {action.description}" for action in snapshot.available_actions)
    if snapshot.attrs_unavailable:
        lines.extend(["", "## Attributes Unavailable"])
        lines.extend(f"- `{node_id}`" for node_id in snapshot.attrs_unavailable)
    return "\n".join(lines)
