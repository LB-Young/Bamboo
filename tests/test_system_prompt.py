"""验证 Bamboo system prompt 的模式选择和会话接入。"""

from pathlib import Path

import pytest

from bamboo.factory.session import SessionFactory
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.requests_params import RunParams
from bamboo.prompts import build_system_prompt, resolve_prompt_mode
from bamboo.userspace.userspace import ensure_userspace


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """隔离用户空间，避免真实 ~/.bamboo/prompt 影响测试结果。"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))


def test_resolve_prompt_mode_uses_explicit_modes(tmp_path: Path) -> None:
    """验证显式 project/chat 模式优先于目录自动识别。"""
    assert resolve_prompt_mode(SessionMode.project, tmp_path) == "project"
    assert resolve_prompt_mode(SessionMode.chat, tmp_path) == "chat"


def test_resolve_prompt_mode_detects_project_for_auto(tmp_path: Path) -> None:
    """验证 auto 模式会在工程目录中使用 project prompt。"""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    assert resolve_prompt_mode(SessionMode.auto, tmp_path) == "project"


def test_build_project_prompt_includes_project_instructions(tmp_path: Path) -> None:
    """验证 project prompt 会拼入项目级 Agent 指令文件。"""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (tmp_path / "AGENTS.md").write_text("项目内回答必须先读代码。", encoding="utf-8")

    prompt = build_system_prompt(
        session_mode=SessionMode.project,
        project_root=tmp_path,
        memory_dir=memory_dir,
        model="deepseek-chat",
        provider="deepseek",
    )

    assert "# Identity" in prompt
    assert "面向软件工程项目的自主 Agent" in prompt
    assert "# Language" in prompt
    assert "# Tool Results" in prompt
    assert "# Runtime Environment" in prompt
    assert "deepseek-chat" in prompt
    assert "项目内回答必须先读代码。" in prompt


def test_build_chat_prompt_excludes_project_instructions(tmp_path: Path) -> None:
    """验证 chat prompt 不拼入项目级工程指令。"""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (tmp_path / "AGENTS.md").write_text("项目专属规则", encoding="utf-8")

    prompt = build_system_prompt(
        session_mode=SessionMode.chat,
        project_root=tmp_path,
        memory_dir=memory_dir,
    )

    assert "可靠、清晰、直接的 AI 助手" in prompt
    assert "面向软件工程项目的自主 Agent" not in prompt
    assert "项目专属规则" not in prompt


def test_ensure_userspace_copies_prompt_templates(tmp_path: Path) -> None:
    """验证 init 用户空间时会复制可编辑 prompt 模板。"""
    layout = ensure_userspace()

    assert (layout.root / "prompts" / "project" / "00-identity.md").is_file()
    assert (layout.root / "prompts" / "chat" / "00-identity.md").is_file()
    assert (layout.root / "prompts" / "shared" / "00-language.md").is_file()
    assert (layout.root / "storage" / "skills").is_dir()
    assert (layout.root / "buildin_skills" / "skill-creator" / "SKILL.md").is_file()
    assert (layout.root / "buildin_subagents" / "knowledge-curator.yaml").is_file()
    assert (layout.root / "memory" / "dates" / "chat" / "knowledge" / "profile.md").is_file()
    assert (layout.root / "memory" / "projects" / "knowledge" / "overview.md").is_file()
    assert "# Profile" in (layout.root / "memory" / "dates" / "chat" / "knowledge" / "profile.md").read_text(
        encoding="utf-8"
    )
    assert not (layout.root / "prompts" / "__init__.py").exists()
    assert not (layout.root / "prompts" / "system_prompt.py").exists()


def test_build_prompt_prefers_userspace_prompt_sections(tmp_path: Path) -> None:
    """验证运行时优先读取用户空间中的 prompt section。"""
    layout = ensure_userspace()
    user_chat_identity = layout.root / "prompts" / "chat" / "00-identity.md"
    user_chat_identity.write_text("# Custom Chat Identity\n\n用户自定义闲聊身份。", encoding="utf-8")

    prompt = build_system_prompt(
        session_mode=SessionMode.chat,
        project_root=tmp_path,
        memory_dir=tmp_path / "memory",
    )

    assert "# Custom Chat Identity" in prompt
    assert "用户自定义闲聊身份。" in prompt
    assert "可靠、清晰、直接的 AI 助手" not in prompt


def test_session_factory_sets_prompt_mode_metadata(tmp_path: Path) -> None:
    """验证 SessionFactory 会把完整 system prompt 和模式元数据写入 Context。"""
    run_params = RunParams(
        message="hello",
        project=str(tmp_path),
        session_mode=SessionMode.project,
        model="deepseek-chat",
        provider="deepseek",
    )
    session = SessionFactory().create(memory_dir_path=tmp_path / "memory", run_params=run_params)

    assert session.context.metadata["prompt_mode"] == "project"
    assert "面向软件工程项目的自主 Agent" in session.context.system_prompt
    assert session.messages[0].content == "hello"
