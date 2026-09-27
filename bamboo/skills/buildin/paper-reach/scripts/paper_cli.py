#!/usr/bin/env python3
"""Download research papers with resumable transfers and PDF validation."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a project dependency.
    yaml = None  # type: ignore[assignment]


DEFAULT_USER_AGENT = "Mozilla/5.0 Bamboo Paper Reach/1"
ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$")


class PaperReachError(RuntimeError):
    """Raised when paper-reach cannot complete a requested operation."""


@dataclass(frozen=True, slots=True)
class PaperSpec:
    """One paper download target."""

    url: str
    output: Path
    expected_bytes: int | None = None
    title: str = ""


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Structured result for one download attempt."""

    status: str
    url: str
    output: str
    bytes: int
    expected_bytes: int | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "url": self.url,
            "output": self.output,
            "bytes": self.bytes,
            "expected_bytes": self.expected_bytes,
            "message": self.message,
        }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            spec = PaperSpec(
                url=normalize_paper_url(args.url),
                output=Path(args.output).expanduser(),
                expected_bytes=args.expected_bytes,
            )
            result = download_paper(
                spec,
                staging_dir=Path(args.staging_dir).expanduser() if args.staging_dir else None,
                retries=args.retries,
                timeout=args.timeout,
                overwrite=args.overwrite,
                min_bytes=args.min_bytes,
            )
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            return 0 if result.status in {"downloaded", "skipped"} else 1
        if args.command == "arxiv":
            filename = args.filename or f"{normalize_arxiv_id(args.arxiv_id)}.pdf"
            output = build_output_path(Path(args.output_dir).expanduser(), args.series, filename)
            result = download_paper(
                PaperSpec(url=arxiv_pdf_url(args.arxiv_id), output=output, expected_bytes=args.expected_bytes),
                staging_dir=Path(args.staging_dir).expanduser() if args.staging_dir else None,
                retries=args.retries,
                timeout=args.timeout,
                overwrite=args.overwrite,
                min_bytes=args.min_bytes,
            )
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            return 0 if result.status in {"downloaded", "skipped"} else 1
        if args.command == "manifest":
            specs = load_manifest(Path(args.manifest).expanduser(), output_dir=Path(args.output_dir).expanduser())
            results = [
                download_paper(
                    spec,
                    staging_dir=Path(args.staging_dir).expanduser() if args.staging_dir else None,
                    retries=args.retries,
                    timeout=args.timeout,
                    overwrite=args.overwrite,
                    min_bytes=args.min_bytes,
                )
                for spec in specs
            ]
            print(json.dumps([result.as_dict() for result in results], ensure_ascii=False, indent=2))
            return 0 if all(result.status in {"downloaded", "skipped"} for result in results) else 1
        if args.command == "status":
            specs = load_manifest(Path(args.manifest).expanduser(), output_dir=Path(args.output_dir).expanduser())
            print(json.dumps([status_for_spec(spec).as_dict() for spec in specs], ensure_ascii=False, indent=2))
            return 0
        if args.command == "normalize":
            print(normalize_paper_url(args.value))
            return 0
        parser.error(f"unsupported command: {args.command}")
    except PaperReachError as exc:
        print(f"paper-reach error: {exc}", file=sys.stderr)
        return 1
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download one direct paper URL.")
    download.add_argument("url")
    download.add_argument("--output", required=True)
    add_download_options(download)

    arxiv = subparsers.add_parser("arxiv", help="Download one arXiv id.")
    arxiv.add_argument("arxiv_id")
    arxiv.add_argument("--output-dir", required=True)
    arxiv.add_argument("--series", default="")
    arxiv.add_argument("--filename", default="")
    add_download_options(arxiv)

    manifest = subparsers.add_parser("manifest", help="Download every paper in a JSON/YAML manifest.")
    manifest.add_argument("manifest")
    manifest.add_argument("--output-dir", required=True)
    add_download_options(manifest)

    status = subparsers.add_parser("status", help="Inspect manifest targets without downloading.")
    status.add_argument("manifest")
    status.add_argument("--output-dir", required=True)

    normalize = subparsers.add_parser("normalize", help="Normalize an arXiv id or PDF URL.")
    normalize.add_argument("value")
    return parser


def add_download_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--staging-dir", default="", help="Directory for partial files. Defaults next to output.")
    parser.add_argument("--expected-bytes", type=int, default=None)
    parser.add_argument("--min-bytes", type=int, default=1024, help="Smallest acceptable PDF size.")
    parser.add_argument("--timeout", type=int, default=120, help="Per-request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")


def download_paper(
    spec: PaperSpec,
    *,
    staging_dir: Path | None,
    retries: int,
    timeout: int,
    overwrite: bool,
    min_bytes: int,
) -> DownloadResult:
    output = spec.output
    if output.exists() and not overwrite and pdf_is_valid(output, min_bytes=min_bytes, expected_bytes=spec.expected_bytes):
        return DownloadResult("skipped", spec.url, str(output), output.stat().st_size, spec.expected_bytes, "already complete")

    staging_root = staging_dir or output.parent / ".paper-reach"
    staging_root.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = staging_root / f"{safe_filename(output.name)}.part"

    last_error = ""
    for attempt in range(1, max(1, retries) + 1):
        try:
            transfer_url_to_file(spec.url, partial, timeout=timeout)
            if not pdf_is_valid(partial, min_bytes=min_bytes, expected_bytes=spec.expected_bytes):
                last_error = "downloaded file failed PDF or size validation"
                time.sleep(min(attempt, 5))
                continue
            shutil.copy2(partial, output)
            return DownloadResult("downloaded", spec.url, str(output), output.stat().st_size, spec.expected_bytes)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = str(exc)
            time.sleep(min(attempt, 5))
    size = partial.stat().st_size if partial.exists() else 0
    return DownloadResult("failed", spec.url, str(output), size, spec.expected_bytes, last_error)


def transfer_url_to_file(url: str, partial: Path, *, timeout: int) -> None:
    existing_size = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if existing_size:
        headers["Range"] = f"bytes={existing_size}-"

    request = urllib.request.Request(url, headers=headers)
    opener = build_url_opener()
    with opener.open(request, timeout=timeout) as response:
        status = getattr(response, "status", response.getcode())
        mode = "ab" if existing_size and status == 206 else "wb"
        if existing_size and status != 206:
            existing_size = 0
        with partial.open(mode + "") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)


def build_url_opener() -> urllib.request.OpenerDirector:
    proxy = normalized_proxy(load_vpn_proxy_from_env_files())
    if not proxy:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))


def normalized_proxy(value: str) -> str:
    proxy = value.strip().strip('"').strip("'")
    if not proxy:
        return ""
    if proxy.isdigit():
        proxy = f"http://127.0.0.1:{proxy}"
    if "://" not in proxy:
        proxy = f"http://{proxy}"
    parsed = urllib.parse.urlparse(proxy)
    if parsed.scheme not in {"http", "https", "socks5", "socks4"} or not parsed.netloc:
        raise PaperReachError("VPN_PROT must be a proxy URL or port, such as http://127.0.0.1:<port> or <port>")
    return proxy


def pdf_is_valid(path: Path, *, min_bytes: int, expected_bytes: int | None) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size < min_bytes:
        return False
    if expected_bytes is not None and size < int(expected_bytes * 0.99):
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def status_for_spec(spec: PaperSpec) -> DownloadResult:
    if not spec.output.exists():
        return DownloadResult("missing", spec.url, str(spec.output), 0, spec.expected_bytes)
    size = spec.output.stat().st_size
    status = "complete" if pdf_is_valid(spec.output, min_bytes=1024, expected_bytes=spec.expected_bytes) else "incomplete"
    return DownloadResult(status, spec.url, str(spec.output), size, spec.expected_bytes)


def load_manifest(path: Path, *, output_dir: Path) -> list[PaperSpec]:
    if not path.is_file():
        raise PaperReachError(f"manifest not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise PaperReachError("PyYAML is required for YAML manifests")
        data = yaml.safe_load(text)
    items = data.get("papers") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise PaperReachError("manifest must be a list or contain a 'papers' list")
    return [paper_spec_from_mapping(item, output_dir=output_dir) for item in items]


def paper_spec_from_mapping(item: Any, *, output_dir: Path) -> PaperSpec:
    if not isinstance(item, dict):
        raise PaperReachError("each manifest paper must be a mapping")
    raw_url = str(item.get("url") or "").strip()
    arxiv_id = str(item.get("arxiv_id") or item.get("arxiv") or "").strip()
    url = normalize_paper_url(raw_url or arxiv_id)
    output = output_from_manifest_item(item, output_dir=output_dir, url=url)
    expected_bytes = item.get("expected_bytes")
    if expected_bytes is not None:
        expected_bytes = int(expected_bytes)
    return PaperSpec(url=url, output=output, expected_bytes=expected_bytes, title=str(item.get("title") or ""))


def output_from_manifest_item(item: dict[str, Any], *, output_dir: Path, url: str) -> Path:
    raw_path = str(item.get("path") or "").strip()
    if raw_path:
        return safe_join(output_dir, raw_path)
    filename = str(item.get("filename") or "").strip() or filename_from_url(url)
    series = str(item.get("series") or "").strip()
    return build_output_path(output_dir, series, filename)


def build_output_path(output_dir: Path, series: str, filename: str) -> Path:
    relative = Path(series) / filename if series else Path(filename)
    return safe_join(output_dir, str(relative))


def safe_join(root: Path, relative: str) -> Path:
    root_resolved = root.expanduser().resolve()
    target = (root_resolved / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise PaperReachError(f"output path escapes output directory: {relative}") from exc
    return target


def filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = Path(path).name or "paper.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return safe_filename(name)


def safe_filename(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", name).strip() or "paper.pdf"


def normalize_paper_url(value: str) -> str:
    text = value.strip()
    if not text:
        raise PaperReachError("paper URL or arXiv id is required")
    if ARXIV_ID_RE.match(text):
        return arxiv_pdf_url(text)
    parsed = urllib.parse.urlparse(text)
    if parsed.netloc == "arxiv.org":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"abs", "pdf"}:
            return arxiv_pdf_url(parts[1])
    if parsed.scheme in {"http", "https"}:
        return text
    raise PaperReachError(f"unsupported paper URL or id: {value}")


def normalize_arxiv_id(value: str) -> str:
    arxiv_id = value.strip()
    if arxiv_id.startswith("arXiv:"):
        arxiv_id = arxiv_id.removeprefix("arXiv:")
    if not ARXIV_ID_RE.match(arxiv_id):
        raise PaperReachError(f"invalid arXiv id: {value}")
    return arxiv_id


def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{normalize_arxiv_id(arxiv_id)}"


def load_vpn_proxy_from_env_files() -> str:
    """Read VPN_PROT only from .env files; do not infer or probe local ports."""
    for path in (Path.cwd() / ".env", Path.home() / ".bamboo" / ".env"):
        if path.is_file():
            value = parse_env_file(path).get("VPN_PROT", "")
            if value:
                return value
    return ""


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


if __name__ == "__main__":
    raise SystemExit(main())
