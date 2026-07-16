"""Prepare and execute BKN-private action scripts."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from bamboo.bkn.models import BKNAction, BKNDefinition
from bamboo.bkn.validator import BKNValidationError


def list_actions(definition: BKNDefinition, *, entity_class: str | None = None) -> list[BKNAction]:
    """List actions allowed by manifest and optionally class binding."""
    allowlist = set(definition.manifest.action_allowlist) if definition.manifest else set(definition.actions)
    class_actions: set[str] | None = None
    if entity_class:
        spec = definition.ontology.classes.get(entity_class, {})
        values = spec.get("actions", []) if isinstance(spec, dict) else []
        class_actions = {item for item in values if isinstance(item, str)}
    actions: list[BKNAction] = []
    for name in sorted(definition.actions):
        if name not in allowlist:
            continue
        if class_actions is not None and name not in class_actions:
            continue
        actions.append(definition.actions[name])
    return actions


def prepare_action(definition: BKNDefinition, *, action_id: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and prepare an action execution plan without executing it."""
    action = _action(definition, action_id)
    script_path = _script_path(definition, action)
    cwd = _cwd(definition, action)
    args = arguments or {}
    _validate_arguments(action, args)
    risk_level = str(action.config.get("risk_level", "execute"))
    return {
        "platform_id": definition.platform_id or definition.name,
        "action_id": action.name,
        "script_path": str(script_path),
        "cwd": str(cwd),
        "arguments": args,
        "arguments_schema": action.config.get("arguments_schema", {}),
        "risk_level": risk_level,
        "description": action.description,
    }


async def execute_action(
    definition: BKNDefinition,
    *,
    action_id: str,
    arguments: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute a prepared BKN-private script."""
    plan = prepare_action(definition, action_id=action_id, arguments=arguments)
    env = {**os.environ, "BKN_ACTION_ARGS": json.dumps(plan["arguments"], ensure_ascii=False)}
    process = await asyncio.create_subprocess_exec(
        "/bin/sh",
        plan["script_path"],
        cwd=plan["cwd"],
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        stdout, stderr = b"", f"Action timed out after {timeout}s".encode()
    return {
        **plan,
        "exit_code": process.returncode if process.returncode is not None else 1,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
    }


def _action(definition: BKNDefinition, action_id: str) -> BKNAction:
    if definition.manifest and definition.manifest.status not in {"draft", "active"}:
        raise BKNValidationError(f"platform status {definition.manifest.status} does not allow actions")
    allowlist = set(definition.manifest.action_allowlist) if definition.manifest else set(definition.actions)
    if action_id not in allowlist:
        raise BKNValidationError(f"action {action_id} is not allowed by manifest")
    if action_id not in definition.actions:
        raise BKNValidationError(f"action {action_id} is not defined")
    return definition.actions[action_id]


def _script_path(definition: BKNDefinition, action: BKNAction) -> Path:
    entrypoint = str(action.config.get("entrypoint", action.config.get("script", "")))
    if not entrypoint:
        raise BKNValidationError(f"action {action.name} entrypoint is required")
    path = (definition.root / entrypoint).resolve()
    root = definition.root.resolve()
    if path != root and root not in path.parents:
        raise BKNValidationError(f"action {action.name} entrypoint escapes platform directory")
    if not path.is_file():
        raise BKNValidationError(f"action {action.name} script does not exist: {path}")
    return path


def _cwd(definition: BKNDefinition, action: BKNAction) -> Path:
    raw = str(action.config.get("cwd", "."))
    path = (definition.root / raw).resolve()
    root = definition.root.resolve()
    if path != root and root not in path.parents:
        raise BKNValidationError(f"action {action.name} cwd escapes platform directory")
    return path


def _validate_arguments(action: BKNAction, arguments: dict[str, Any]) -> None:
    schema = action.config.get("arguments_schema", {})
    if not isinstance(schema, dict):
        return
    required = schema.get("required", [])
    if isinstance(required, list):
        missing = [item for item in required if isinstance(item, str) and item not in arguments]
        if missing:
            raise BKNValidationError(f"action {action.name} missing required arguments: {', '.join(missing)}")
