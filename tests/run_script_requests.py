"""Run every standalone script request as a real integration check without pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = sorted(
        path
        for base in (ROOT / "bamboo" / "skills" / "buildin", ROOT / "bamboo" / "workflows" / "buildin")
        for path in base.glob("*/scripts_test/*_test.py")
        if not path.name.startswith("test_")
    )
    failures: list[Path] = []
    for path in files:
        print(f"\n=== {path.relative_to(ROOT)} ===")
        result = subprocess.run([sys.executable, str(path)], cwd=ROOT, check=False)
        if result.returncode != 0:
            failures.append(path)
    print(f"\nRan {len(files)} standalone script requests; failures: {len(failures)}")
    for path in failures:
        print(f"- {path.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
