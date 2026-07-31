"""Skill safety scanner used before installing external skills."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from bamboo.skills.models import SkillScanFinding, SkillScanResult
from bamboo.skills.store import utc_now


MAX_SCAN_BYTES = 512 * 1024
SKILLSPECTOR_TIMEOUT_SECONDS = 180


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


def scan_skill_for_install(
    path: Path,
    source: str = "",
    *,
    skillspector_scan: Callable[[Path, str], SkillScanResult] | None = None,
) -> SkillScanResult:
    """Run all required safety scanners before installing a skill."""
    local_result = scan_skill(path, source=source)
    external_result = (skillspector_scan or scan_skill_with_skillspector)(path, source)
    return merge_scan_results(local_result, external_result)


def scan_skill_with_skillspector(path: Path, source: str = "") -> SkillScanResult:
    """Run embedded SkillSpector, falling back to its CLI when needed."""
    root = path.expanduser().resolve()
    embedded_result = _scan_with_embedded_skillspector(root, source)
    if embedded_result is not None:
        return embedded_result
    executable = shutil.which("skillspector")
    if executable is None:
        return _result(
            root,
            source,
            [
                SkillScanFinding(
                    severity="dangerous",
                    category="skillspector-unavailable",
                    message=(
                        "SkillSpector is required before installing skills but is not importable or available on PATH. "
                        "Reinstall Bamboo so its embedded SkillSpector dependency is installed."
                    ),
                    path=str(root),
                )
            ],
        )

    try:
        process = subprocess.run(
            [executable, "scan", str(root), "--no-llm", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=SKILLSPECTOR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return _result(
            root,
            source,
            [
                SkillScanFinding(
                    severity="dangerous",
                    category="skillspector-timeout",
                    message=f"SkillSpector scan exceeded {SKILLSPECTOR_TIMEOUT_SECONDS} seconds",
                    path=str(root),
                )
            ],
        )
    except OSError as exc:
        return _result(
            root,
            source,
            [
                SkillScanFinding(
                    severity="dangerous",
                    category="skillspector-failed",
                    message=f"unable to run SkillSpector: {exc}",
                    path=str(root),
                )
            ],
        )
    payload = _parse_skillspector_json(process.stdout)
    if payload is None:
        message = (process.stderr or process.stdout or "SkillSpector did not return JSON").strip()
        return _result(
            root,
            source,
            [
                SkillScanFinding(
                    severity="dangerous",
                    category="skillspector-failed",
                    message=message[:1000],
                    path=str(root),
                )
            ],
        )
    return _skillspector_payload_to_result(root, source, payload, returncode=process.returncode)


def merge_scan_results(*results: SkillScanResult) -> SkillScanResult:
    """Merge scanner results, preserving the highest risk level."""
    findings = [finding for result in results for finding in result.findings]
    level = _max_level(result.level for result in results)
    return SkillScanResult(
        schema_version=1,
        scanned_at=utc_now(),
        source=next((result.source for result in results if result.source), ""),
        path=next((result.path for result in results if result.path), ""),
        level=level,
        ok=all(result.ok for result in results) and level != "dangerous",
        findings=findings,
    )


def _scan_with_embedded_skillspector(root: Path, source: str) -> SkillScanResult | None:
    try:
        import typer
        from skillspector.cli import FormatChoice, scan
    except ImportError:
        return None

    with tempfile.TemporaryDirectory(prefix="bamboo-skillspector-") as temp_dir:
        output_path = Path(temp_dir) / "skillspector.json"
        returncode = 0
        try:
            scan(
                str(root),
                format=FormatChoice.json,
                output=output_path,
                no_llm=True,
            )
        except typer.Exit as exc:
            try:
                returncode = int(exc.exit_code or 0)
            except (TypeError, ValueError):
                returncode = 1
            if not output_path.is_file():
                return _result(
                    root,
                    source,
                    [
                        SkillScanFinding(
                            severity="dangerous",
                            category="skillspector-failed",
                            message=f"embedded SkillSpector exited with status {exc.exit_code}",
                            path=str(root),
                        )
                    ],
                )
        except Exception as exc:
            return _result(
                root,
                source,
                [
                    SkillScanFinding(
                        severity="dangerous",
                        category="skillspector-failed",
                        message=f"embedded SkillSpector failed: {exc}",
                        path=str(root),
                    )
                ],
            )
        try:
            payload = _parse_skillspector_json(output_path.read_text(encoding="utf-8"))
        except OSError as exc:
            return _result(
                root,
                source,
                [
                    SkillScanFinding(
                        severity="dangerous",
                        category="skillspector-failed",
                        message=f"unable to read embedded SkillSpector output: {exc}",
                        path=str(root),
                    )
                ],
            )
    if payload is None:
        return _result(
            root,
            source,
            [
                SkillScanFinding(
                    severity="dangerous",
                    category="skillspector-failed",
                    message="embedded SkillSpector did not return JSON",
                    path=str(root),
                )
            ],
        )
    return _skillspector_payload_to_result(root, source, payload, returncode=returncode)


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


def _parse_skillspector_json(stdout: str) -> dict[str, object] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _skillspector_payload_to_result(
    root: Path,
    source: str,
    payload: dict[str, object],
    *,
    returncode: int,
) -> SkillScanResult:
    risk_assessment = payload.get("risk_assessment")
    risk = risk_assessment if isinstance(risk_assessment, dict) else {}
    recommendation = str(
        payload.get("risk_recommendation") or payload.get("recommendation") or risk.get("recommendation") or ""
    ).upper()
    severity = str(payload.get("risk_severity") or payload.get("severity") or risk.get("severity") or "").upper()
    findings = _skillspector_findings(payload)
    if returncode != 0 and not findings:
        findings.append(
            SkillScanFinding(
                severity="dangerous",
                category="skillspector-failed",
                message=f"SkillSpector exited with status {returncode}",
                path=str(root),
            )
        )
    execution_successful = payload.get("execution_successful")
    if execution_successful is False:
        findings.append(
            SkillScanFinding(
                severity="dangerous",
                category="skillspector-incomplete",
                message="SkillSpector reported execution_successful=false",
                path=str(root),
            )
        )
    if recommendation == "DO_NOT_INSTALL" or severity == "CRITICAL" or execution_successful is False:
        level = "dangerous"
    elif recommendation == "CAUTION" or severity in {"HIGH", "MEDIUM"} or findings:
        level = "caution"
    else:
        level = "safe"
    return SkillScanResult(
        schema_version=1,
        scanned_at=utc_now(),
        source=source,
        path=str(root),
        level=level,
        ok=level != "dangerous" and returncode == 0,
        findings=findings,
    )


def _skillspector_findings(payload: dict[str, object]) -> list[SkillScanFinding]:
    raw_findings = payload.get("issues") or payload.get("filtered_findings") or payload.get("findings") or []
    if not isinstance(raw_findings, list):
        return []
    findings: list[SkillScanFinding] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        severity = _skillspector_finding_severity(str(raw.get("severity") or "caution"))
        rule_id = str(raw.get("rule_id") or raw.get("id") or raw.get("category") or "finding")
        path, line = _skillspector_location(raw)
        message = str(raw.get("message") or raw.get("description") or rule_id)
        findings.append(
            SkillScanFinding(
                severity=severity,
                category=f"skillspector:{rule_id}",
                message=message,
                path=path,
                line=line,
            )
        )
    return findings


def _skillspector_location(raw: dict[str, object]) -> tuple[str, int]:
    location = raw.get("location")
    if isinstance(location, dict):
        path = str(location.get("path") or location.get("file") or "")
        line_value = location.get("line") or location.get("start_line") or 0
    else:
        path = str(raw.get("path") or raw.get("file") or "")
        line_value = raw.get("line") or raw.get("start_line") or 0
    try:
        line = int(line_value)
    except (TypeError, ValueError):
        line = 0
    return path, line


def _skillspector_finding_severity(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"critical", "high", "dangerous"}:
        return "dangerous"
    if normalized in {"medium", "warning", "caution"}:
        return "caution"
    return "safe"


def _max_level(levels: object) -> str:
    rank = {"safe": 0, "caution": 1, "dangerous": 2}
    highest = "safe"
    for level in levels:
        normalized = str(level)
        if rank.get(normalized, 0) > rank[highest]:
            highest = normalized
    return highest


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
