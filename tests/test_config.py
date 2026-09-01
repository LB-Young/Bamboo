"""Configuration loading tests."""

from __future__ import annotations

import os
from pathlib import Path

from bamboo.helpers.config import BambooConfig, load_user_env


def test_load_user_env_reads_bamboo_env_file(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# comments are ignored",
                "DEEPSEEK_API_KEY=deepseek-key",
                "export MOONSHOT_API_KEY='moonshot-key'",
                'OPENROUTER_API_KEY="openrouter-key"',
                "invalid-line",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    load_user_env(env_path=env_path)

    assert os.environ["DEEPSEEK_API_KEY"] == "deepseek-key"
    assert os.environ["MOONSHOT_API_KEY"] == "moonshot-key"
    assert os.environ["OPENROUTER_API_KEY"] == "openrouter-key"


def test_load_user_env_preserves_existing_environment(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DEEPSEEK_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "shell-key")

    load_user_env(env_path=env_path)

    assert os.environ["DEEPSEEK_API_KEY"] == "shell-key"


def test_bamboo_config_loads_env_before_yaml(monkeypatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    config_dir = home_dir / ".bamboo" / "configs"
    config_dir.mkdir(parents=True)
    (home_dir / ".bamboo" / ".env").write_text("DEEPSEEK_API_KEY=loaded-key\n", encoding="utf-8")
    (config_dir / "models.yaml").write_text(
        "default_model: test\n"
        "models:\n"
        "  test:\n"
        "    provider: deepseek\n"
        "    model: deepseek-chat\n"
        "    api_key: ${DEEPSEEK_API_KEY}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    BambooConfig._instance = None

    config = BambooConfig()

    assert os.environ["DEEPSEEK_API_KEY"] == "loaded-key"
    assert config.get("models")["models"]["test"]["api_key"] == "${DEEPSEEK_API_KEY}"
