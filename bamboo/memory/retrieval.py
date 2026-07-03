"""Lightweight retrieval over memory knowledge and source logs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bamboo.factory.session import Session
from bamboo.memory.manager import MemoryManager
from bamboo.memory.source_log import search_source_logs

MemoryRetrievalSource = Literal["knowledge", "source_log", "all"]


@dataclass(frozen=True, slots=True)
class MemoryRetrievalMatch:
    """One retrieved memory item."""

    source: str
    origin: str
    content: str
    score: int
    session_id: str = ""
    task_id: str = ""


def retrieve_memory(
    *,
    query: str,
    session: Session,
    memory_manager: MemoryManager,
    source: MemoryRetrievalSource = "knowledge",
    limit: int = 5,
) -> list[MemoryRetrievalMatch]:
    """Retrieve memory from knowledge md files and/or source logs."""
    normalized_source = source if source in {"knowledge", "source_log", "all"} else "knowledge"
    safe_limit = max(1, min(limit, 20))
    matches: list[MemoryRetrievalMatch] = []
    if normalized_source in {"knowledge", "all"}:
        matches.extend(_search_knowledge(query, session, memory_manager, limit=safe_limit))
    if normalized_source in {"source_log", "all"} and len(matches) < safe_limit:
        remaining = safe_limit - len(matches)
        scope = memory_manager.resolve_scope(session)
        for match in search_source_logs(query, scope, limit=remaining):
            matches.append(
                MemoryRetrievalMatch(
                    source=match.source,
                    origin="source_log",
                    content=match.content,
                    score=match.score,
                    session_id=match.session_id,
                    task_id=match.task_id,
                )
            )
    return sorted(matches, key=lambda match: match.score, reverse=True)[:safe_limit]


def _search_knowledge(
    query: str,
    session: Session,
    memory_manager: MemoryManager,
    *,
    limit: int,
) -> list[MemoryRetrievalMatch]:
    terms = _terms(query)
    if not terms:
        return []
    matches: list[MemoryRetrievalMatch] = []
    for file in memory_manager.load_knowledge_files_for_retrieval(session):
        score = _score(file.content, terms)
        if score <= 0:
            continue
        matches.append(
            MemoryRetrievalMatch(
                source=str(file.path),
                origin="knowledge",
                content=f"{file.relative_path}\n{file.content}",
                score=score,
            )
        )
    return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]


def _terms(query: str) -> set[str]:
    return {part.lower() for part in query.split() if part.strip()}


def _score(content: str, terms: set[str]) -> int:
    normalized = content.lower()
    return sum(normalized.count(term) for term in terms)
