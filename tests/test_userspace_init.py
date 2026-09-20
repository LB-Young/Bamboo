from pathlib import Path

from bamboo.userspace.userspace import ensure_userspace


def test_init_creates_builtin_and_config_dirs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    ensure_userspace(overwrite=False)

    root = tmp_path / ".bamboo"
    required_dirs = [
        "configs",
        "buildin_tools",
        "buildin_skills",
        "buildin_subagents",
        "buildin_workflows",
    ]
    for name in required_dirs:
        assert (root / name).is_dir()

    assert (root / "configs" / "workflows_buildin.yaml").is_file()
    assert (root / "buildin_tools" / "base.py").is_file()
    assert (root / "buildin_skills" / "skill-creator" / "SKILL.md").is_file()
    assert (root / "buildin_subagents" / "planner.yaml").is_file()
    assert (root / "buildin_workflows" / "video-insight" / "WORKFLOW.md").is_file()


def test_overwrite_refreshes_builtin_and_config_dirs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    ensure_userspace(overwrite=False)

    root = tmp_path / ".bamboo"
    stale_config = root / "configs" / "stale.yaml"
    stale_tool = root / "buildin_tools" / "stale.txt"
    stale_skill = root / "buildin_skills" / "stale.txt"
    stale_subagent = root / "buildin_subagents" / "stale.txt"
    stale_workflow = root / "buildin_workflows" / "stale.txt"
    for path in [stale_config, stale_tool, stale_skill, stale_subagent, stale_workflow]:
        path.write_text("stale\n", encoding="utf-8")

    ensure_userspace(overwrite=True)

    for path in [stale_config, stale_tool, stale_skill, stale_subagent, stale_workflow]:
        assert not path.exists()
    assert (root / "configs" / "workflows_buildin.yaml").is_file()
    assert (root / "buildin_tools" / "base.py").is_file()
    assert (root / "buildin_workflows" / "video-insight" / "WORKFLOW.md").is_file()
