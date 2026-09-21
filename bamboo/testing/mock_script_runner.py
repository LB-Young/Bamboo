"""Run standalone script checks as real subprocesses without pytest."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def run_script(test_file: str, script_name: str, argv: list[str], request: dict) -> None:
    """Execute the corresponding script with sample request arguments."""
    script = Path(test_file).resolve().parent.parent / "scripts" / script_name
    if not script.is_file():
        raise FileNotFoundError(script)
    if script.suffix == ".py":
        command = [sys.executable, str(script), *argv]
    else:
        bash = shutil.which("bash")
        if bash is None:
            raise RuntimeError("bash is required to execute this shell script")
        command = [bash, str(script), *argv]
    print(json.dumps({"script": str(script), "request": request}, ensure_ascii=False, indent=2))
    print(f"Executing: {subprocess.list2cmdline(command)}")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print("Test succeeded")
