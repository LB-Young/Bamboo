import platform
import os
from pathlib import Path
from typing import Any

import yaml


class BambooConfig:
    """Configuration manager for Bamboo.

    Loads all YAML configuration files from the user's local configs directory.
    The configs directory location is platform-aware:
      - Windows: %USERPROFILE%/.bamboo/configs
      - macOS/Linux: ~/.bamboo/configs
    """

    _instance: "BambooConfig | None" = None
    _configs: dict[str, dict[str, Any]] = {}

    def __new__(cls) -> "BambooConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._configs = {}
        self.load_config()

    @staticmethod
    def get_configs_dir() -> Path:
        """Get the user's local .bamboo/configs directory path (cross-platform)."""
        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("USERPROFILE", Path.home()))
        else:
            base = Path.home()
        return base / ".bamboo" / "configs"

    def load_config(self) -> None:
        """Load all YAML config files from the user's local configs directory."""
        configs_dir = BambooConfig.get_configs_dir()

        if not configs_dir.exists():
            print(f"Configs directory not found: {configs_dir}")
            self._configs = {}
            return

        loaded: dict[str, dict[str, Any]] = {}
        for yaml_file in sorted(configs_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    loaded[yaml_file.stem] = data
            except yaml.YAMLError as e:
                print(f"Error parsing YAML file {yaml_file.name}: {e}")
            except OSError as e:
                print(f"Error reading file {yaml_file.name}: {e}")

        self._configs = loaded

    def get(self, name: str, default: Any = None) -> dict[str, Any] | Any:
        """Get a specific config by its filename (without .yaml extension)."""
        return self._configs.get(name, default)

    def all(self) -> dict[str, dict[str, Any]]:
        """Get all loaded configs."""
        return dict(self._configs)

    def __getitem__(self, name: str) -> dict[str, Any]:
        """Allow dict-style access to configs, e.g., config['models']."""
        if name not in self._configs:
            raise KeyError(f"Config '{name}' not found. Available configs: {list(self._configs.keys())}")
        return self._configs[name]

    def __contains__(self, name: str) -> bool:
        """Allow 'in' operator, e.g., 'models' in config."""
        return name in self._configs
