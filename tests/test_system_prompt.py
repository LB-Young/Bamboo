from pathlib import Path

from bamboo.prompts import build_system_prompt_sections


def _section_names(platform_name: str) -> list[str]:
    sections = build_system_prompt_sections(
        session_mode="chat",
        project_root=Path.cwd(),
        memory_dir=Path("/tmp/bamboo-test-memory"),
        model="deepseek-chat",
        provider="deepseek",
        platform_name=platform_name,
    )
    return [section.name for section in sections]


def test_app_platform_prompt_is_loaded_for_app() -> None:
    assert "platform-app" in _section_names("app")


def test_app_fancy_uses_app_platform_prompt() -> None:
    assert "platform-app" in _section_names("app-fancy")


def test_web_does_not_load_app_platform_prompt() -> None:
    assert "platform-app" not in _section_names("web")
