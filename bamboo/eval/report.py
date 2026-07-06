"""Evaluation report models and rendering."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvalCheck:
    """One assertion result."""

    name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    details: str = ""


@dataclass(frozen=True, slots=True)
class EvalReport:
    """Result of running an eval case."""

    case_name: str
    mode: str
    passed: bool
    checks: tuple[EvalCheck, ...]
    summary: dict[str, Any] = field(default_factory=dict)
    record_dir: str = ""
    output: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return {
            "case_name": self.case_name,
            "mode": self.mode,
            "passed": self.passed,
            "record_dir": self.record_dir,
            "output": self.output,
            "summary": self.summary,
            "checks": [asdict(check) for check in self.checks],
        }


def render_report(report: EvalReport, *, json_output: bool = False) -> str:
    """Render a report for CLI output."""
    if json_output:
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    status = "PASS" if report.passed else "FAIL"
    lines = [f"{status} {report.case_name} mode={report.mode}"]
    if report.record_dir:
        lines.append(f"record_dir: {report.record_dir}")
    if report.summary:
        summary = " ".join(f"{key}={value}" for key, value in sorted(report.summary.items()))
        lines.append(f"summary: {summary}")
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        detail = f" {check.details}" if check.details else ""
        lines.append(f"- {marker} {check.name}: expected={check.expected!r} actual={check.actual!r}{detail}")
    return "\n".join(lines)
