"""Workflow package installer used by dialog tools."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from bamboo.security import inspect_command
from bamboo.skills.guard import MAX_SCAN_BYTES, PATTERNS
from bamboo.userspace.userspace import get_userspace_dir
from bamboo.workflows.registry import load_workflow_definition


@dataclass(frozen=True, slots=True)
class WorkflowScanFinding:
    severity: str
    category: str
    message: str
    path: str = ""
    line: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowScanResult:
    level: str
    ok: bool
    findings: tuple[WorkflowScanFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowInstallResult:
    name: str
    installed: bool
    reason: str
    destination: Path | None
    scan_result: WorkflowScanResult


class WorkflowInstaller:
    """Install workflow packages into user workflows directory."""

    def __init__(self, *, workflows_dir: Path | None = None) -> None:
        self.workflows_dir = workflows_dir or get_userspace_dir() / "workflows"

    def install(self, source_dir: Path, *, force: bool = False, overwrite: bool = False) -> WorkflowInstallResult:
        source = source_dir.expanduser().resolve()
        entry_path = source / "WORKFLOW.md"
        if not entry_path.is_file():
            scan = WorkflowScanResult("dangerous", False, (WorkflowScanFinding("dangerous", "invalid-workflow", "WORKFLOW.md is missing", str(source)),))
            return WorkflowInstallResult(source.name, False, "WORKFLOW.md is missing", None, scan)
        definition = load_workflow_definition(entry_path, source="local")
        scan = scan_workflow(source)
        if scan.level == "dangerous" and not force:
            return WorkflowInstallResult(definition.name, False, "dangerous scan findings", None, scan)
        destination = self.workflows_dir / definition.name
        if destination.exists():
            if not overwrite:
                return WorkflowInstallResult(definition.name, False, f"workflow already exists: {destination}", destination, scan)
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        return WorkflowInstallResult(definition.name, True, "installed", destination, scan)


def scan_workflow(source_dir: Path) -> WorkflowScanResult:
    """Scan workflow files and declared run command for risky content."""
    root = source_dir.resolve()
    findings: list[WorkflowScanFinding] = []
    for file_path in _iter_scan_files(root):
        relative = str(file_path.relative_to(root))
        content = _read_text_limited(file_path)
        if content is None:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for severity, category, pattern, message in PATTERNS:
                if pattern.search(line):
                    findings.append(WorkflowScanFinding(severity, category, message, relative, line_number))
    try:
        definition = load_workflow_definition(root / "WORKFLOW.md", source="local")
    except Exception as exc:
        findings.append(WorkflowScanFinding("dangerous", "invalid-workflow", str(exc), "WORKFLOW.md"))
    else:
        command = definition.run.command
        if command:
            result = inspect_command(command)
            if not result.allowed or result.risk.value != "read_only":
                severity = "dangerous" if not result.allowed or result.risk.value == "destructive" else "caution"
                findings.append(
                    WorkflowScanFinding(
                        severity,
                        "workflow-command-risk",
                        f"workflow command risk={result.risk.value}: {result.reason}",
                        "WORKFLOW.md",
                    )
                )
    level = "safe"
    if any(finding.severity == "dangerous" for finding in findings):
        level = "dangerous"
    elif findings:
        level = "caution"
    return WorkflowScanResult(level, level != "dangerous", tuple(findings))


def format_workflow_scan_report(result: WorkflowScanResult) -> str:
    """Format workflow scan findings for tool output."""
    if not result.findings:
        return f"Workflow scan {result.level}: no findings"
    rows = [f"Workflow scan {result.level}: {len(result.findings)} finding(s)"]
    for finding in result.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path or "-"
        rows.append(f"- [{finding.severity}] {finding.category} {location}: {finding.message}")
    return "\n".join(rows)


def _iter_scan_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.parts and path.stat().st_size <= MAX_SCAN_BYTES
    ]


def _read_text_limited(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    return raw[:MAX_SCAN_BYTES].decode("utf-8", errors="ignore")
