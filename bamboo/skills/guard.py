"""Skill safety scanner used before installing external skills."""

from __future__ import annotations

import re
from pathlib import Path

from bamboo.skills.models import SkillScanFinding, SkillScanResult
from bamboo.skills.store import utc_now


MAX_SCAN_BYTES = 512 * 1024


PATTERNS: tuple[tuple[str, str, re.Pattern[str], str], ...] = (
    (
        "dangerous",
        "destructive-command",
        re.compile(r"\brm\s+-[^\n]*r[^\n]*f\b|\bmkfs\b|\bdd\s+[^\n]*(of=/dev/|if=/dev/)", re.I),
        "contains destructive shell command",
    ),
    (
        "dangerous",
        "remote-code-execution",
        re.compile(r"\b(curl|wget)\b[^\n|;]*\|\s*(sh|bash|zsh|python|python3)\b", re.I),
        "downloads and executes remote code",
    ),
    (
        "dangerous",
        "persistence",
        re.compile(r"(~?/\.ssh/authorized_keys|crontab\s+-|launchctl|systemctl\s+enable|/etc/(passwd|shadow))", re.I),
        "attempts persistence or sensitive system file modification",
    ),
    (
        "dangerous",
        "network-tunnel",
        re.compile(r"\b(reverse shell|nc\s+-e|ncat\s+-e|socat\s+tcp|ssh\s+-R|ssh\s+-D)\b", re.I),
        "contains reverse shell or tunnel pattern",
    ),
    (
        "dangerous",
        "secret-exfiltration",
        re.compile(r"(OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN).{0,120}(curl|wget|http|https)", re.I | re.S),
        "appears to exfiltrate secrets",
    ),
    (
        "caution",
        "prompt-injection",
        re.compile(r"(ignore (all )?(previous|prior) instructions|reveal (system|developer) prompt|disable safety)", re.I),
        "contains prompt injection language",
    ),
    (
        "caution",
        "obfuscation",
        re.compile(r"\b(base64\s+-d|eval\s*\(|exec\s*\(|fromCharCode|atob\s*\()\b", re.I),
        "contains obfuscation or dynamic execution pattern",
    ),
)


def scan_skill(path: Path, source: str = "") -> SkillScanResult:
    """Scan a skill directory for high-risk content."""
    root = path.resolve()
    findings: list[SkillScanFinding] = []
    if not (root / "SKILL.md").is_file():
        findings.append(
            SkillScanFinding(
                severity="dangerous",
                category="invalid-skill",
                message="SKILL.md is missing",
                path=str(root),
            )
        )
        return _result(root, source, findings)

    for file_path in _iter_scan_files(root):
        relative = str(file_path.relative_to(root))
        content = _read_text_limited(file_path)
        if content is None:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for severity, category, pattern, message in PATTERNS:
                if pattern.search(line):
                    findings.append(
                        SkillScanFinding(
                            severity=severity,
                            category=category,
                            message=message,
                            path=relative,
                            line=line_number,
                            pattern=pattern.pattern,
                        )
                    )
    return _result(root, source, findings)


def should_allow_install(
    result: SkillScanResult,
    trust_level: str,
    *,
    force: bool = False,
) -> tuple[bool, str]:
    """Return whether an install should proceed for a trust level."""
    if result.level == "safe":
        return True, "scan passed"
    if trust_level == "builtin":
        return True, f"{trust_level} source allowed with {result.level} findings"
    if trust_level == "trusted" and result.level == "caution":
        return True, "trusted source allowed with caution findings"
    if trust_level == "community" and force:
        return True, "force allowed community source despite scan findings"
    if trust_level == "local" and result.level == "caution":
        return True, "local source allowed with caution findings"
    return False, f"{trust_level} source blocked by {result.level} scan findings"


def format_scan_report(result: SkillScanResult) -> str:
    """Format scan findings for CLI or logs."""
    if not result.findings:
        return f"Skill scan {result.level}: no findings"
    rows = [f"Skill scan {result.level}: {len(result.findings)} finding(s)"]
    for finding in result.findings:
        location = f"{finding.path}:{finding.line}" if finding.path else "-"
        rows.append(f"- [{finding.severity}] {finding.category} {location}: {finding.message}")
    return "\n".join(rows)


def _result(root: Path, source: str, findings: list[SkillScanFinding]) -> SkillScanResult:
    level = "safe"
    if any(finding.severity == "dangerous" for finding in findings):
        level = "dangerous"
    elif findings:
        level = "caution"
    return SkillScanResult(
        schema_version=1,
        scanned_at=utc_now(),
        source=source,
        path=str(root),
        level=level,
        ok=level != "dangerous",
        findings=findings,
    )


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
