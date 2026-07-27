"""Single browser automation tool backed by Playwright."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from bamboo.helpers.config import BambooConfig
from bamboo.tools.buildin.base import Tool, ToolResult
from bamboo.userspace.userspace import get_userspace_dir

BROWSER_ACTIONS = {
    "open",
    "click",
    "type",
    "press",
    "screenshot",
    "extract_text",
    "eval",
    "wait_for",
    "wait_for_login",
    "close",
}


class BrowserTool(Tool):
    """Operate one process-local browser page through an action parameter."""

    name = "browser"
    description = (
        "Operate a browser page using Playwright. Use action=open/click/type/press/screenshot/"
        "extract_text/eval/wait_for/wait_for_login/close with the matching parameters."
    )
    risk_level = "unknown"
    tags = ("browser", "web", "automation")

    def __init__(self, *, session: BrowserSession | None = None) -> None:
        self.session = session or get_browser_session()

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": sorted(BROWSER_ACTIONS),
                    "description": "Browser action to perform.",
                },
                "url": {"type": "string", "description": "URL for action=open, or optional login URL for action=wait_for_login."},
                "selector": {"type": "string", "description": "CSS/text selector for click/type/wait_for/extract_text. For wait_for_login, a selector that appears after login succeeds."},
                "text": {"type": "string", "description": "Text for action=type."},
                "key": {"type": "string", "description": "Keyboard key for action=press, e.g. Enter."},
                "script": {"type": "string", "description": "JavaScript expression/function for action=eval. For wait_for_login, a predicate returning true when login is complete."},
                "url_pattern": {"type": "string", "description": "Regex that current URL must match for action=wait_for_login."},
                "timeout_ms": {"type": "integer", "description": "Action timeout in milliseconds."},
                "wait_until": {
                    "type": "string",
                    "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                    "description": "Navigation wait condition for action=open.",
                },
                "screenshot_path": {"type": "string", "description": "Optional output path for action=screenshot."},
                "full_page": {"type": "boolean", "description": "Capture full page for action=screenshot."},
                "headless": {"type": "boolean", "description": "Launch browser in headless mode."},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        url: str = "",
        selector: str = "",
        text: str = "",
        key: str = "",
        script: str = "",
        url_pattern: str = "",
        timeout_ms: int = 10000,
        wait_until: str = "load",
        screenshot_path: str = "",
        full_page: bool = True,
        headless: bool | None = None,
    ) -> ToolResult:
        normalized_action = action.strip().lower()
        if normalized_action not in BROWSER_ACTIONS:
            return ToolResult(
                content=f"Unsupported browser action: {action}",
                success=False,
                error="unsupported_browser_action",
                metadata={"supported_actions": sorted(BROWSER_ACTIONS)},
            )
        try:
            effective_timeout = _login_timeout(timeout_ms) if normalized_action == "wait_for_login" else _timeout(timeout_ms)
            result = await self.session.execute(
                BrowserAction(
                    action=normalized_action,
                    url=url,
                    selector=selector,
                    text=text,
                    key=key,
                    script=script,
                    url_pattern=url_pattern,
                    timeout_ms=effective_timeout,
                    wait_until=wait_until or "load",
                    screenshot_path=screenshot_path,
                    full_page=full_page,
                    headless=_browser_headless_default() if headless is None else bool(headless),
                )
            )
        except BrowserToolError as exc:
            return ToolResult(content=str(exc), success=False, error=exc.error)
        return result


@dataclass(frozen=True, slots=True)
class BrowserAction:
    """Normalized browser action parameters."""

    action: str
    url: str = ""
    selector: str = ""
    text: str = ""
    key: str = ""
    script: str = ""
    url_pattern: str = ""
    timeout_ms: int = 10000
    wait_until: str = "load"
    screenshot_path: str = ""
    full_page: bool = True
    headless: bool = True


class BrowserToolError(RuntimeError):
    """Expected browser tool failure."""

    def __init__(self, message: str, *, error: str) -> None:
        super().__init__(message)
        self.error = error


class BrowserSession:
    """Lazy Playwright browser session with one active page."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._headless: bool | None = None

    async def execute(self, action: BrowserAction) -> ToolResult:
        """Dispatch one browser action."""
        if action.action == "open":
            return await self._open(action)
        if action.action == "click":
            return await self._click(action)
        if action.action == "type":
            return await self._type(action)
        if action.action == "press":
            return await self._press(action)
        if action.action == "screenshot":
            return await self._screenshot(action)
        if action.action == "extract_text":
            return await self._extract_text(action)
        if action.action == "eval":
            return await self._eval(action)
        if action.action == "wait_for":
            return await self._wait_for(action)
        if action.action == "wait_for_login":
            return await self._wait_for_login(action)
        if action.action == "close":
            return await self.close()
        raise BrowserToolError(f"Unsupported browser action: {action.action}", error="unsupported_browser_action")

    async def _ensure_page(self, *, headless: bool) -> Any:
        if self._page is not None:
            return self._page
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserToolError(
                "Playwright is not installed. Install project dependencies with playwright support first.",
                error="playwright_missing",
            ) from exc
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)
            self._headless = headless
            self._page = await self._browser.new_page()
            return self._page
        except Exception as exc:
            await self.close()
            raise BrowserToolError(
                _format_browser_launch_error(exc),
                error="browser_launch_failed",
            ) from exc

    async def _open(self, action: BrowserAction) -> ToolResult:
        if not action.url.strip():
            raise BrowserToolError("browser action=open requires url.", error="missing_url")
        page = await self._ensure_page(headless=action.headless)
        response = await page.goto(action.url, wait_until=action.wait_until, timeout=action.timeout_ms)
        title = await page.title()
        current_url = page.url
        status = getattr(response, "status", None) if response is not None else None
        return ToolResult(
            content=f"Opened {current_url}\ntitle: {title}\nstatus: {status or 'n/a'}",
            metadata={"action": "open", "url": current_url, "title": title, "status": status},
        )

    async def _click(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        selector = _require_selector(action)
        await page.locator(selector).click(timeout=action.timeout_ms)
        return ToolResult(content=f"Clicked `{selector}`.", metadata={"action": "click", "selector": selector})

    async def _type(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        selector = _require_selector(action)
        await page.locator(selector).fill(action.text, timeout=action.timeout_ms)
        return ToolResult(
            content=f"Typed {len(action.text)} characters into `{selector}`.",
            metadata={"action": "type", "selector": selector, "text_length": len(action.text)},
        )

    async def _press(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        if not action.key.strip():
            raise BrowserToolError("browser action=press requires key.", error="missing_key")
        target = page.locator(action.selector) if action.selector.strip() else page
        await target.press(action.key, timeout=action.timeout_ms)
        return ToolResult(content=f"Pressed `{action.key}`.", metadata={"action": "press", "key": action.key})

    async def _screenshot(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        path = _screenshot_path(action.screenshot_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(path), full_page=action.full_page, timeout=action.timeout_ms)
        return ToolResult(
            content=f"Saved screenshot to {path}",
            metadata={"action": "screenshot", "path": str(path), "full_page": action.full_page},
        )

    async def _extract_text(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        selector = action.selector.strip() or "body"
        text = await page.locator(selector).inner_text(timeout=action.timeout_ms)
        return ToolResult(
            content=text,
            metadata={"action": "extract_text", "selector": selector, "length": len(text)},
        )

    async def _eval(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        if not action.script.strip():
            raise BrowserToolError("browser action=eval requires script.", error="missing_script")
        value = await page.evaluate(action.script)
        return ToolResult(
            content=_stringify_eval_result(value),
            metadata={"action": "eval"},
        )

    async def _wait_for(self, action: BrowserAction) -> ToolResult:
        page = await self._require_page(action)
        if action.selector.strip():
            await page.locator(action.selector).wait_for(timeout=action.timeout_ms)
            return ToolResult(
                content=f"Waited for `{action.selector}`.",
                metadata={"action": "wait_for", "selector": action.selector},
            )
        await page.wait_for_timeout(action.timeout_ms)
        return ToolResult(content=f"Waited {action.timeout_ms} ms.", metadata={"action": "wait_for"})

    async def _wait_for_login(self, action: BrowserAction) -> ToolResult:
        if self._page is None:
            if not action.url.strip():
                raise BrowserToolError("No browser page is open. Provide url or call browser with action=open first.", error="page_not_open")
            page = await self._ensure_page(headless=action.headless)
        else:
            page = await self._require_page(action)
        if self._headless:
            raise BrowserToolError(
                "browser action=wait_for_login requires a visible browser. Set browser.headless: false in tools_buildin.yaml or open the page with headless=false.",
                error="login_requires_headful_browser",
            )
        if action.url.strip():
            await page.goto(action.url, wait_until=action.wait_until, timeout=action.timeout_ms)
        deadline = asyncio.get_running_loop().time() + (action.timeout_ms / 1000)
        start_url = page.url
        while asyncio.get_running_loop().time() < deadline:
            if await self._login_completed(page, action, start_url):
                title = await page.title()
                return ToolResult(
                    content=f"Login appears complete.\nurl: {page.url}\ntitle: {title}",
                    metadata={
                        "action": "wait_for_login",
                        "url": page.url,
                        "title": title,
                        "timeout_ms": action.timeout_ms,
                    },
                )
            await page.wait_for_timeout(1000)
        raise BrowserToolError(
            f"Timed out after {action.timeout_ms} ms waiting for user login.",
            error="login_wait_timeout",
        )

    async def _login_completed(self, page: Any, action: BrowserAction, start_url: str) -> bool:
        if action.selector.strip():
            try:
                if await page.locator(action.selector).count() > 0:
                    return True
            except Exception:
                pass
        if action.script.strip():
            try:
                if bool(await page.evaluate(action.script)):
                    return True
            except Exception:
                pass
        if action.url_pattern.strip():
            try:
                if re.search(action.url_pattern, page.url):
                    return True
            except re.error as exc:
                raise BrowserToolError(f"Invalid wait_for_login url_pattern: {exc}", error="invalid_url_pattern") from exc
        if action.selector.strip() or action.script.strip() or action.url_pattern.strip():
            return False
        try:
            password_count = await page.locator("input[type='password']").count()
        except Exception:
            password_count = 0
        return page.url != start_url and not _looks_like_login_url(page.url) and password_count == 0

    async def _require_page(self, action: BrowserAction) -> Any:
        if self._page is None:
            raise BrowserToolError("No browser page is open. Call browser with action=open first.", error="page_not_open")
        return self._page

    async def close(self) -> ToolResult:
        if self._page is not None:
            await self._page.close()
            self._page = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        return ToolResult(content="Closed browser.", metadata={"action": "close"})


_browser_session: BrowserSession | None = None


def get_browser_session() -> BrowserSession:
    """Return the process-local browser session."""
    global _browser_session
    if _browser_session is None:
        _browser_session = BrowserSession()
    return _browser_session


def reset_browser_session() -> None:
    """Reset the process-local browser session for tests."""
    global _browser_session
    _browser_session = None


def _timeout(value: int) -> int:
    return max(100, min(int(value or 10000), 120000))


def _login_timeout(value: int) -> int:
    if value == 10000:
        value = 300000
    return max(1000, min(int(value or 300000), 900000))


def _looks_like_login_url(url: str) -> bool:
    normalized = url.lower()
    return any(marker in normalized for marker in ("login", "signin", "sign-in", "auth", "oauth", "sso"))


def _browser_headless_default() -> bool:
    """Load the default browser launch mode from tools_buildin.yaml."""
    try:
        tools_config = BambooConfig().get("tools_buildin", {})
    except Exception:
        return True
    if not isinstance(tools_config, dict):
        return True
    browser_config = tools_config.get("browser", {})
    if not isinstance(browser_config, dict):
        return True
    return _as_bool(browser_config.get("headless"), default=True)


def _as_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _require_selector(action: BrowserAction) -> str:
    selector = action.selector.strip()
    if not selector:
        raise BrowserToolError(f"browser action={action.action} requires selector.", error="missing_selector")
    return selector


def _screenshot_path(raw_path: str) -> Path:
    if raw_path.strip():
        return Path(raw_path).expanduser().resolve()
    return (
        get_userspace_dir()
        / "workspace"
        / "browser-screenshots"
        / f"browser-{uuid4().hex}.png"
    )


def _stringify_eval_result(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)


def _format_browser_launch_error(exc: Exception) -> str:
    detail = str(exc).strip()
    lines = [
        "Failed to launch Playwright browser.",
        "Install the browser runtime with: `python -m playwright install chromium`.",
    ]
    if detail:
        lines.append(f"Underlying error: {detail}")
    return "\n".join(lines)
