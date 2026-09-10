"""Run one real Bamboo query through the production runtime.

This script intentionally does not mock the LLM. It reads the user's normal
`~/.bamboo/configs/models.yaml`, calls the configured model, and lets the model
decide which Bamboo tools to call.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import anyio
import yaml

from bamboo.adapters.cli.main import _start_session
from bamboo.factory.event_bus import get_event_bus
from bamboo.helpers.constant import (
    PermissionRequestEvent,
    PermissionResultEvent,
    StepFinishEvent,
    StepStartEvent,
    TaskStatusChangeEvent,
    TextFinishEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from bamboo.helpers.requests_params import RunParams

DEFAULT_QUERY = """这是 Bamboo 真实端到端测试。

请真实调用 Bamboo 工具完成下面的事情：
1. 调用 todo_write 写入两项测试计划。
2. 调用 write 在项目目录下的 .bamboo/e2e-real-output.txt 写入文本 bamboo-real-e2e-token。
3. 调用 read 读取刚才写入的文件。
4. 最终回答必须包含 bamboo-real-e2e-token 和文件路径。

不要只口头说明，请真的调用工具。"""
DEFAULT_SUITE = Path(__file__).with_name("real_queries.yaml")


def main() -> int:
    args = parse_args()
    project = args.project.expanduser().resolve()
    if args.suite:
        return run_suite(args, project)
    case = {
        "id": "single",
        "query": args.query,
        "expect_tools": args.expect_tool,
        "expect_output": args.expect_output,
    }
    return run_case(case, args=args, project=project)


def run_suite(args: argparse.Namespace, project: Path) -> int:
    suite_path = args.suite.expanduser().resolve()
    document = yaml.safe_load(suite_path.read_text(encoding="utf-8")) or {}
    cases = document.get("cases", [])
    if not isinstance(cases, list):
        print(f"[real-e2e] invalid suite: {suite_path}")
        return 1
    selected = set(args.case or [])
    failures = 0
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            print(f"[real-e2e] skip invalid case at index {index}")
            failures += 1
            continue
        case_id = str(case.get("id") or index)
        if selected and case_id not in selected:
            continue
        print(f"\n========== real-e2e case {index}: {case_id} ==========")
        failures += 0 if run_case(case, args=args, project=project) == 0 else 1
    if failures:
        print(f"\n[real-e2e] suite failed: {failures} case(s)")
        return 1
    print("\n[real-e2e] suite completed")
    return 0


def run_case(case: dict[str, Any], *, args: argparse.Namespace, project: Path) -> int:
    prepare_fixtures(project, case)
    event_bus = get_event_bus()
    events: list[object] = []
    unsubscribe = event_bus.subscribe(lambda event: (_print_event(event), events.append(event)))
    query = str(case.get("query") or DEFAULT_QUERY).format(project=project)
    expected_tools = list(case.get("expect_tools") or [])
    expected_output = str(case.get("expect_output") or "")
    run_params = RunParams(
        platform="cli",
        message=query,
        project=str(project),
        model=args.model,
        permission=args.permission,
        yes_all=args.yes_all,
        no_stream=True,
        session_mode="chat",
    )

    async def run():
        return await _start_session(run_params)

    try:
        task = anyio.run(run)
    except Exception as exc:
        print(f"\n[real-e2e] failed case={case.get('id', 'single')}: {exc}")
        return 1
    finally:
        unsubscribe()

    tool_calls = [event.tool_name for event in events if isinstance(event, ToolCallEvent)]
    missing = [tool for tool in expected_tools if tool not in tool_calls]
    if missing:
        print(f"\n[real-e2e] missing expected tool calls: {', '.join(missing)}")
        print(f"[real-e2e] actual tool calls: {', '.join(tool_calls) or '(none)'}")
        return 2
    if expected_output and expected_output not in task.output:
        print(f"\n[real-e2e] final output did not contain: {expected_output}")
        print(f"[real-e2e] final output:\n{task.output}")
        return 3

    print("\n[real-e2e] completed")
    print(f"[real-e2e] task_id={task.task_id}")
    print(f"[real-e2e] session_id={task.session_id}")
    print(f"[real-e2e] status={task.status}")
    print(f"[real-e2e] tools={', '.join(tool_calls) or '(none)'}")
    print(f"[real-e2e] output:\n{task.output}")
    return 0


def prepare_fixtures(project: Path, case: dict[str, Any]) -> None:
    for relative_path, content in (case.get("fixture_files") or {}).items():
        path = project / str(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")
    pdf = case.get("fixture_pdf")
    if isinstance(pdf, dict):
        write_fixture_pdf(
            project / str(pdf.get("path")),
            title=str(pdf.get("title") or "Bamboo E2E PDF"),
            body=str(pdf.get("body") or "bamboo-real-pdf-token"),
        )


def write_fixture_pdf(path: Path, *, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to generate the real PDF workflow fixture") from exc
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 96), title, fontsize=18)
    page.insert_text((72, 140), body, fontsize=12)
    document.save(path)
    document.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real Bamboo E2E query with the configured LLM.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="User query to send to Bamboo.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project directory for the task.")
    parser.add_argument("--model", default="", help="Optional Bamboo model registration name.")
    parser.add_argument("--permission", default="default", help="Bamboo permission mode.")
    parser.add_argument("--yes-all", action=argparse.BooleanOptionalAction, default=True, help="Auto-approve safe test tools.")
    parser.add_argument("--suite", type=Path, nargs="?", const=DEFAULT_SUITE, help="Run query cases from a YAML suite.")
    parser.add_argument("--case", action="append", help="Run only one case id from --suite. Repeatable.")
    parser.add_argument(
        "--expect-tool",
        action="append",
        default=["todo_write", "write", "read"],
        help="Tool name expected at least once. Repeatable.",
    )
    parser.add_argument("--expect-output", default="bamboo-real-e2e-token", help="Text expected in the final answer.")
    return parser.parse_args()


def _print_event(event: object) -> None:
    if isinstance(event, TaskStatusChangeEvent):
        print(f"[task] {event.from_status} -> {event.to_status}")
    elif isinstance(event, StepStartEvent):
        print(f"[step:start] {event.step_id or event.step_index}")
    elif isinstance(event, StepFinishEvent):
        print(f"[step:finish] {event.summary or event.step_id or event.step_index}")
    elif isinstance(event, PermissionRequestEvent):
        print(f"[permission:request] {event.tool_name} risk={event.risk_level}")
    elif isinstance(event, PermissionResultEvent):
        print(f"[permission:result] {event.tool_name} approved={event.approved}")
    elif isinstance(event, ToolCallEvent):
        print(f"[tool:call] {event.tool_name} {event.tool_input}")
    elif isinstance(event, ToolResultEvent):
        print(f"[tool:result] {event.tool_name} {_preview(event.output)}")
    elif isinstance(event, ToolErrorEvent):
        print(f"[tool:error] {event.tool_name} {event.error}")
    elif isinstance(event, TextFinishEvent):
        print(f"[assistant] {_preview(event.content)}")


def _preview(value: str, limit: int = 500) -> str:
    text = value.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


if __name__ == "__main__":
    raise SystemExit(main())
