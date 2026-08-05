"""Lightweight semantic code intelligence tool."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bamboo.tools.buildin.base import Tool, ToolResult


SUPPORTED_OPERATIONS = {
    "diagnostics",
    "document_symbols",
    "find_references",
    "find_symbol",
    "go_to_definition",
    "hover",
}
MAX_SCAN_FILES = 500
DEFAULT_MAX_RESULTS = 100
SKIPPED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "venv",
}
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """A source-level symbol extracted from a Python AST."""

    name: str
    qualified_name: str
    kind: str
    file_path: str
    line: int
    character: int
    end_line: int
    end_character: int
    signature: str = ""
    docstring: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "file_path": self.file_path,
            "line": self.line,
            "character": self.character,
            "end_line": self.end_line,
            "end_character": self.end_character,
            "signature": self.signature,
            "docstring": self.docstring,
        }


@dataclass(frozen=True, slots=True)
class ReferenceInfo:
    """A source location that mentions a symbol name."""

    name: str
    kind: str
    file_path: str
    line: int
    character: int
    context: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "line": self.line,
            "character": self.character,
            "context": self.context,
        }


class LSPTool(Tool):
    """Semantic code query interface inspired by IDE/LSP workflows.

    The current implementation is intentionally dependency-free and supports Python files through
    AST analysis. It provides useful symbol-level behavior now while leaving room for a real
    language-server backend later.
    """

    name = "lsp"
    description = (
        "Semantic code query interface for Python symbols: definitions, references, hover, "
        "document symbols, project symbol search, and syntax diagnostics."
    )
    risk_level = "read"
    tags = ("code", "lsp", "read", "semantic")

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": (
                        "One of diagnostics, document_symbols, find_references, find_symbol, "
                        "go_to_definition, hover."
                    ),
                },
                "file_path": {"type": "string", "description": "Source file path."},
                "line": {"type": "integer", "description": "Zero-based line number."},
                "character": {"type": "integer", "description": "Zero-based character offset."},
                "symbol_name": {
                    "type": "string",
                    "description": "Symbol name for find_symbol, or an explicit target for definition/reference lookup.",
                },
                "project_root": {
                    "type": "string",
                    "description": "Optional project root to scan. Defaults to the file's parent directory.",
                },
                "max_results": {"type": "integer", "description": "Maximum results to return."},
            },
            "required": ["operation", "file_path"],
        }

    async def execute(
        self,
        operation: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
        symbol_name: str = "",
        project_root: str = "",
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> ToolResult:
        if operation not in SUPPORTED_OPERATIONS:
            return ToolResult(
                content=f"Unsupported LSP operation: {operation}",
                success=False,
                error="unsupported_operation",
                metadata={"supported_operations": sorted(SUPPORTED_OPERATIONS)},
            )

        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            return ToolResult(content=f"File not found: {path}", success=False, error="file_not_found")
        if path.suffix != ".py":
            return ToolResult(
                content=f"Semantic LSP currently supports Python files only: {path}",
                success=False,
                error="unsupported_language",
                metadata={"file_path": str(path), "language": path.suffix.lstrip(".")},
            )

        root = Path(project_root).expanduser().resolve() if project_root else path.parent
        if not root.exists() or not root.is_dir():
            return ToolResult(content=f"Project root not found: {root}", success=False, error="project_root_not_found")

        normalized_line = max(line, 0)
        normalized_character = max(character, 0)
        max_results = max(1, min(max_results, 1000))

        if operation == "diagnostics":
            return _diagnostics(path)
        if operation == "document_symbols":
            return _document_symbols(path)
        if operation == "find_symbol":
            return _find_symbol(root, symbol_name, max_results=max_results)

        target_name = symbol_name.strip() or _identifier_at_position(path, normalized_line, normalized_character)
        if not target_name:
            return ToolResult(
                content=f"No symbol found at {path}:{normalized_line}:{normalized_character}",
                success=False,
                error="symbol_not_found",
                metadata={"file_path": str(path), "line": normalized_line, "character": normalized_character},
            )

        if operation == "go_to_definition":
            return _go_to_definition(root, target_name, max_results=max_results)
        if operation == "find_references":
            return _find_references(root, target_name, max_results=max_results)
        if operation == "hover":
            return _hover(root, target_name, path, normalized_line, normalized_character)

        return ToolResult(content=f"Unsupported LSP operation: {operation}", success=False, error="unsupported_operation")


def _diagnostics(path: Path) -> ToolResult:
    try:
        _parse_python(path)
    except SyntaxError as exc:
        diagnostic = {
            "severity": "error",
            "message": exc.msg,
            "file_path": str(path),
            "line": max((exc.lineno or 1) - 1, 0),
            "character": max((exc.offset or 1) - 1, 0),
        }
        return ToolResult(
            content=_json([diagnostic]),
            success=False,
            error="syntax_error",
            metadata={"diagnostics": [diagnostic]},
        )
    return ToolResult(content="[]", metadata={"diagnostics": []})


def _document_symbols(path: Path) -> ToolResult:
    try:
        symbols = _symbols_in_file(path)
    except SyntaxError as exc:
        return _syntax_error_result(path, exc)
    data = [symbol.to_dict() for symbol in symbols]
    return ToolResult(content=_json(data), metadata={"symbols": data, "count": len(data)})


def _find_symbol(root: Path, symbol_name: str, *, max_results: int) -> ToolResult:
    query = symbol_name.strip()
    if not query:
        return ToolResult(content="symbol_name is required for find_symbol", success=False, error="missing_symbol_name")
    symbols, errors, scanned_files = _project_symbols(root, max_results=max_results, name_filter=query)
    data = [symbol.to_dict() for symbol in symbols]
    return ToolResult(
        content=_json(data),
        success=bool(data),
        error="" if data else "symbol_not_found",
        metadata={"symbols": data, "count": len(data), "scanned_files": scanned_files, "errors": errors},
    )


def _go_to_definition(root: Path, target_name: str, *, max_results: int) -> ToolResult:
    symbols, errors, scanned_files = _project_symbols(root, max_results=max_results, name_filter=target_name)
    data = [symbol.to_dict() for symbol in symbols]
    return ToolResult(
        content=_json(data),
        success=bool(data),
        error="" if data else "definition_not_found",
        metadata={
            "symbol_name": target_name,
            "definitions": data,
            "count": len(data),
            "scanned_files": scanned_files,
            "errors": errors,
        },
    )


def _find_references(root: Path, target_name: str, *, max_results: int) -> ToolResult:
    references: list[ReferenceInfo] = []
    errors: list[dict[str, str]] = []
    scanned_files = 0
    for path in _python_files(root):
        if scanned_files >= MAX_SCAN_FILES or len(references) >= max_results:
            break
        scanned_files += 1
        try:
            references.extend(_references_in_file(path, target_name, remaining=max_results - len(references)))
        except SyntaxError as exc:
            errors.append({"file_path": str(path), "error": exc.msg})
    data = [reference.to_dict() for reference in references]
    return ToolResult(
        content=_json(data),
        success=bool(data),
        error="" if data else "references_not_found",
        metadata={
            "symbol_name": target_name,
            "references": data,
            "count": len(data),
            "scanned_files": scanned_files,
            "errors": errors,
        },
    )


def _hover(root: Path, target_name: str, path: Path, line: int, character: int) -> ToolResult:
    definitions, errors, scanned_files = _project_symbols(root, max_results=10, name_filter=target_name)
    preferred = _symbol_covering_position(definitions, path, line, character) or (definitions[0] if definitions else None)
    if preferred is None:
        return ToolResult(
            content=f"No definition found for symbol `{target_name}`",
            success=False,
            error="definition_not_found",
            metadata={"symbol_name": target_name, "scanned_files": scanned_files, "errors": errors},
        )

    lines = [
        f"{preferred.kind} `{preferred.qualified_name}`",
        f"{preferred.file_path}:{preferred.line}:{preferred.character}",
    ]
    if preferred.signature:
        lines.append(f"signature: {preferred.signature}")
    if preferred.docstring:
        lines.append("")
        lines.append(preferred.docstring)
    return ToolResult(
        content="\n".join(lines),
        metadata={
            "symbol_name": target_name,
            "definition": preferred.to_dict(),
            "scanned_files": scanned_files,
            "errors": errors,
        },
    )


def _symbols_in_file(path: Path) -> list[SymbolInfo]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))
    collector = _SymbolCollector(path, source)
    collector.visit(tree)
    return collector.symbols


def _project_symbols(
    root: Path,
    *,
    max_results: int,
    name_filter: str,
) -> tuple[list[SymbolInfo], list[dict[str, str]], int]:
    symbols: list[SymbolInfo] = []
    errors: list[dict[str, str]] = []
    scanned_files = 0
    for path in _python_files(root):
        if scanned_files >= MAX_SCAN_FILES or len(symbols) >= max_results:
            break
        scanned_files += 1
        try:
            for symbol in _symbols_in_file(path):
                if _symbol_matches(symbol, name_filter):
                    symbols.append(symbol)
                    if len(symbols) >= max_results:
                        break
        except SyntaxError as exc:
            errors.append({"file_path": str(path), "error": exc.msg})
    return symbols, errors, scanned_files


def _symbol_matches(symbol: SymbolInfo, query: str) -> bool:
    return symbol.name == query or symbol.qualified_name == query or symbol.qualified_name.endswith(f".{query}")


def _references_in_file(path: Path, target_name: str, *, remaining: int) -> list[ReferenceInfo]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    references: list[ReferenceInfo] = []
    for node in ast.walk(tree):
        if len(references) >= remaining:
            break
        match = _reference_match(node, target_name)
        if match is None:
            continue
        line = max(getattr(node, "lineno", 1) - 1, 0)
        character = max(getattr(node, "col_offset", 0), 0)
        context = lines[line].strip() if line < len(lines) else ""
        references.append(
            ReferenceInfo(
                name=target_name,
                kind=match,
                file_path=str(path),
                line=line,
                character=character,
                context=context,
            )
        )
    return references


def _reference_match(node: ast.AST, target_name: str) -> str | None:
    if isinstance(node, ast.Name) and node.id == target_name:
        return "name"
    if isinstance(node, ast.Attribute) and node.attr == target_name:
        return "attribute"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target_name:
        return "definition"
    return None


def _identifier_at_position(path: Path, line: int, character: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line >= len(lines):
        return ""
    text = lines[line]
    character = min(max(character, 0), len(text))
    for match in IDENTIFIER_RE.finditer(text):
        if match.start() <= character <= match.end():
            return match.group(0)
    return ""


def _parse_python(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))


def _python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in SKIPPED_DIRS for part in path.parts):
            continue
        files.append(path.resolve())
        if len(files) >= MAX_SCAN_FILES:
            break
    return sorted(files)


def _symbol_covering_position(symbols: list[SymbolInfo], path: Path, line: int, character: int) -> SymbolInfo | None:
    path_text = str(path)
    for symbol in symbols:
        if symbol.file_path != path_text:
            continue
        if symbol.line == line and symbol.character <= character <= max(symbol.character + len(symbol.name), symbol.end_character):
            return symbol
    return None


def _syntax_error_result(path: Path, exc: SyntaxError) -> ToolResult:
    return ToolResult(
        content=f"Syntax error in {path}:{exc.lineno}:{exc.offset}: {exc.msg}",
        success=False,
        error="syntax_error",
        metadata={"file_path": str(path), "line": exc.lineno, "character": exc.offset, "message": exc.msg},
    )


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


class _SymbolCollector(ast.NodeVisitor):
    def __init__(self, path: Path, source: str) -> None:
        self.path = path
        self.source = source
        self.scope: list[str] = []
        self.symbols: list[SymbolInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._add_symbol(node, "class")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._add_symbol(node, "function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._add_symbol(node, "async_function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            for name in _target_names(target):
                self._add_assignment_symbol(name, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        for name in _target_names(node.target):
            self._add_assignment_symbol(name, node)
        self.generic_visit(node)

    def _add_symbol(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        signature = _signature(self.source, node) if kind != "class" else ""
        self.symbols.append(
            SymbolInfo(
                name=node.name,
                qualified_name=".".join([*self.scope, node.name]),
                kind=kind,
                file_path=str(self.path),
                line=max(node.lineno - 1, 0),
                character=node.col_offset,
                end_line=max(getattr(node, "end_lineno", node.lineno) - 1, 0),
                end_character=getattr(node, "end_col_offset", node.col_offset),
                signature=signature,
                docstring=(ast.get_docstring(node) or "").strip(),
            )
        )

    def _add_assignment_symbol(self, name: str, node: ast.Assign | ast.AnnAssign) -> None:
        if not name:
            return
        self.symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=".".join([*self.scope, name]),
                kind="variable",
                file_path=str(self.path),
                line=max(node.lineno - 1, 0),
                character=node.col_offset,
                end_line=max(getattr(node, "end_lineno", node.lineno) - 1, 0),
                end_character=getattr(node, "end_col_offset", node.col_offset),
            )
        )


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in node.elts:
            names.extend(_target_names(item))
        return names
    return []


def _signature(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    segment = ast.get_source_segment(source, node) or ""
    first_line = segment.splitlines()[0].strip() if segment else ""
    if first_line.endswith(":"):
        first_line = first_line[:-1]
    return first_line
