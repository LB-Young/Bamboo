from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from bamboo.adapters.wechat.app import ITEM_TEXT, MSG_USER, WeChatBotClient, _chunk_text
from bamboo.helpers.constant import SessionMode
from bamboo.run import app


def test_wechat_command_launches_adapter(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    cron_started: list[bool] = []
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: cron_started.append(True))
    monkeypatch.setattr("bamboo.adapters.wechat.launch_wechat", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        app,
        [
            "wechat",
            "--project",
            "/tmp/project",
            "--model",
            "kimi-k3",
            "--provider",
            "kimi",
            "--permission",
            "default",
            "--session-mode",
            "project",
            "--yes",
            "--relogin",
        ],
    )

    assert result.exit_code == 0
    assert cron_started == [True]
    assert calls == [
        {
            "project": Path("/tmp/project"),
            "model": "kimi-k3",
            "provider": "kimi",
            "permission": "default",
            "session_mode": SessionMode.project,
            "yes_all": True,
            "relogin": True,
        }
    ]


def test_wechat_client_extracts_text_items() -> None:
    message = {
        "message_type": MSG_USER,
        "item_list": [
            {"type": ITEM_TEXT, "text_item": {"text": "hello"}},
            {"type": 99, "text_item": {"text": "ignored"}},
            {"type": ITEM_TEXT, "text_item": {"text": "world"}},
        ],
    }

    assert WeChatBotClient.is_user_message(message)
    assert WeChatBotClient.extract_text(message) == "hello\nworld"


def test_wechat_chunk_text_prefers_line_boundaries() -> None:
    chunks = _chunk_text("alpha\n\nbeta\n\ngamma", max_chars=12)

    assert chunks == ["alpha\n\nbeta", "gamma"]
