"""把完整会话记录持久化到 Bamboo memory 目录。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bamboo.helpers.redact import redact_sensitive_text


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

    def append_event(self, event: Any) -> None:
        """追加保存一条运行时事件。"""
        if not self.enabled:
            return
        if hasattr(event, "to_dict"):
            payload = event.to_dict()
        elif isinstance(event, dict):
            payload = dict(event)
        else:
            payload = {"type": type(event).__name__, "value": self._to_plain(event)}
        payload.setdefault("schema_version", 1)
        payload.setdefault("time", utc_now())
        self._append_jsonl(self.session_dir / "events.jsonl", self._to_jsonable(payload))

    def append_task(self, task: Any, *, action: str) -> None:
        """追加保存一条任务生命周期快照。"""
        if not self.enabled:
            return
        payload = {
            "schema_version": 1,
            "type": "task",
            "time": utc_now(),
            "action": action,
            "session_id": getattr(task, "session_id", self.session_id),
            "task_id": getattr(task, "task_id", ""),
            "status": getattr(task, "status", ""),
            "platform": getattr(task, "platform", ""),
            "user_query": getattr(task, "user_query", ""),
            "output": getattr(task, "output", ""),
            "error": getattr(task, "error", ""),
            "metadata": dict(getattr(task, "metadata", {}) or {}),
        }
        self._append_jsonl(self.session_dir / "tasks.jsonl", payload)

    def append_turn(self, task: Any) -> None:
        """追加保存一次用户请求对应的 turn 级源日志。"""
        if not self.enabled:
            return
        task_id = getattr(task, "task_id", "")
        session = getattr(task, "session", None)
        messages = list(getattr(session, "messages", []) or [])
        task_messages = [
            message
            for message in messages
            if (getattr(message, "metadata", {}) or {}).get("task_id") == task_id
            and getattr(message, "message_type", "") != "compaction"
        ]
        if not task_messages:
            task_messages = [message for message in messages if getattr(message, "message_type", "") != "compaction"]
        payload = {
            "schema_version": 1,
            "type": "turn",
            "time": utc_now(),
            "session_id": getattr(task, "session_id", self.session_id),
            "task_id": task_id,
            "status": getattr(task, "status", ""),
            "user_message": self._redact(self._last_content(task_messages, "user")),
            "assistant_answer": self._redact(getattr(task, "output", "") or self._last_content(task_messages, "assistant")),
            "tool_calls": self._collect_tool_calls(task_messages),
            "tool_results": self._collect_tool_results(task_messages),
            "message_ids": [getattr(message, "message_id", "") for message in task_messages],
            "error": self._redact(getattr(task, "error", "")),
            "metadata": self._redact_jsonable(dict(getattr(task, "metadata", {}) or {})),
        }
        self._append_jsonl(self.session_dir / "turns.jsonl", payload)

    def load_session(self) -> dict[str, Any]:
        """读取 session.json。"""
        return self._read_json(self.session_dir / "session.json") or {}

    def load_messages(self) -> list[dict[str, Any]]:
        """读取 messages.jsonl。"""
        return self._read_jsonl(self.session_dir / "messages.jsonl")

    def load_events(self) -> list[dict[str, Any]]:
        """读取 events.jsonl。"""
        return self._read_jsonl(self.session_dir / "events.jsonl")

    def load_tasks(self) -> list[dict[str, Any]]:
        """读取 tasks.jsonl。"""
        return self._read_jsonl(self.session_dir / "tasks.jsonl")

    def load_turns(self) -> list[dict[str, Any]]:
        """读取 turns.jsonl。"""
        return self._read_jsonl(self.session_dir / "turns.jsonl")

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

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
        return records

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

    def _to_jsonable(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._to_jsonable(asdict(value))
        if isinstance(value, dict):
            return {str(key): self._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _last_content(self, messages: list[Any], role: str) -> str:
        for message in reversed(messages):
            if getattr(message, "role", "") == role and getattr(message, "message_type", "") != "compaction":
                return str(getattr(message, "content", ""))
        return ""

    def _collect_tool_calls(self, messages: list[Any]) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for message in messages:
            for tool_call in getattr(message, "tool_calls", []) or []:
                plain = self._to_jsonable(self._to_plain(tool_call))
                if isinstance(plain, dict):
                    calls.append(self._redact_mapping(plain))
                else:
                    calls.append({"value": self._redact(str(plain))})
        return calls

    def _collect_tool_results(self, messages: list[Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for message in messages:
            if getattr(message, "role", "") != "tool":
                continue
            content = str(getattr(message, "content", ""))
            results.append(
                {
                    "tool_name": getattr(message, "tool_name", "") or getattr(message, "agent_name", ""),
                    "tool_call_id": getattr(message, "tool_call_id", ""),
                    "summary": self._redact(self._summarize_text(content)),
                    "content_length": len(content),
                    "metadata": self._redact_jsonable(dict(getattr(message, "metadata", {}) or {})),
                }
            )
        return results

    def _summarize_text(self, text: str, *, limit: int = 1200) -> str:
        if len(text) <= limit:
            return text
        head = text[: limit // 2]
        tail = text[-limit // 2 :]
        return f"{head}\n[truncated source log tool result omitted_chars={len(text) - limit}]\n{tail}"

    def _redact_mapping(self, value: dict[str, Any]) -> dict[str, Any]:
        redacted = self._redact_jsonable(value)
        return redacted if isinstance(redacted, dict) else {}

    def _redact(self, value: str) -> str:
        return redact_sensitive_text(value)

    def _redact_jsonable(self, value: Any) -> Any:
        value = self._to_jsonable(value)
        if isinstance(value, str):
            return self._redact(value)
        if isinstance(value, dict):
            return {key: self._redact_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact_jsonable(item) for item in value]
        return value


def current_time_record_name() -> str:
    """返回用于 chat 记录目录名的当前时间。"""
    return datetime.now().strftime("%H-%M-%S-%f")
