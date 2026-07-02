"""EditTool tests."""

from __future__ import annotations

import pytest

from bamboo.tools.buildin.edit import EditTool


@pytest.mark.asyncio
async def test_edit_tool_multi_replace_is_all_or_nothing(tmp_path) -> None:
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = await EditTool().execute(
        str(path),
        mode="multi_replace",
        edits=[
            {"old": "alpha", "new": "one"},
            {"old": "gamma", "new": "three"},
        ],
    )

    assert result.success is True
    assert path.read_text(encoding="utf-8") == "one\nbeta\nthree\n"


@pytest.mark.asyncio
async def test_edit_tool_multi_replace_does_not_write_when_any_old_fails(tmp_path) -> None:
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = await EditTool().execute(
        str(path),
        mode="multi_replace",
        edits=[
            {"old": "alpha", "new": "one"},
            {"old": "missing", "new": "three"},
        ],
    )

    assert result.success is False
    assert result.error == "old_string_match_count"
    assert path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"
