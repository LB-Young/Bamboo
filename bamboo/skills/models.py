"""Skill 数据模型。

这些模型把 Skill 的静态定义、运行状态、索引缓存、校验结果和使用事件
拆开保存，避免把运行时状态写回 `SKILL.md`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SkillStatus = Literal["draft", "active", "disabled", "error", "deprecated"]
SkillHealth = Literal["unknown", "ok", "warning", "error"]
SkillUsageEventType = Literal[
    "created",
    "validated",
    "selected",
    "loaded",
    "succeeded",
    "failed",
    "disabled",
    "enabled",
]
SkillTrustLevel = Literal["builtin", "trusted", "community", "local"]
SkillScanLevel = Literal["safe", "caution", "dangerous"]


@dataclass(slots=True)
class SkillDefinition:
    """表示从 `SKILL.md` 和目录结构读取出的 Skill 定义。"""

    name: str
    description: str
    source_path: str
    source: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    user_invocable: bool = True
    load_experiences: bool = True
    trust_level: str = "local"
    origin: str = ""


@dataclass(slots=True)
class SkillState:
    """保存 Skill 的当前运行状态。"""

    schema_version: int
    name: str
    status: SkillStatus
    health: SkillHealth
    created_at: str
    updated_at: str
    last_indexed_at: str | None = None
    last_loaded_at: str | None = None
    last_validated_at: str | None = None
    last_error: str | None = None
    load_count: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass(slots=True)
class SkillIndex:
    """保存 SkillRegistry 使用的摘要索引。"""

    schema_version: int
    name: str
    description: str
    source_path: str
    source: str
    skill_md_sha256: str
    skill_md_mtime: float
    estimated_tokens: int
    resources: dict[str, list[str]]
    triggers: list[str]
    indexed_at: str


@dataclass(slots=True)
class SkillValidationResult:
    """保存最近一次 Skill 校验结果。"""

    schema_version: int
    validated_at: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillUsageEvent:
    """保存一条追加式 Skill 使用事件。"""

    ts: str
    event: SkillUsageEventType
    skill_name: str
    session_id: str = ""
    task_id: str = ""
    reason: str = ""
    tokens: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillHubSource:
    """Describes an external skill source."""

    identifier: str
    source_type: str
    location: str
    ref: str = ""
    path: str = ""


@dataclass(slots=True)
class SkillHubLockEntry:
    """Lockfile entry for an installed external skill."""

    schema_version: int
    name: str
    source: str
    source_type: str
    trust_level: SkillTrustLevel | str
    installed_at: str
    source_path: str
    content_hash: str
    scan_level: SkillScanLevel | str
    blocked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillScanFinding:
    """One finding produced by SkillGuard."""

    severity: SkillScanLevel | str
    category: str
    message: str
    path: str = ""
    line: int = 0
    pattern: str = ""


@dataclass(slots=True)
class SkillScanResult:
    """Complete result of scanning a skill directory."""

    schema_version: int
    scanned_at: str
    source: str
    path: str
    level: SkillScanLevel | str
    ok: bool
    findings: list[SkillScanFinding] = field(default_factory=list)
