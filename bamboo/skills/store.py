"""Skill 状态文件存储。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from bamboo.skills.models import SkillHubLockEntry, SkillIndex, SkillState, SkillUsageEvent, SkillValidationResult
from bamboo.userspace.userspace import get_skill_storage_dir


def utc_now() -> str:
    """返回统一的 UTC ISO 时间戳。"""
    return datetime.now(UTC).isoformat()


class SkillStore:
    """读写 `~/.bamboo/storage/skills/{name}` 下的状态文件。"""

    def __init__(self, *, root: Path | None = None) -> None:
        """初始化 Skill 状态存储。"""
        self.root = root or get_skill_storage_dir()

    def skill_dir(self, name: str) -> Path:
        """返回指定 Skill 的状态目录。"""
        return self.root / name

    def ensure_skill_dir(self, name: str) -> Path:
        """确保指定 Skill 的状态目录存在。"""
        path = self.skill_dir(name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def hub_dir(self) -> Path:
        """返回 SkillHub 存储目录。"""
        return self.root / ".hub"

    def quarantine_dir(self) -> Path:
        """返回外部 Skill 安装隔离区目录。"""
        return self.hub_dir() / "quarantine"

    def lock_path(self) -> Path:
        """返回 SkillHub lockfile 路径。"""
        return self.hub_dir() / "lock.json"

    def audit_path(self) -> Path:
        """返回 SkillHub audit JSONL 路径。"""
        return self.hub_dir() / "audit.jsonl"

    def load_hub_lock(self) -> dict[str, SkillHubLockEntry]:
        """读取 SkillHub lockfile。"""
        data = self._read_json(self.lock_path()) or {}
        entries = data.get("skills", data)
        if not isinstance(entries, dict):
            return {}
        lock: dict[str, SkillHubLockEntry] = {}
        for name, raw_entry in entries.items():
            if not isinstance(raw_entry, dict):
                continue
            try:
                lock[str(name)] = SkillHubLockEntry(**raw_entry)
            except TypeError:
                continue
        return lock

    def save_hub_lock(self, entries: dict[str, SkillHubLockEntry]) -> None:
        """保存 SkillHub lockfile。"""
        payload = {"schema_version": 1, "skills": {name: asdict(entry) for name, entry in sorted(entries.items())}}
        self._write_json(self.lock_path(), payload)

    def append_hub_audit(self, event: dict[str, Any]) -> None:
        """追加一条 SkillHub 审计事件。"""
        payload = {"ts": utc_now(), **event}
        path = self.audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def load_state(self, name: str) -> SkillState | None:
        """读取 Skill 当前状态。"""
        data = self._read_json(self.skill_dir(name) / "state.json")
        if data is None:
            return None
        try:
            return SkillState(**data)
        except TypeError:
            return None

    def save_state(self, state: SkillState) -> None:
        """保存 Skill 当前状态。"""
        state.updated_at = utc_now()
        self._write_json(self.ensure_skill_dir(state.name) / "state.json", asdict(state))

    def create_state(self, name: str, *, status: str = "draft", health: str = "unknown") -> SkillState:
        """创建初始 Skill 状态。"""
        now = utc_now()
        state = SkillState(
            schema_version=1,
            name=name,
            status=status,  # type: ignore[arg-type]
            health=health,  # type: ignore[arg-type]
            created_at=now,
            updated_at=now,
        )
        self.save_state(state)
        return state

    def load_index(self, name: str) -> SkillIndex | None:
        """读取 Skill 索引缓存。"""
        data = self._read_json(self.skill_dir(name) / "index.json")
        if data is None:
            return None
        try:
            return SkillIndex(**data)
        except TypeError:
            return None

    def save_index(self, index: SkillIndex) -> None:
        """保存 Skill 索引缓存。"""
        self._write_json(self.ensure_skill_dir(index.name) / "index.json", asdict(index))
        state = self.load_state(index.name) or self.create_state(index.name)
        state.last_indexed_at = index.indexed_at
        self.save_state(state)

    def load_validation(self, name: str) -> SkillValidationResult | None:
        """读取最近一次校验结果。"""
        data = self._read_json(self.skill_dir(name) / "validation.json")
        if data is None:
            return None
        try:
            return SkillValidationResult(**data)
        except TypeError:
            return None

    def save_validation(self, name: str, result: SkillValidationResult) -> None:
        """保存校验结果并同步 state。"""
        self._write_json(self.ensure_skill_dir(name) / "validation.json", asdict(result))
        state = self.load_state(name) or self.create_state(name)
        state.last_validated_at = result.validated_at
        if result.ok:
            state.health = "warning" if result.warnings else "ok"
            state.last_error = None
            if state.status in {"draft", "error"}:
                state.status = "active"
        else:
            state.health = "error"
            state.status = "error"
            state.last_error = "; ".join(result.errors)
            state.failure_count += 1
        self.save_state(state)

    def append_usage(self, event: SkillUsageEvent) -> None:
        """追加一条 Skill 使用事件，并更新 state 计数。"""
        skill_dir = self.ensure_skill_dir(event.skill_name)
        usage_path = skill_dir / "usage.jsonl"
        with usage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")

        state = self.load_state(event.skill_name) or self.create_state(event.skill_name)
        if event.event == "loaded":
            state.load_count += 1
            state.last_loaded_at = event.ts
        elif event.event == "succeeded":
            state.success_count += 1
        elif event.event == "failed":
            state.failure_count += 1
            state.last_error = event.error or state.last_error
            state.health = "error"
        elif event.event == "disabled":
            state.status = "disabled"
        elif event.event == "enabled" and state.status == "disabled":
            state.status = "active"
        self.save_state(state)

    def disable(self, name: str) -> SkillState:
        """禁用指定 Skill。"""
        state = self.load_state(name) or self.create_state(name)
        state.status = "disabled"
        self.save_state(state)
        self.append_usage(SkillUsageEvent(ts=utc_now(), event="disabled", skill_name=name))
        return state

    def enable(self, name: str) -> SkillState:
        """启用指定 Skill。"""
        state = self.load_state(name) or self.create_state(name)
        state.status = "active"
        if state.health == "unknown":
            state.health = "ok"
        self.save_state(state)
        self.append_usage(SkillUsageEvent(ts=utc_now(), event="enabled", skill_name=name))
        return state

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if is_dataclass(data):
            data = asdict(data)
        content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)
