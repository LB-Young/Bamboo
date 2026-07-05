"""Post-task knowledge curation using a restricted subagent."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from bamboo.factory.task_factory import Task
from bamboo.helpers.constant import KnowledgeUpdateErrorEvent, KnowledgeUpdateEvent
from bamboo.memory.manager import (
    CHAT_TEMPLATE_NAMES,
    PROJECT_TEMPLATE_NAMES,
    MemoryManager,
)

if TYPE_CHECKING:
    from bamboo.runtime.runtime_context import RuntimeContext

KnowledgeScope = Literal["chat", "project-global", "project-current"]
KnowledgeRunner = Callable[[str], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class KnowledgeUpdateRequest:
    """One validated append request."""

    scope: KnowledgeScope
    file: str
    content: str
    operation: str = "append"


@dataclass(frozen=True, slots=True)
class KnowledgeSubagentResult:
    """Summary of one knowledge curation run."""

    applied: int
    rejected: int
    skip_reason: str = ""


class KnowledgeSubagent:
    """Runs the knowledge-curator subagent and applies safe md updates."""

    def __init__(
        self,
        *,
        runtime_context: "RuntimeContext | None" = None,
        memory_manager: MemoryManager | None = None,
        subagent_name: str = "knowledge-curator",
        runner: KnowledgeRunner | None = None,
    ) -> None:
        self.runtime_context = runtime_context
        self.memory_manager = memory_manager or (
            runtime_context.memory_manager if runtime_context is not None and isinstance(runtime_context.memory_manager, MemoryManager) else MemoryManager()
        )
        self.subagent_name = subagent_name
        self.runner = runner

    async def maybe_update(self, task: Task) -> KnowledgeSubagentResult:
        """Run curation and apply any validated updates. Never raises to caller."""
        try:
            output = await self._run_curator(task)
            updates, skip_reason = self._parse_output(output)
            applied = 0
            rejected = 0
            for raw_update in updates:
                try:
                    update = self._validate_update(raw_update, task)
                    self._append_update(task, update)
                    applied += 1
                    await self._emit_update(task, update, status="applied")
                except Exception as exc:
                    rejected += 1
                    await self._emit_error(
                        task,
                        scope=str(raw_update.get("scope", "")) if isinstance(raw_update, dict) else "",
                        file=str(raw_update.get("file", "")) if isinstance(raw_update, dict) else "",
                        reason=str(exc),
                    )
            return KnowledgeSubagentResult(applied=applied, rejected=rejected, skip_reason=skip_reason)
        except Exception as exc:
            await self._emit_error(task, scope="", file="", reason=str(exc))
            return KnowledgeSubagentResult(applied=0, rejected=1, skip_reason="")

    async def _run_curator(self, task: Task) -> str:
        prompt = self._build_prompt(task)
        if self.runner is not None:
            return await self.runner(prompt)
        if self.runtime_context is None:
            raise RuntimeError("KnowledgeSubagent requires runtime_context or runner")
        if self.runtime_context.subagent_registry is None:
            raise RuntimeError("No subagent registry is configured")
        from bamboo.runtime.subagent_runtime import SubagentRuntime

        result = await SubagentRuntime(
            parent_context=self.runtime_context,
            parent_task=task,
            registry=self.runtime_context.subagent_registry,
        ).run(
            subagent_type=self.subagent_name,
            description="Extract stable memory knowledge updates from the completed turn.",
            prompt=prompt,
        )
        return result.output

    def _build_prompt(self, task: Task) -> str:
        turn = self._latest_turn(task)
        knowledge_files = self.memory_manager.load_knowledge_files_for_retrieval(task.session)
        existing = "\n\n".join(f"## {file.relative_path}\n{file.content}" for file in knowledge_files) or "(none)"
        return (
            "You are the Bamboo knowledge curator. Decide whether the completed turn contains stable, reusable "
            "knowledge worth appending to editable memory markdown files.\n\n"
            "Return only JSON with this shape:\n"
            '{"updates":[{"scope":"project-current","file":"decisions.md","operation":"append","content":"- ... source: session_id/task_id"}],"skip_reason":""}\n\n'
            "Rules:\n"
            "- Use operation append only.\n"
            "- Every content entry must include exact source: session_id/task_id.\n"
            "- Do not copy large tool output.\n"
            "- If nothing stable should be remembered, return updates=[] and a skip_reason.\n"
            "- Valid scopes: chat, project-global, project-current.\n\n"
            f"Completed turn:\n{json.dumps(turn, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
            f"Existing knowledge:\n{existing}"
        )

    def _latest_turn(self, task: Task) -> dict[str, Any]:
        store = task.session.memory_store
        if store is None:
            return {
                "session_id": task.session_id,
                "task_id": task.task_id,
                "user_message": task.user_query,
                "assistant_answer": task.output,
                "error": task.error,
            }
        turns = [turn for turn in store.load_turns() if turn.get("task_id") == task.task_id]
        if turns:
            return turns[-1]
        return {
            "session_id": task.session_id,
            "task_id": task.task_id,
            "user_message": task.user_query,
            "assistant_answer": task.output,
            "error": task.error,
        }

    def _parse_output(self, output: str) -> tuple[list[dict[str, Any]], str]:
        payload = self._extract_json(output)
        updates = payload.get("updates", [])
        if not isinstance(updates, list):
            raise ValueError("knowledge curator updates must be a list")
        normalized = [item for item in updates if isinstance(item, dict)]
        return normalized, str(payload.get("skip_reason", "") or "")

    def _extract_json(self, output: str) -> dict[str, Any]:
        text = output.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end < start:
                raise ValueError("knowledge curator did not return JSON")
            payload = json.loads(text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("knowledge curator JSON must be an object")
        return payload

    def _validate_update(self, raw: dict[str, Any], task: Task) -> KnowledgeUpdateRequest:
        scope = str(raw.get("scope", "")).strip()
        file_name = str(raw.get("file", "")).strip()
        operation = str(raw.get("operation", "append")).strip() or "append"
        content = str(raw.get("content", "")).strip()
        if operation != "append":
            raise ValueError("only append operation is supported")
        if scope not in self._allowed_scopes(task):
            raise ValueError(f"scope not allowed: {scope}")
        allowed_files = CHAT_TEMPLATE_NAMES if scope == "chat" else PROJECT_TEMPLATE_NAMES
        if file_name not in allowed_files:
            raise ValueError(f"knowledge file not allowed: {file_name}")
        if Path(file_name).is_absolute() or ".." in Path(file_name).parts or not file_name.endswith(".md"):
            raise ValueError("invalid knowledge file path")
        if not content:
            raise ValueError("knowledge content is empty")
        if f"source: {task.session_id}/{task.task_id}" not in content:
            raise ValueError("knowledge content must include source: session_id/task_id")
        return KnowledgeUpdateRequest(
            scope=scope,  # type: ignore[arg-type]
            file=file_name,
            content=content,
            operation=operation,
        )

    def _allowed_scopes(self, task: Task) -> set[str]:
        prompt_mode = task.session.context.metadata.get("prompt_mode", "chat")
        if prompt_mode == "project":
            return {"project-global", "project-current"}
        return {"chat"}

    def _append_update(self, task: Task, update: KnowledgeUpdateRequest) -> None:
        target_dir = self._target_dir(task, update.scope)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / update.file
        if not self.memory_manager.ensure_knowledge_templates(self._scope_for_update(task, update.scope), target_dir):
            raise ValueError("failed to ensure knowledge templates")
        existing = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
        separator = "" if existing.endswith("\n") or not existing else "\n"
        new_content = f"{existing}{separator}{update.content}\n"
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        temp_path.write_text(new_content, encoding="utf-8")
        temp_path.replace(target_path)

    def _target_dir(self, task: Task, scope: str) -> Path:
        memory_scope = self.memory_manager.resolve_scope(task.session)
        if scope == "chat":
            return self.memory_manager.memory_root / "dates" / "chat" / "knowledge"
        if scope == "project-global":
            return self.memory_manager.memory_root / "projects" / "knowledge"
        if scope == "project-current":
            return self.memory_manager.memory_root / "projects" / memory_scope.project_hash / "knowledge"
        raise ValueError(f"unsupported scope: {scope}")

    def _scope_for_update(self, task: Task, scope: str):
        from bamboo.memory.scope import MemoryScope

        if scope == "chat":
            return MemoryScope(kind="chat", root=self.memory_manager.memory_root / "dates")
        memory_scope = self.memory_manager.resolve_scope(task.session)
        return MemoryScope(
            kind="project",
            root=self.memory_manager.memory_root / "projects",
            project_hash=memory_scope.project_hash if scope == "project-current" else "",
            project_root=memory_scope.project_root,
        )

    async def _emit_update(self, task: Task, update: KnowledgeUpdateRequest, *, status: str) -> None:
        if self.runtime_context is None:
            return
        await self.runtime_context.event_bus.emit(
            KnowledgeUpdateEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                scope=update.scope,
                file=update.file,
                operation=update.operation,
                status=status,
            )
        )

    async def _emit_error(self, task: Task, *, scope: str, file: str, reason: str) -> None:
        if self.runtime_context is None:
            return
        await self.runtime_context.event_bus.emit(
            KnowledgeUpdateErrorEvent(
                session_id=task.session_id,
                task_id=task.task_id,
                scope=scope,
                file=file,
                reason=reason,
            )
        )
