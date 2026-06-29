"""把完整会话记录持久化到 Bamboo memory 目录。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(UTC).isoformat()


class SessionMemoryStore:
    """保存完整对话、system prompt 和压缩记录。"""

    def __init__(self, *, memory_dir: Path, session_id: str, record_dir: Path | None = None) -> None:
        """初始化指定 Session 的 memory 存储目录。"""
        self.memory_dir = memory_dir
        self.session_id = session_id
        self.session_dir = record_dir or memory_dir / session_id
        self.enabled = True
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.enabled = False

    def save_session(
        self,
        *,
        mode: str,
        project_root: Path,
        model: str,
        provider: str,
        system_prompt: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """保存会话元信息和完整 system prompt。"""
        if not self.enabled:
            return
        now = utc_now()
        session_json = self.session_dir / "session.json"
        existing = self._read_json(session_json) or {}
        created_at = str(existing.get("created_at") or now)
        payload = {
            "schema_version": 1,
            "session_id": self.session_id,
            "mode": mode,
            "project_root": str(project_root),
            "memory_dir": str(self.memory_dir),
            "record_dir": str(self.session_dir),
            "model": model,
            "provider": provider,
            "created_at": created_at,
            "updated_at": now,
            "system_prompt_file": "system_prompt.md",
            "metadata": metadata or {},
        }
        self._write_json(session_json, payload)
        (self.session_dir / "system_prompt.md").write_text(system_prompt, encoding="utf-8")

    def append_message(self, message: Any, *, task_id: str = "", extra: dict[str, Any] | None = None) -> None:
        """追加保存一条完整消息。"""
        if not self.enabled:
            return
        payload = {
            "schema_version": 1,
            "type": "message",
            "time": getattr(message, "created_at", "") or utc_now(),
            "session_id": self.session_id,
            "task_id": task_id,
            "message_id": message.message_id,
            "role": message.role,
            "content": message.content,
            "agent_name": message.agent_name,
            "message_type": message.message_type,
            "active_for_prompt": message.active_for_prompt,
            "compressed": message.compressed,
            "origin_message_ids": list(message.origin_message_ids),
            "metadata": dict(message.metadata),
            "tool_calls": [self._to_plain(tool_call) for tool_call in message.tool_calls],
            "tool_call_id": message.tool_call_id,
            "tool_name": message.tool_name,
        }
        if extra:
            payload.update(extra)
        self._append_jsonl(
            self.session_dir / "messages.jsonl",
            payload,
        )

    def build_compaction_payload(
        self,
        *,
        selected_messages: list[Any],
        summary_message: Any,
        summary: str,
        agent_name: str,
        after_active_message_ids: list[str],
    ) -> dict[str, Any]:
        """构建一次压缩前后完整记录。"""
        return {
            "schema_version": 1,
            "type": "compaction",
            "time": utc_now(),
            "session_id": self.session_id,
            "agent_name": agent_name,
            "before_message_ids": [message.message_id for message in selected_messages],
            "before_messages": [self.message_snapshot(message) for message in selected_messages],
            "summary_message_id": summary_message.message_id,
            "summary": summary,
            "summary_message": self.message_snapshot(summary_message),
            "after_active_message_ids": after_active_message_ids,
        }

    def append_compaction(self, payload: dict[str, Any]) -> None:
        """追加保存一次压缩前后完整记录。"""
        if not self.enabled:
            return
        self._append_jsonl(self.session_dir / "compactions.jsonl", payload)

    def message_snapshot(self, message: Any) -> dict[str, Any]:
        """生成一条完整消息快照。"""
        return {
            "message_id": message.message_id,
            "time": getattr(message, "created_at", ""),
            "role": message.role,
            "content": message.content,
            "agent_name": message.agent_name,
            "message_type": message.message_type,
            "active_for_prompt": message.active_for_prompt,
            "compressed": message.compressed,
            "origin_message_ids": list(message.origin_message_ids),
            "metadata": dict(message.metadata),
            "tool_calls": [self._to_plain(tool_call) for tool_call in message.tool_calls],
            "tool_call_id": message.tool_call_id,
            "tool_name": message.tool_name,
        }

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(path)

    def _to_plain(self, value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return value
        return str(value)


def current_time_record_name() -> str:
    """返回用于 chat 记录目录名的当前时间。"""
    return datetime.now().strftime("%H-%M-%S-%f")
