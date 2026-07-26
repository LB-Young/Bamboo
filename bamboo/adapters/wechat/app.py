"""WeChat iLink adapter for Bamboo.

This adapter provides a personal WeChat bot frontend using the same iLink
protocol shape used by GenericAgent. The first version focuses on text
messages: QR login, long polling, sending user text to Bamboo, and replying
with the final task output.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import anyio
import httpx

from bamboo.adapters.cli.commands import expand_command_message
from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.logging import get_logger, setup_logging
from bamboo.helpers.requests_params import RunParams
from bamboo.runtime import TaskRuntime

API_BASE = "https://ilinkai.weixin.qq.com"
TOKEN_FILE = Path.home() / ".wxbot" / "token.json"
VERSION = "2.1.10"
ILINK_APP_ID = "bot"
ILINK_APP_CLIENT_VERSION = (2 << 16) | (1 << 8) | 10
USER_AGENT = f"bamboo-weixin/{VERSION}"
MSG_USER = 1
MSG_BOT = 2
ITEM_TEXT = 1
STATE_FINISH = 2


class WeChatAuthExpired(Exception):
    """Raised when the stored iLink token is expired or invalid."""


class WeChatBotClient:
    """Small synchronous client for the WeChat iLink bot endpoints."""

    def __init__(
        self,
        *,
        api_base: str = API_BASE,
        token_file: Path | None = None,
        token: str = "",
        bot_id: str = "",
        timeout: float = 15.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.token_file = token_file or TOKEN_FILE
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token = token
        self.bot_id = bot_id
        self.updates_buf = ""
        self.timeout = timeout
        if not self.token:
            self._load()

    def _load(self) -> None:
        if not self.token_file.is_file():
            return
        try:
            payload = httpx.Response(200, content=self.token_file.read_bytes()).json()
        except Exception:
            return
        self.token = str(payload.get("bot_token", ""))
        self.bot_id = str(payload.get("ilink_bot_id", ""))
        self.updates_buf = str(payload.get("updates_buf", ""))

    def _save(self, **extra: Any) -> None:
        import json

        payload = {
            "bot_token": self.token or "",
            "ilink_bot_id": self.bot_id or "",
            "updates_buf": self.updates_buf or "",
            **extra,
        }
        self.token_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _post(self, endpoint: str, body: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        import base64
        import struct

        data = body
        random_uin = base64.b64encode(str(struct.unpack(">I", os.urandom(4))[0]).encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": random_uin,
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
            "User-Agent": USER_AGENT,
        }
        if self.token.strip():
            headers["Authorization"] = f"Bearer {self.token.strip()}"
        with httpx.Client(timeout=timeout or self.timeout, trust_env=False) as client:
            response = client.post(f"{self.api_base}/{endpoint}", json=data, headers=headers)
            response.raise_for_status()
            return response.json()

    def login_qr(self, *, poll_interval: float = 2.0) -> dict[str, Any]:
        """Login with a WeChat-scannable QR code and persist the token."""
        qrcode_payload: dict[str, Any] = {}
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            for attempt in range(6):
                response = client.get(
                    f"{self.api_base}/ilink/bot/get_bot_qrcode",
                    params={"bot_type": 3},
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                qrcode_payload = response.json()
                if qrcode_payload.get("qrcode") and qrcode_payload.get("qrcode_img_content"):
                    break
                wait = 2**attempt
                print(f"[WeChat] QR code not ready, retrying in {wait}s...")
                time.sleep(wait)

            qr_id = str(qrcode_payload.get("qrcode", ""))
            url = str(qrcode_payload.get("qrcode_img_content", ""))
            if not qr_id or not url:
                raise RuntimeError("failed to obtain WeChat QR code")

            print(f"[WeChat] QR id: {qr_id}")
            _print_qr(url)
            last_status = ""
            while True:
                time.sleep(poll_interval)
                try:
                    status_response = client.get(
                        f"{self.api_base}/ilink/bot/get_qrcode_status",
                        params={"qrcode": qr_id},
                        headers={"User-Agent": USER_AGENT},
                        timeout=60.0,
                    )
                    payload = status_response.json()
                except (httpx.HTTPError, ValueError):
                    continue
                status = str(payload.get("status", ""))
                if status != last_status:
                    print(f"[WeChat] QR status: {status}")
                    last_status = status
                if status == "confirmed":
                    self.token = str(payload.get("bot_token", ""))
                    self.bot_id = str(payload.get("ilink_bot_id", ""))
                    self._save(login_time=time.strftime("%Y-%m-%d %H:%M:%S"))
                    print(f"[WeChat] login successful bot_id={self.bot_id}")
                    return payload
                if status == "expired":
                    raise RuntimeError("WeChat QR code expired")

    def get_updates(self, *, timeout: float = 30.0) -> list[dict[str, Any]]:
        try:
            payload = self._post(
                "ilink/bot/getupdates",
                {
                    "get_updates_buf": self.updates_buf or "",
                    "base_info": {"channel_version": VERSION},
                },
                timeout=timeout + 5,
            )
        except httpx.ReadTimeout:
            return []
        if payload.get("errcode"):
            errcode = payload.get("errcode")
            print(f"[WeChat] getupdates error: {errcode} {payload.get('errmsg', '')}")
            if errcode == -14:
                self.updates_buf = ""
                self.token = ""
                self.bot_id = ""
                self._save(bot_token="", ilink_bot_id="")
                raise WeChatAuthExpired(str(payload.get("errmsg", "")))
            return []
        next_buf = str(payload.get("get_updates_buf", ""))
        if next_buf:
            self.updates_buf = next_buf
            self._save()
        messages = payload.get("msgs") or []
        return [message for message in messages if isinstance(message, dict)]

    def send_text(self, to_user_id: str, text: str, *, context_token: str = "") -> dict[str, Any]:
        message = {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": f"pyclient-{uuid.uuid4().hex[:16]}",
            "message_type": MSG_BOT,
            "message_state": STATE_FINISH,
            "item_list": [{"type": ITEM_TEXT, "text_item": {"text": text}}],
        }
        if context_token:
            message["context_token"] = context_token
        return self._post(
            "ilink/bot/sendmessage",
            {"msg": message, "base_info": {"channel_version": VERSION}},
        )

    @staticmethod
    def extract_text(message: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in message.get("item_list", []) or []:
            if not isinstance(item, dict) or item.get("type") != ITEM_TEXT:
                continue
            text_item = item.get("text_item")
            if isinstance(text_item, dict):
                text = str(text_item.get("text", ""))
                if text:
                    parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def is_user_message(message: dict[str, Any]) -> bool:
        return message.get("message_type") == MSG_USER

    def run_loop(self, on_message: Callable[[dict[str, Any]], None], *, poll_timeout: float = 30.0) -> None:
        print(f"[WeChat] listening bot_id={self.bot_id}")
        seen: list[str] = []
        seen_set: set[str] = set()
        while True:
            try:
                for message in self.get_updates(timeout=poll_timeout):
                    message_id = str(message.get("message_id", ""))
                    if not self.is_user_message(message) or message_id in seen_set:
                        continue
                    seen.append(message_id)
                    seen_set.add(message_id)
                    if len(seen) > 5000:
                        seen = seen[-2000:]
                        seen_set = set(seen)
                    on_message(message)
            except KeyboardInterrupt:
                print("[WeChat] exiting")
                break
            except WeChatAuthExpired:
                raise
            except Exception as exc:
                print(f"[WeChat] loop error: {exc}; retrying in 5s")
                time.sleep(5)


@dataclass(slots=True)
class WeChatAdapterConfig:
    project: Path
    model: str = ""
    provider: str = ""
    permission: str = "default"
    session_mode: SessionMode | str = SessionMode.chat
    yes_all: bool = False
    relogin: bool = False


class BambooWeChatAdapter:
    """Bridge WeChat messages into Bamboo tasks."""

    def __init__(
        self,
        *,
        client: WeChatBotClient | None = None,
        runtime: TaskRuntime | None = None,
        config: WeChatAdapterConfig | None = None,
    ) -> None:
        self.client = client or WeChatBotClient()
        self.runtime = runtime or TaskRuntime()
        self.config = config or WeChatAdapterConfig(project=Path.cwd())
        self.sessions: dict[str, Task] = {}
        self.user_locks: dict[str, threading.Lock] = {}
        self.lock = threading.Lock()
        self.log = get_logger("wechat")

    def start(self) -> None:
        if self.config.relogin or not self.client.token:
            self.client.login_qr()
        self.client.run_loop(self.on_message)

    def on_message(self, message: dict[str, Any]) -> None:
        text = self.client.extract_text(message).strip()
        user_id = str(message.get("from_user_id", ""))
        context_token = str(message.get("context_token", ""))
        if not text or not user_id:
            return
        threading.Thread(
            target=self._handle_message,
            args=(user_id, context_token, text),
            daemon=True,
        ).start()

    def _handle_message(self, user_id: str, context_token: str, text: str) -> None:
        user_lock = self._user_lock(user_id)
        if not user_lock.acquire(blocking=False):
            self._send(user_id, "上一条消息还在处理中，请稍后再发。", context_token=context_token)
            return
        try:
            if text in {"/new", "/reset"}:
                self.sessions.pop(user_id, None)
                self._send(user_id, "已开启新的 Bamboo 会话。", context_token=context_token)
                return
            if text in {"/help", "help"}:
                self._send(
                    user_id,
                    "Bamboo 微信入口已连接。\n/new 开启新会话\n/reset 重置当前会话\n直接发送文本即可提问。",
                    context_token=context_token,
                )
                return
            output = anyio.run(self._run_turn, user_id, text)
            self._send_chunks(user_id, output or "[Bamboo 没有返回文本输出]", context_token=context_token)
        except Exception as exc:
            self.log.exception("wechat message failed user_id={user_id}", user_id=user_id)
            self._send(user_id, f"Bamboo 执行失败：{exc}", context_token=context_token)
        finally:
            user_lock.release()

    async def _run_turn(self, user_id: str, text: str) -> str:
        expanded = expand_command_message(text, project=str(self.config.project))
        if expanded.error:
            return expanded.error
        message = expanded.message if expanded.expanded else text
        previous = self.sessions.get(user_id)
        if previous is None:
            params = RunParams(
                platform="wechat",
                message=message,
                project=str(self.config.project),
                model=self.config.model,
                provider=self.config.provider,
                permission=self.config.permission,
                yes_all=self.config.yes_all,
                session_mode=self.config.session_mode,
            )
            task = self.runtime.create_task(params)
        else:
            task = self.runtime.create_followup_task(previous, message)
        completed = await self.runtime.run_existing_task(task)
        self.sessions[user_id] = completed
        return completed.output

    def _user_lock(self, user_id: str) -> threading.Lock:
        with self.lock:
            lock = self.user_locks.get(user_id)
            if lock is None:
                lock = threading.Lock()
                self.user_locks[user_id] = lock
            return lock

    def _send_chunks(self, user_id: str, text: str, *, context_token: str = "") -> None:
        for chunk in _chunk_text(text, max_chars=3000):
            self._send(user_id, chunk, context_token=context_token)

    def _send(self, user_id: str, text: str, *, context_token: str = "") -> None:
        self.client.send_text(user_id, text, context_token=context_token)


def launch_wechat(
    *,
    project: Path | None = None,
    model: str = "",
    provider: str = "",
    permission: str = "default",
    session_mode: SessionMode | str = SessionMode.chat,
    yes_all: bool = False,
    relogin: bool = False,
) -> None:
    """Start the Bamboo WeChat bot frontend."""
    setup_logging()
    config = WeChatAdapterConfig(
        project=(project or Path.cwd()).expanduser().resolve(strict=False),
        model=model,
        provider=provider,
        permission=permission,
        session_mode=session_mode,
        yes_all=yes_all,
        relogin=relogin,
    )
    BambooWeChatAdapter(config=config).start()


def _print_qr(url: str) -> None:
    try:
        import qrcode
    except ImportError:
        print("[WeChat] install qrcode to print an ASCII QR code, or open this URL in WeChat:")
        print(url)
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(out=sys.stdout, invert=True)


def _chunk_text(text: str, *, max_chars: int) -> list[str]:
    content = text.strip()
    if not content:
        return []
    chunks: list[str] = []
    while len(content) > max_chars:
        split_at = content.rfind("\n\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = content.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(content[:split_at].strip())
        content = content[split_at:].strip()
    if content:
        chunks.append(content)
    return chunks
