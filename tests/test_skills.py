"""验证 Bamboo Skill 生命周期、注册表和加载工具。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bamboo.skills.creator import SkillCreator
from bamboo.skills.frontmatter import parse_skill_markdown
from bamboo.skills.registry import PACKAGE_BUILTIN_SKILLS_DIR, SkillRegistry
from bamboo.skills.store import SkillStore
from bamboo.skills.validator import SkillValidator
from bamboo.tools.buildin.skill_load import SkillLoadTool


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """隔离用户空间，避免测试写入真实 ~/.bamboo。"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_parse_skill_markdown_reads_frontmatter() -> None:
    """验证 SKILL.md frontmatter 解析。"""
    parsed = parse_skill_markdown(
        "---\n"
        "name: demo-skill\n"
        "description: Demo skill.\n"
        "---\n"
        "\n"
        "# Demo\n"
    )

    assert parsed.frontmatter["name"] == "demo-skill"
    assert parsed.body == "# Demo"


def test_skill_creator_writes_definition_and_state_files(tmp_path: Path) -> None:
    """验证创建 Skill 会生成完整源文件和状态文件。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    result = SkillCreator(skills_dir=skills_dir, store=store).create(
        "demo-skill",
        description="Demo reusable workflow.",
    )

    assert result.status == "active"
    assert (skills_dir / "demo-skill" / "SKILL.md").is_file()
    assert (skills_dir / "demo-skill" / "config.yaml").is_file()
    assert (skills_dir / "demo-skill" / "scripts").is_dir()
    assert (skills_dir / "demo-skill" / "references").is_dir()
    assert (skills_dir / "demo-skill" / "assets").is_dir()
    assert (skills_dir / "demo-skill" / "experiences" / "README.md").is_file()

    state_dir = store.skill_dir("demo-skill")
    assert (state_dir / "state.json").is_file()
    assert (state_dir / "index.json").is_file()
    assert (state_dir / "validation.json").is_file()
    assert (state_dir / "usage.jsonl").is_file()

    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "active"
    assert state["health"] == "ok"


def test_skill_registry_filters_disabled_skills(tmp_path: Path) -> None:
    """验证 disabled Skill 不进入运行时摘要。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    store.disable("demo-skill")

    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    assert registry.list() == []
    assert [skill.name for skill in registry.list(include_inactive=True)] == ["demo-skill"]
    assert registry.render_catalog() == ""


def test_skill_registry_honors_disabled_config(tmp_path: Path) -> None:
    """验证 config.yaml enabled=false 会禁用 Skill。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    config_path = skills_dir / "demo-skill" / "config.yaml"
    config_path.write_text(config_path.read_text(encoding="utf-8").replace("enabled: true", "enabled: false"), encoding="utf-8")

    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    assert registry.list() == []
    state = store.load_state("demo-skill")
    assert state is not None
    assert state.status == "disabled"


def test_skill_registry_tolerates_corrupt_state_file(tmp_path: Path) -> None:
    """验证损坏的 state.json 不会阻断 Bamboo 启动。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    (store.skill_dir("demo-skill") / "state.json").write_text("{", encoding="utf-8")

    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    assert [skill.name for skill in registry.list()] == ["demo-skill"]
    state = store.load_state("demo-skill")
    assert state is not None
    assert state.status == "active"


def test_skill_registry_tolerates_legacy_state_schema(tmp_path: Path) -> None:
    """验证旧版 state.json 字段不会阻断 Bamboo 启动。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    (store.skill_dir("demo-skill") / "state.json").write_text(
        json.dumps({"version": 1, "name": "demo-skill", "status": "active"}),
        encoding="utf-8",
    )

    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    assert [skill.name for skill in registry.list()] == ["demo-skill"]
    state = store.load_state("demo-skill")
    assert state is not None
    assert state.schema_version == 1


def test_skill_registry_renders_tool_catalog_and_resource_files(tmp_path: Path) -> None:
    """验证 SkillRegistry 能给工具描述和 skill_load 输出提供资源摘要。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    reference_path = skills_dir / "demo-skill" / "references" / "guide.md"
    reference_path.write_text("# Guide\n", encoding="utf-8")
    script_path = skills_dir / "demo-skill" / "scripts" / "helper.sh"
    script_path.write_text("echo helper\n", encoding="utf-8")

    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    catalog = registry.render_tool_catalog(verbose=True)
    assert "- demo-skill: Demo workflow." in catalog
    assert "references/guide.md" in catalog
    assert registry.list_resource_files("demo-skill") == ["references/guide.md", "scripts/helper.sh"]


@pytest.mark.asyncio
async def test_skill_load_tool_returns_content_and_updates_state(tmp_path: Path) -> None:
    """验证 skill_load 返回完整 Skill 内容并记录 usage/state。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    (skills_dir / "demo-skill" / "references" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    tool = SkillLoadTool(skill_registry=registry)
    result = await tool.execute("demo-skill")

    assert result.success is True
    assert '<skill_content name="demo-skill">' in result.content
    assert "# Skill: demo-skill" in result.content
    assert "Demo workflow." in result.content
    assert "<skill_base_dir>" in result.content
    assert "<file>references/guide.md</file>" in result.content
    assert result.metadata is not None
    assert result.metadata["resources"] == ["references/guide.md"]

    state = store.load_state("demo-skill")
    assert state is not None
    assert state.load_count == 1
    assert state.last_loaded_at is not None
    usage_lines = (store.skill_dir("demo-skill") / "usage.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"event": "loaded"' in line for line in usage_lines)


@pytest.mark.asyncio
async def test_skill_load_tool_lists_available_skills_when_missing(tmp_path: Path) -> None:
    """验证加载不存在 Skill 时返回可用列表，方便模型纠正选择。"""
    skills_dir = tmp_path / "skills"
    store = SkillStore(root=tmp_path / "storage" / "skills")
    SkillCreator(skills_dir=skills_dir, store=store).create("demo-skill", description="Demo workflow.")
    registry = SkillRegistry(skill_dirs=[("user", skills_dir)], store=store)
    registry.refresh()

    result = await SkillLoadTool(skill_registry=registry).execute("missing-skill")

    assert result.success is False
    assert "Available skills:" in result.content
    assert "demo-skill" in result.content


def test_builtin_phase4_skills_validate(tmp_path: Path) -> None:
    """验证 Phase 4 新增内置开发类 Skill 都能被扫描和校验。"""
    store = SkillStore(root=tmp_path / "storage" / "skills")
    registry = SkillRegistry(skill_dirs=[("buildin", PACKAGE_BUILTIN_SKILLS_DIR)], store=store)
    registry.refresh()
    names = {definition.name for definition in registry.list(include_inactive=True)}

    expected = {
        "systematic-debugging",
        "test-driven-development",
        "writing-plans",
        "requesting-code-review",
        "github-pr-workflow",
        "native-mcp",
    }
    assert expected.issubset(names)

    validator = SkillValidator()
    for definition in registry.list(include_inactive=True):
        if definition.name in expected:
            result = validator.validate(definition)
            assert result.ok, f"{definition.name}: {result.errors}"
