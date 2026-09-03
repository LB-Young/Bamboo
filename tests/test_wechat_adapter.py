from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from bamboo.adapters.output_images import OutputImage, extract_output_images, text_without_output_image_markdown
from bamboo.adapters.wechat.app import (
    ITEM_IMAGE,
    ITEM_TEXT,
    MSG_USER,
    BambooWeChatAdapter,
    WeChatAdapterConfig,
    WeChatBotClient,
    _chunk_text,
    _preview_text,
    _short_user_id,
)
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


def test_wechat_command_defaults_to_bypass_permission(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("bamboo.run._start_default_cron", lambda: None)
    monkeypatch.setattr("bamboo.adapters.wechat.launch_wechat", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(app, ["wechat"])

    assert result.exit_code == 0
    assert "permission=bypass" in result.output
    assert "--permission default/read-only/bypass/yolo" in result.output
    assert calls[0]["permission"] == "bypass"


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


def test_output_image_extraction_supports_markdown_and_bare_paths(tmp_path: Path) -> None:
    local_image = tmp_path / "chart.png"
    text = f"结果如下：\n![chart]({local_image})\n另一个图 /tmp/report.jpeg\nhttps://asset.test/a.webp?x=1\\nSaved"

    images = extract_output_images(text)

    assert [image.source for image in images] == [
        str(local_image),
        str(Path("/tmp/report.jpeg").resolve(strict=False)),
        "https://asset.test/a.webp?x=1",
    ]
    assert text_without_output_image_markdown(text) == "结果如下：\n另一个图 /tmp/report.jpeg\nhttps://asset.test/a.webp?x=1\\nSaved"


def test_wechat_final_output_sends_text_then_images(tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.sent: list[tuple[str, str]] = []

        def send_text(self, to_user_id: str, text: str, *, context_token: str = "") -> dict[str, object]:
            self.sent.append(("text", text))
            return {"ok": True}

        def send_image(self, to_user_id: str, image, *, context_token: str = "") -> dict[str, object]:
            self.sent.append(("image", image.source))
            return {"ok": True}

    image_path = tmp_path / "result.png"
    image_path.write_bytes(b"png")
    client = FakeClient()
    adapter = BambooWeChatAdapter(
        client=client,  # type: ignore[arg-type]
        runtime=None,  # type: ignore[arg-type]
        config=WeChatAdapterConfig(project=tmp_path),
    )

    adapter._send_final_output("user-1", f"完成\n![result]({image_path})", context_token="ctx")

    assert client.sent == [("text", "完成"), ("image", str(image_path))]


def test_wechat_send_image_builds_ilink_thumbnail_media(tmp_path: Path) -> None:
    class FakeClient(WeChatBotClient):
        def __init__(self) -> None:
            super().__init__(token="token", token_file=tmp_path / "token.json")
            self.posts: list[tuple[str, dict[str, Any]]] = []

        def _post(self, endpoint: str, body: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
            self.posts.append((endpoint, body))
            if endpoint == "ilink/bot/getuploadurl":
                return {
                    "upload_param": "main-upload",
                    "thumb_upload_param": "thumb-upload",
                }
            return {"ok": True}

        def _upload_media_content(
            self,
            *,
            file_key: str,
            upload_param: str,
            raw: bytes,
            aes_key: bytes,
            upload_url: str = "",
        ) -> dict[str, Any]:
            return {
                "encrypt_query_param": f"eq-{upload_param}",
                "aes_key": base64.b64encode(aes_key.hex().encode("ascii")).decode("ascii"),
                "encrypt_type": 1,
            }

    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    )

    client = FakeClient()
    client.send_image("user-1", OutputImage(source=str(image_path), is_local=True), context_token="ctx")

    upload_body = client.posts[0][1]
    assert upload_body["to_user_id"] == "user-1"
    assert upload_body["rawsize"] == image_path.stat().st_size
    assert upload_body["filesize"] % 16 == 0
    assert upload_body["thumb_rawsize"] > 0
    assert upload_body["thumb_filesize"] % 16 == 0
    assert upload_body["no_need_thumb"] is False
    send_body = client.posts[1][1]["msg"]
    image_item = send_body["item_list"][0]["image_item"]
    assert send_body["context_token"] == "ctx"
    assert send_body["item_list"][0]["type"] == ITEM_IMAGE
    assert image_item["media"]["encrypt_query_param"] == "eq-main-upload"
    assert image_item["thumb_media"]["encrypt_query_param"] == "eq-thumb-upload"
    assert image_item["thumb_size"] > 0


def test_wechat_chunk_text_prefers_line_boundaries() -> None:
    chunks = _chunk_text("alpha\n\nbeta\n\ngamma", max_chars=12)

    assert chunks == ["alpha\n\nbeta", "gamma"]


def test_wechat_log_helpers_keep_output_compact() -> None:
    assert _short_user_id("abcdef1234567890") == "abcdef...7890"
    assert _preview_text("hello\nworld") == "'hello world'"
    assert _preview_text("x" * 90, max_chars=12) == "'xxxxxxxxx...'"
