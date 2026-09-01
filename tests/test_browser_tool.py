"""Browser tool tests."""

from __future__ import annotations

import anyio

from bamboo.tools.buildin.base import ToolResult
from bamboo.tools.buildin.browser import (
    BrowserAction,
    BrowserSession,
    BrowserTool,
    _browser_user_data_dir,
    _format_browser_launch_error,
)


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


def test_browser_tool_exposes_wait_for_login_action() -> None:
    schema = BrowserTool(session=_FakeBrowserSession()).input_schema()

    assert "wait_for_login" in schema["properties"]["action"]["enum"]
    assert "url_pattern" in schema["properties"]


def test_browser_tool_rejects_unknown_action() -> None:
    async def run_test() -> None:
        result = await BrowserTool(session=_FakeBrowserSession()).execute(action="download_everything")

        assert not result.success
        assert result.error == "unsupported_browser_action"
        assert "click" in result.metadata["supported_actions"]  # type: ignore[index]

    anyio.run(run_test)


def test_browser_tool_wait_for_login_uses_long_default_timeout() -> None:
    fake = _FakeBrowserSession()
    tool = BrowserTool(session=fake)

    async def run_test() -> None:
        result = await tool.execute(
            action="wait_for_login",
            url="https://example.com/login",
            selector="[data-testid='avatar']",
            url_pattern="/dashboard",
            script="() => Boolean(window.__loggedIn)",
        )

        assert result.success
        action = fake.actions[0]
        assert action.action == "wait_for_login"
        assert action.url == "https://example.com/login"
        assert action.selector == "[data-testid='avatar']"
        assert action.url_pattern == "/dashboard"
        assert action.script == "() => Boolean(window.__loggedIn)"
        assert action.timeout_ms == 300000

    anyio.run(run_test)


def test_browser_tool_wait_for_login_respects_explicit_timeout() -> None:
    fake = _FakeBrowserSession()
    tool = BrowserTool(session=fake)

    async def run_test() -> None:
        result = await tool.execute(action="wait_for_login", timeout_ms=45000)

        assert result.success
        assert fake.actions[0].timeout_ms == 45000

    anyio.run(run_test)


def test_browser_session_wait_for_login_can_open_login_url() -> None:
    session = _FakeLoginSession()

    async def run_test() -> None:
        result = await session.execute(
            BrowserAction(
                action="wait_for_login",
                url="https://example.com/login",
                selector=".account-menu",
                headless=False,
                timeout_ms=5000,
            )
        )

        assert result.success
        assert result.metadata == {
            "headless": False,
            "user_data_dir": None,
            "action": "wait_for_login",
            "url": "https://example.com/dashboard",
            "title": "Dashboard",
            "timeout_ms": 5000,
        }
        assert session.launched_headless is False
        assert session.page.goto_calls == [("https://example.com/login", "load", 5000)]

    anyio.run(run_test)


def test_browser_session_wait_for_uses_first_matching_locator() -> None:
    session = _FakeMultiMatchSession()

    async def run_test() -> None:
        result = await session.execute(
            BrowserAction(
                action="wait_for",
                selector=".note-content, .title",
                timeout_ms=5000,
            )
        )

        assert result.success
        assert session.locator.waited_timeout == 5000

    anyio.run(run_test)


def test_browser_session_extract_text_combines_multiple_matches() -> None:
    session = _FakeMultiMatchSession()

    async def run_test() -> None:
        result = await session.execute(BrowserAction(action="extract_text", selector=".note-content, .title"))

        assert result.content == "title\n\nbody"
        assert result.metadata["match_count"] == 2  # type: ignore[index]

    anyio.run(run_test)


def test_browser_tool_uses_configured_headless_default(monkeypatch) -> None:
    fake = _FakeBrowserSession()
    monkeypatch.setattr("bamboo.tools.buildin.browser.BambooConfig", lambda: _StubConfig({"browser": {"headless": False}}))
    tool = BrowserTool(session=fake)

    async def run_test() -> None:
        result = await tool.execute(action="open", url="https://example.com")

        assert result.success
        assert fake.actions[0].headless is False

    anyio.run(run_test)


def test_browser_tool_uses_configured_persistent_profile(monkeypatch, tmp_path) -> None:
    profile = tmp_path / "profile"
    monkeypatch.setattr(
        "bamboo.tools.buildin.browser.BambooConfig",
        lambda: _StubConfig({"browser": {"user_data_dir": str(profile)}}),
    )

    assert _browser_user_data_dir() == profile


def test_browser_tool_defaults_to_userspace_persistent_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("bamboo.tools.buildin.browser.BambooConfig", lambda: _StubConfig({"browser": {}}))
    monkeypatch.setattr("bamboo.tools.buildin.browser.get_userspace_dir", lambda: tmp_path / ".bamboo")

    assert _browser_user_data_dir() == tmp_path / ".bamboo" / "storage" / "browser" / "default"


def test_browser_tool_call_headless_overrides_config(monkeypatch) -> None:
    fake = _FakeBrowserSession()
    monkeypatch.setattr("bamboo.tools.buildin.browser.BambooConfig", lambda: _StubConfig({"browser": {"headless": True}}))
    tool = BrowserTool(session=fake)

    async def run_test() -> None:
        result = await tool.execute(action="open", url="https://example.com", headless=False)

        assert result.success
        assert fake.actions[0].headless is False

    anyio.run(run_test)


def test_browser_tool_forces_headful_for_guarded_social_domains(monkeypatch) -> None:
    fake = _FakeBrowserSession()
    monkeypatch.setattr("bamboo.tools.buildin.browser.BambooConfig", lambda: _StubConfig({"browser": {"headless": True}}))
    tool = BrowserTool(session=fake)

    async def run_test() -> None:
        result = await tool.execute(action="open", url="https://www.zhihu.com/question/1")

        assert result.success
        assert fake.actions[0].headless is False

    anyio.run(run_test)


def test_browser_launch_error_includes_underlying_detail() -> None:
    message = _format_browser_launch_error(RuntimeError("Executable doesn't exist at /tmp/headless_shell"))

    assert "python -m playwright install chromium" in message
    assert "Executable doesn't exist" in message


class _FakeBrowserSession:
    def __init__(self) -> None:
        self.actions: list[BrowserAction] = []

    async def execute(self, action: BrowserAction) -> ToolResult:
        self.actions.append(action)
        if action.action == "extract_text":
            return ToolResult(content="page text", metadata={"action": action.action})
        return ToolResult(content=f"ok:{action.action}", metadata={"action": action.action})


class _FakeLoginSession(BrowserSession):
    def __init__(self) -> None:
        super().__init__()
        self.page = _FakeLoginPage()
        self.launched_headless: bool | None = None

    async def _ensure_page(self, *, headless: bool):
        self.launched_headless = headless
        self._headless = headless
        self._page = self.page
        return self.page


class _FakeLoginPage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.goto_calls: list[tuple[str, str, int]] = []
        self._checks = 0

    async def goto(self, url: str, *, wait_until: str, timeout: int):
        self.url = url
        self.goto_calls.append((url, wait_until, timeout))

    async def title(self) -> str:
        return "Dashboard"

    def locator(self, selector: str):
        return _FakeLoginLocator(self, selector)

    async def wait_for_timeout(self, _timeout_ms: int) -> None:
        self._checks += 1
        self.url = "https://example.com/dashboard"


class _FakeLoginLocator:
    def __init__(self, page: _FakeLoginPage, selector: str) -> None:
        self.page = page
        self.selector = selector

    async def count(self) -> int:
        return 1 if self.selector == ".account-menu" and self.page.url.endswith("/dashboard") else 0


class _FakeMultiMatchSession(BrowserSession):
    def __init__(self) -> None:
        super().__init__()
        self.locator = _FakeMultiMatchLocator()
        self._page = _FakeMultiMatchPage(self.locator)


class _FakeMultiMatchLocator:
    def __init__(self) -> None:
        self.selector = ""
        self.first = self
        self.waited_timeout: int | None = None

    async def wait_for(self, *, timeout: int) -> None:
        self.waited_timeout = timeout

    async def count(self) -> int:
        return 2

    async def all_inner_texts(self) -> list[str]:
        return ["title", "", "body"]


class _FakeMultiMatchPage:
    def __init__(self, locator: _FakeMultiMatchLocator) -> None:
        self._locator = locator

    def locator(self, selector: str):
        self._locator.selector = selector
        return self._locator


class _StubConfig:
    def __init__(self, tools_buildin: dict[str, object]) -> None:
        self.tools_buildin = tools_buildin

    def get(self, name: str, default: object = None) -> object:
        if name == "tools_buildin":
            return self.tools_buildin
        return default
