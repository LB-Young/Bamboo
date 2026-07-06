"""Browser tool tests."""

from __future__ import annotations

import anyio

from bamboo.tools.buildin.browser import BrowserAction, BrowserTool
from bamboo.tools.buildin.base import ToolResult


def test_browser_tool_dispatches_single_action_parameter() -> None:
    fake = _FakeBrowserSession()
    tool = BrowserTool(session=fake)

    async def run_test() -> None:
        opened = await tool.execute(action="open", url="https://example.com")
        text = await tool.execute(action="extract_text", selector="main")

        assert opened.success
        assert text.content == "page text"
        assert [action.action for action in fake.actions] == ["open", "extract_text"]
        assert fake.actions[0].url == "https://example.com"
        assert fake.actions[1].selector == "main"

    anyio.run(run_test)


def test_browser_tool_rejects_unknown_action() -> None:
    async def run_test() -> None:
        result = await BrowserTool(session=_FakeBrowserSession()).execute(action="download_everything")

        assert not result.success
        assert result.error == "unsupported_browser_action"
        assert "click" in result.metadata["supported_actions"]  # type: ignore[index]

    anyio.run(run_test)


class _FakeBrowserSession:
    def __init__(self) -> None:
        self.actions: list[BrowserAction] = []

    async def execute(self, action: BrowserAction) -> ToolResult:
        self.actions.append(action)
        if action.action == "extract_text":
            return ToolResult(content="page text", metadata={"action": action.action})
        return ToolResult(content=f"ok:{action.action}", metadata={"action": action.action})
