"""验证 Bamboo Skill 生命周期、注册表和加载工具。"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from bamboo.helpers.config import load_builtin_skill_variables
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


def test_skill_registry_honors_builtin_central_disabled_config(tmp_path: Path) -> None:
    """验证 skills_buildin.yaml 可以集中禁用内置 Skill。"""
    config_path = tmp_path / "skills_buildin.yaml"
    config_path.write_text(
        "schema_version: 1\n"
        "skills:\n"
        "  youtube-reach:\n"
        "    enabled: false\n",
        encoding="utf-8",
    )
    store = SkillStore(root=tmp_path / "storage" / "skills")
    registry = SkillRegistry(
        skill_dirs=[("buildin", PACKAGE_BUILTIN_SKILLS_DIR)],
        store=store,
        builtin_config_paths=[config_path],
    )
    registry.refresh()

    assert registry.get("youtube-reach") is None
    assert registry.get("youtube-reach", include_inactive=True) is not None
    state = store.load_state("youtube-reach")
    assert state is not None
    assert state.status == "disabled"


def test_skill_registry_prefers_package_builtin_over_stale_mirror(tmp_path: Path) -> None:
    """验证用户空间旧内置镜像不会覆盖包内最新版 skill。"""
    mirror = tmp_path / "buildin_skills"
    stale_skill = mirror / "skill-creator" / "SKILL.md"
    stale_skill.parent.mkdir(parents=True)
    stale_skill.write_text(
        "---\n"
        "name: skill-creator\n"
        "description: stale mirror\n"
        "---\n"
        "\n"
        "# Stale\n",
        encoding="utf-8",
    )
    store = SkillStore(root=tmp_path / "storage" / "skills")
    registry = SkillRegistry(
        skill_dirs=[("buildin", mirror), ("buildin", PACKAGE_BUILTIN_SKILLS_DIR)],
        store=store,
    )

    registry.refresh()
    definition = registry.get("skill-creator")

    assert definition is not None
    assert Path(definition.source_path) == PACKAGE_BUILTIN_SKILLS_DIR / "skill-creator"
    assert definition.description != "stale mirror"


@pytest.mark.parametrize(
    ("skill_name", "expected_text"),
    [
        ("socratic-questioning", "苏格拉底式提问"),
        ("first-principles", "第一性原理"),
        ("minimum-experiment", "最小实验"),
        ("reverse-engineering-example", "反向拆解"),
        ("vertical-horizontal-analysis", "横纵分析法"),
        ("steelman-argument", "双向钢人论证"),
        ("macos-harness", "macos-harness doctor"),
    ],
)
def test_prompt_toolkit_adapted_builtin_skills_are_registered(
    tmp_path: Path,
    skill_name: str,
    expected_text: str,
) -> None:
    """验证从 prompt-toolkit 借鉴的内置 Skill 均已注册并可加载。"""
    store = SkillStore(root=tmp_path / "storage" / "skills")
    registry = SkillRegistry(
        skill_dirs=[("buildin", PACKAGE_BUILTIN_SKILLS_DIR)],
        store=store,
    )
    registry.refresh()

    definition = registry.get(skill_name)

    assert definition is not None
    assert definition.user_invocable is True
    assert expected_text in registry.load_skill_content(skill_name)


def test_hithink_finance_builtin_skill_is_registered_with_references(tmp_path: Path) -> None:
    """验证同花顺金融数据服务 Skill 作为 Bamboo 内置 Skill 可加载。"""
    store = SkillStore(root=tmp_path / "storage" / "skills")
    registry = SkillRegistry(
        skill_dirs=[("buildin", PACKAGE_BUILTIN_SKILLS_DIR)],
        store=store,
    )
    registry.refresh()

    definition = registry.get("hithink-finance")

    assert definition is not None
    assert definition.user_invocable is True
    assert "同花顺金融数据服务" in registry.load_skill_content(
        "hithink-finance",
        include_experiences=False,
        references=["cli.md"],
    )
    resource_files = registry.list_resource_files("hithink-finance", limit=40)
    assert "references/cli.md" in resource_files
    assert "references/api/endpoints-prices.md" in resource_files


def test_hithink_finance_builtin_references_are_included_in_package_data() -> None:
    """验证打包配置会包含内置 Skill 的多层 references。"""
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    package_data = pyproject["tool"]["setuptools"]["package-data"]["bamboo"]

    assert "skills/buildin/*/references/*" in package_data
    assert "skills/buildin/*/references/*/*" in package_data
    assert "skills/buildin/*/agents/*" in package_data


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


def test_macos_harness_is_macos_only_project_dependency() -> None:
    """验证 macos-harness 通过平台条件依赖随 macOS 安装 Bamboo。"""
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]
    assert any(dependency.startswith("macos-harness>=0.1.2;") and "sys_platform" in dependency and "darwin" in dependency for dependency in dependencies)


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
        "anysearch",
        "github-reach",
        "paper-reach",
        "douyin-reach",
        "youtube-reach",
        "rss-reach",
        "bilibili-reach",
        "xiaohongshu-reach",
        "zhihu-reach",
    }
    assert expected.issubset(names)

    validator = SkillValidator()
    for definition in registry.list(include_inactive=True):
        if definition.name in expected:
            result = validator.validate(definition)
            assert result.ok, f"{definition.name}: {result.errors}"


def test_builtin_skills_config_lists_reach_skills() -> None:
    """验证集中内置 Skill 配置包含平台 reach skill 及其变量。"""
    config_path = Path("bamboo/configs/skills_buildin.yaml")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    skills = data.get("skills", {})

    for name in (
        "github-reach",
        "paper-reach",
        "douyin-reach",
        "youtube-reach",
        "rss-reach",
        "bilibili-reach",
        "xiaohongshu-reach",
        "zhihu-reach",
    ):
        assert skills[name]["enabled"] is True
        assert skills[name]["user_invocable"] is True
        assert skills[name]["load_experiences"] is False
        assert isinstance(skills[name].get("load_policy"), dict)
        assert isinstance(skills[name].get("variables"), dict)
        assert isinstance(skills[name].get("requirements"), dict)
        assert isinstance(skills[name].get("permissions"), dict)
    assert skills["github-reach"]["variables"]["GITHUB_REACH_USER_AGENT"]
    assert skills["paper-reach"]["variables"]["PAPER_REACH_USER_AGENT"]
    assert skills["douyin-reach"]["variables"]["DOUYIN_REACH_REFERER"] == "https://www.douyin.com/"
    assert skills["douyin-reach"]["variables"]["DOUYIN_REACH_MAX_DOWNLOAD_MB"] == "200"
    assert "ffmpeg" in skills["douyin-reach"]["requirements"]["optional_bins"]
    assert "yt-dlp" in skills["youtube-reach"]["requirements"]["bins"]
    assert skills["rss-reach"]["variables"]["RSS_REACH_USER_AGENT"]
    assert skills["bilibili-reach"]["variables"]["BILIBILI_REACH_REFERER"] == "https://www.bilibili.com/"
    assert skills["xiaohongshu-reach"]["variables"]["XIAOHONGSHU_REACH_REFERER"] == "https://www.xiaohongshu.com/"
    assert skills["zhihu-reach"]["variables"]["ZHIHU_REACH_REFERER"] == "https://www.zhihu.com/"


def test_scripted_builtin_skills_use_bamboo_python_environment() -> None:
    """验证内置脚本型 Skill 引导模型使用 Bamboo 所在 Python 环境。"""
    scripted_skills = (
        "anysearch",
        "github-reach",
        "paper-reach",
        "douyin-reach",
        "youtube-reach",
        "rss-reach",
        "bilibili-reach",
        "xiaohongshu-reach",
        "zhihu-reach",
    )
    config = yaml.safe_load(Path("bamboo/configs/skills_buildin.yaml").read_text(encoding="utf-8")) or {}
    skills = config.get("skills", {})

    for name in scripted_skills:
        content = (PACKAGE_BUILTIN_SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        assert "python3 <skill_dir>" not in content
        assert "Use the same `python` environment that runs Bamboo." in content
        assert "python" in skills[name]["requirements"]["bins"]
        assert "python3" not in skills[name]["requirements"]["bins"]


def test_reach_skills_honor_user_no_fallback_instruction() -> None:
    """验证平台 reach skill 明确禁止违背用户的 no-fallback 限制。"""
    for name in ("douyin-reach", "xiaohongshu-reach", "zhihu-reach"):
        content = (PACKAGE_BUILTIN_SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        assert "If the user explicitly says not to try other methods" in content
        assert "Do not fall back to generic `web_fetch`, raw `curl`, generic search, or unrelated tools." in content


def test_reach_skills_require_headful_browser_for_guarded_platforms() -> None:
    """验证登录态平台的 browser workflow 明确使用可见浏览器。"""
    for name in ("douyin-reach", "xiaohongshu-reach", "zhihu-reach"):
        content = (PACKAGE_BUILTIN_SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        assert "set `headless=false`" in content


def test_builtin_skill_directories_do_not_keep_local_config_yaml() -> None:
    """验证内置 Skill 配置集中在 skills_buildin.yaml，不保留目录级 config.yaml。"""
    assert list(PACKAGE_BUILTIN_SKILLS_DIR.glob("*/config.yaml")) == []


def test_builtin_skill_variables_load_from_shared_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证内置 skill 变量由共享 helper 读取和展开。"""
    package_config = tmp_path / "package.yaml"
    package_config.write_text(
        "schema_version: 1\n"
        "skills:\n"
        "  rss-reach:\n"
        "    variables:\n"
        "      RSS_REACH_USER_AGENT: package-agent\n"
        "      TOKEN: \"${RSS_TEST_TOKEN}\"\n",
        encoding="utf-8",
    )
    user_config = tmp_path / "user.yaml"
    user_config.write_text(
        "schema_version: 1\n"
        "skills:\n"
        "  rss-reach:\n"
        "    variables:\n"
        "      RSS_REACH_USER_AGENT: user-agent\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RSS_TEST_TOKEN", "resolved-token")

    variables = load_builtin_skill_variables("rss-reach", config_paths=[package_config, user_config])

    assert variables["RSS_REACH_USER_AGENT"] == "user-agent"
    assert variables["TOKEN"] == "resolved-token"


def test_builtin_anysearch_cli_exposes_expected_commands() -> None:
    """验证 AnySearch 内置 skill 的最小 CLI 入口存在。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "anysearch" / "scripts" / "anysearch_cli.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "search" in result.stdout
    assert "batch-search" in result.stdout
    assert "extract" in result.stdout
    assert "get-sub-domains" in result.stdout


def test_builtin_reach_clis_expose_expected_commands() -> None:
    """验证平台 reach skill 的最小 CLI 入口存在。"""
    scripts = {
        "github-reach/scripts/github_cli.py": ["parse", "repo", "releases", "issues", "prs", "user"],
        "paper-reach/scripts/paper_cli.py": ["arxiv-search", "arxiv-id", "doi"],
        "douyin-reach/scripts/douyin_cli.py": [
            "parse",
            "resolve",
            "page",
            "search-url",
            "video-info",
            "download",
            "extract-audio",
            "transcript",
            "explain-file",
            "creator-profile",
            "collection-list",
            "creator-analyze",
            "publish-plan",
            "capability",
        ],
        "youtube-reach/scripts/youtube_cli.py": ["info", "transcript", "playlist"],
        "rss-reach/scripts/rss_cli.py": ["read", "latest", "check"],
        "bilibili-reach/scripts/bilibili_cli.py": ["search", "video"],
        "xiaohongshu-reach/scripts/xiaohongshu_cli.py": ["parse", "note", "search-url"],
        "zhihu-reach/scripts/zhihu_cli.py": ["parse", "page", "search-url"],
    }

    for script_name, expected_commands in scripts.items():
        result = subprocess.run(
            [sys.executable, str(PACKAGE_BUILTIN_SKILLS_DIR / script_name), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, script_name
        for command in expected_commands:
            assert command in result.stdout, script_name


def test_builtin_xiaohongshu_parse_extracts_note_id() -> None:
    """验证 Xiaohongshu reach 可以从公开链接文本提取 note id。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "xiaohongshu-reach" / "scripts" / "xiaohongshu_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "parse",
            "看看这个 https://www.xiaohongshu.com/explore/65f123456789abcdef123456?xsec_token=abc",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["note_ids"] == ["65f123456789abcdef123456"]
    assert output["canonical_urls"] == ["https://www.xiaohongshu.com/explore/65f123456789abcdef123456"]


def test_builtin_xiaohongshu_parse_runs_without_bamboo_package() -> None:
    """验证 Xiaohongshu reach 脚本没有安装 bamboo 包时仍可解析链接。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "xiaohongshu-reach" / "scripts" / "xiaohongshu_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(script),
            "parse",
            "看看这个 https://www.xiaohongshu.com/explore/65f123456789abcdef123456",
        ],
        cwd=script.parent,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["note_ids"] == ["65f123456789abcdef123456"]


def test_builtin_douyin_parse_extracts_video_id() -> None:
    """验证 Douyin reach 可以从公开链接文本提取 video id。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "douyin-reach" / "scripts" / "douyin_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "parse",
            "看看这个 https://www.douyin.com/video/7123456789012345678?previous_page=app_code_link",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["video_ids"] == ["7123456789012345678"]
    assert output["canonical_video_urls"] == ["https://www.douyin.com/video/7123456789012345678"]


def test_builtin_douyin_parse_runs_without_bamboo_package() -> None:
    """验证 Douyin reach 脚本没有安装 bamboo 包时仍可解析链接。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "douyin-reach" / "scripts" / "douyin_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(script),
            "parse",
            "看看这个 https://www.douyin.com/video/7123456789012345678",
        ],
        cwd=script.parent,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["video_ids"] == ["7123456789012345678"]


def test_builtin_zhihu_parse_runs_without_bamboo_package() -> None:
    """验证 Zhihu reach 脚本没有安装 bamboo 包时仍可解析链接。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "zhihu-reach" / "scripts" / "zhihu_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(script),
            "parse",
            "看看这个 https://www.zhihu.com/question/1986872411988173762/answer/2069851123398226947",
        ],
        cwd=script.parent,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["entities"] == [
        {"type": "answer", "id": "2069851123398226947", "question_id": "1986872411988173762"}
    ]


def test_builtin_douyin_parse_extracts_user_and_collection_ids() -> None:
    """验证 Douyin reach 可以解析用户和合集链接。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "douyin-reach" / "scripts" / "douyin_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "parse",
            "主页 https://www.douyin.com/user/MS4wLjABAAAAabcd 合集 https://www.douyin.com/collection/7345678901234567890",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["user_ids"] == ["MS4wLjABAAAAabcd"]
    assert output["collection_ids"] == ["7345678901234567890"]


def test_builtin_douyin_capability_lists_internal_modules() -> None:
    """验证 Douyin reach 暴露单 skill 内部能力分层。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "douyin-reach" / "scripts" / "douyin_cli.py"

    result = subprocess.run(
        [sys.executable, str(script), "capability"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "video" in output["modules"]
    assert "creator" in output["modules"]
    assert "publish" in output["modules"]
    assert "publish" in output["requires_explicit_user_confirmation"]


def test_builtin_douyin_publish_plan_requires_confirmation(tmp_path: Path) -> None:
    """验证 Douyin 发布能力只生成受控计划，不静默发布。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "douyin-reach" / "scripts" / "douyin_cli.py"
    media = tmp_path / "demo.mp4"
    media.write_bytes(b"demo")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "publish-plan",
            "--title",
            "标题",
            "--body",
            "正文",
            "--media",
            str(media),
            "--tag",
            "测试",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["can_auto_publish"] is False
    assert output["requires_visible_browser"] is True
    assert output["requires_final_user_confirmation"] is True
    assert output["media"][0]["exists"] is True


def test_builtin_douyin_transcript_reads_sidecar(tmp_path: Path) -> None:
    """验证 Douyin 视频模块可以读取本地字幕 sidecar。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "douyin-reach" / "scripts" / "douyin_cli.py"
    video = tmp_path / "demo.mp4"
    transcript_path = tmp_path / "demo.txt"
    video.write_bytes(b"demo")
    transcript_path.write_text("这是一段字幕", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), "transcript", str(video)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["available"] is True
    assert output["text"] == "这是一段字幕"


def test_builtin_github_repo_argument_parser_accepts_url() -> None:
    """验证 GitHub reach 的 repo 参数解析接受 GitHub URL。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "github-reach" / "scripts" / "github_cli.py"

    result = subprocess.run(
        [sys.executable, str(script), "parse", "https://github.com/openai/codex.git"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["full_name"] == "openai/codex"


def test_builtin_zhihu_parse_extracts_question_and_answer() -> None:
    """验证 Zhihu reach 可以从公开链接文本提取 question/answer 实体。"""
    script = PACKAGE_BUILTIN_SKILLS_DIR / "zhihu-reach" / "scripts" / "zhihu_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "parse",
            "https://www.zhihu.com/question/123456/answer/789012",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["entities"] == [{"type": "answer", "id": "789012", "question_id": "123456"}]
