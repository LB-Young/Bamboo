"""Bamboo 命令行入口。

这个脚本负责注册 Typer 命令，并把用户输入转换为 RunParams 后交给
CLI adapter 和 TaskRuntime。真实执行逻辑不放在这里，避免入口层变重。
"""
import threading
import uuid
import webbrowser
from pathlib import Path

import anyio
import typer
from rich.console import Console
from rich.table import Table

from bamboo.adapters.cli.main import (
    _start_interactive_session,
    _start_resumed_interactive_session,
    _start_resumed_session,
    _start_session,
)
from bamboo.bkn.cli import app as bkn_app
from bamboo.cron import CronScheduler, CronStore, HeartbeatConfig
from bamboo.cron.autostart import start_embedded_cron
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.logging import setup_logging
from bamboo.helpers.requests_params import RunParams
from bamboo.llms.media import image_from_source, images_from_text, merge_images
from bamboo.memory.session_store import (
    SessionRecord,
    _load_record_metadata,
    build_replay_summary,
    find_latest_session_record,
    find_session_record,
    list_session_records,
)
from bamboo.userspace.userspace import ensure_userspace, get_configs_dir

setup_logging()

console = Console()
MSG_OPTION = typer.Option(None, "--msg", "-m", help="Initial message")
IMAGE_OPTION = typer.Option(None, "--image", help="Attach an image path or URL. Can be used multiple times.")
PROJECT_OPTION = typer.Option(None, "--project", "-p", help="Project path")
MODEL_OPTION = typer.Option(None, "--model", help="Override model")
PROVIDER_OPTION = typer.Option(None, "--provider", help="LLM provider: kimi/deepseek/minimax/mimo/gpt/claude")
PERMISSION_OPTION = typer.Option(None, "--permission", help="Permission mode: default/auto/bypass/yolo")
NO_STREAM_OPTION = typer.Option(False, "--no-stream", help="Disable streaming")
YES_ALL_OPTION = typer.Option(False, "--yes", "-y", help="Auto-confirm all permission prompts")
DEBUG_EVENTS_OPTION = typer.Option(False, "--debug-events", help="Print raw EventBus events for this session")
VERBOSITY_OPTION = typer.Option(
    "simple",
    "--verbosity",
    help="CLI output verbosity: full / medium / simple",
)
RESUME_OPTION = typer.Option(None, "--resume", help="Resume session id, latest/last, -1, or list")
RECORD_DIR_OPTION = typer.Option(None, "--record-dir", help="Explicit persisted session record directory")
SESSION_MODE_OPTION = typer.Option(
    SessionMode.auto,
    "--session-mode",
    help="Session mode: auto / project / chat",
)


app = typer.Typer(
    name="bamboo",
    help="Bamboo - AI-powered personal agent assistant",
    rich_markup_mode="rich",
    no_args_is_help=True
)
skill_app = typer.Typer(help="Manage Bamboo skills.", no_args_is_help=True)
app.add_typer(skill_app, name="skill")
cron_app = typer.Typer(help="Manage Bamboo cron jobs.", no_args_is_help=True)
app.add_typer(cron_app, name="cron")
models_app = typer.Typer(help="Discover and manage Bamboo model registrations.", no_args_is_help=True)
app.add_typer(models_app, name="models")
eval_app = typer.Typer(help="Run Bamboo eval and replay cases.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")
plugin_app = typer.Typer(help="Manage Bamboo plugin packages.", no_args_is_help=True)
app.add_typer(plugin_app, name="plugin")
app.add_typer(bkn_app, name="bkn")


@app.command()
def init() -> None:
    """初始化 Bamboo 用户目录。"""
    bamboo_root = get_configs_dir()
    overwrite = False
    if bamboo_root.exists():
        overwrite = typer.confirm(f"{bamboo_root} already exists. Overwrite it?", default=False)
        if not overwrite:
            console.print(f"[yellow]init cancelled[/yellow] existing directory kept: {bamboo_root}")
            raise typer.Exit(0)
    layout = ensure_userspace(overwrite=overwrite)
    console.print(f"[green]✓ 用户目录已就绪：{layout.root}[/green]")
    console.print("[dim]如需使用 browser 工具，可按需安装 Playwright Chromium 运行时：[/dim]")
    console.print("[bold dim]python -m playwright install chromium[/bold dim]")
    console.print("\n接下来请编辑配置文件，填写你的 LLM API Key等信息。")


@app.command()
def run(
    task: str = typer.Argument("", help="Task description to execute"),
    image: list[Path] | None = IMAGE_OPTION,
    debug_events: bool = DEBUG_EVENTS_OPTION,
    resume: str | None = RESUME_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
) -> None:
    """运行一个命令行任务。"""
    _start_default_cron()
    # CLI 命令只负责组装参数；任务生命周期由 TaskRuntime 负责。
    run_params = RunParams()
    run_params.platform = "cli"
    run_params.message = task
    run_params.images = merge_images(
        [image_from_source(str(path)) for path in (image or [])],
        images_from_text(run_params.message),
    )
    if run_params.images and not run_params.message.strip():
        raise typer.BadParameter("--image requires a task message")
    run_params.project = str(Path.cwd())
    run_params.model = ""
    run_params.provider = ""
    run_params.permission = ""
    run_params.no_stream = False
    run_params.yes_all = False
    run_params.debug_events = debug_events
    run_params.session_mode = SessionMode.chat
    run_params.task_id = str(uuid.uuid4())
    resolved_record_dir: str | None = str(record_dir) if record_dir else None
    if resume:
        selected = _resolve_resume_selector(
            resume,
            mode=run_params.session_mode_value,
            project_path=None,
            record_dir=record_dir,
        )
        if selected is None:
            return
        run_params.session_id = selected.session_id
        run_params.session_mode = selected.mode or run_params.session_mode
        run_params.project = str(selected.project_root or Path.cwd())
        resolved_record_dir = str(selected.record_dir)
    else:
        run_params.session_id = str(uuid.uuid4())

    if resume:
        created_task = anyio.run(_run_resumed_session, run_params, resolved_record_dir)
    else:
        created_task = anyio.run(_start_session, run_params)
    console.print(
        f"[green]task completed[/green] task_id={created_task.task_id} session_id={created_task.session_id}"
    )


@app.command()
def main(
    message: str | None = MSG_OPTION,
    image: list[Path] | None = IMAGE_OPTION,
    project: Path | None = PROJECT_OPTION,
    model: str | None = MODEL_OPTION,
    provider: str | None = PROVIDER_OPTION,
    permission: str | None = PERMISSION_OPTION,
    no_stream: bool = NO_STREAM_OPTION,
    yes_all: bool = YES_ALL_OPTION,
    debug_events: bool = DEBUG_EVENTS_OPTION,
    verbosity: str = VERBOSITY_OPTION,
    session_mode: SessionMode = SESSION_MODE_OPTION,
    resume: str | None = RESUME_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
) -> None:
    """启动 Bamboo 会话；无 --msg 时进入交互式命令行对话。"""
    run_params = RunParams()
    run_params.platform = "cli"
    run_params.message = message or ""
    run_params.images = merge_images(
        [image_from_source(str(path)) for path in (image or [])],
        images_from_text(run_params.message),
    )
    if run_params.images and not run_params.message.strip():
        raise typer.BadParameter("--image requires --msg")
    run_params.project = str(project or Path.cwd())
    run_params.model = model or ""
    run_params.provider = provider or ""
    run_params.permission = permission or "default"
    run_params.no_stream = no_stream
    run_params.yes_all = yes_all
    run_params.debug_events = debug_events
    normalized_verbosity = verbosity.strip().lower()
    if normalized_verbosity not in {"full", "medium", "simple"}:
        raise typer.BadParameter("--verbosity must be full, medium, or simple")
    run_params.verbosity = normalized_verbosity
    run_params.session_mode = session_mode
    run_params.task_id = str(uuid.uuid4())
    mode_value = run_params.session_mode_value
    project_path = Path(run_params.project) if mode_value == SessionMode.project.value else None
    resolved_record_dir: str | None = str(record_dir) if record_dir else None
    if resume:
        selected = _resolve_resume_selector(
            resume,
            mode=mode_value,
            project_path=project_path,
            record_dir=record_dir,
        )
        if selected is None:
            return
        run_params.session_id = selected.session_id
        run_params.session_mode = selected.mode or run_params.session_mode
        run_params.project = str(selected.project_root or Path.cwd())
        resolved_record_dir = str(selected.record_dir)
    else:
        run_params.session_id = str(uuid.uuid4())

    _start_default_cron()
    if run_params.message:
        if resume:
            anyio.run(_run_resumed_session, run_params, resolved_record_dir)
        else:
            anyio.run(_start_session, run_params)
        return

    if resume:
        anyio.run(_run_resumed_interactive_session, run_params, resolved_record_dir)
        return

    anyio.run(_start_interactive_session, run_params)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def replay(
    session_id: str | None = typer.Argument(None, help="Session id, latest/last, negative index, or list"),
    mode: SessionMode = SESSION_MODE_OPTION,
    project: Path | None = PROJECT_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
    json_output: bool = typer.Option(False, "--json", help="Print raw replay summary JSON"),
    limit: int = typer.Option(10, "--limit", help="Number of recent sessions to list when SESSION_ID is omitted"),
) -> None:
    """离线回放一个已持久化 session；支持 list/latest/-1 等选择器。"""
    mode_value = mode.value if isinstance(mode, SessionMode) else str(mode)
    project_path = project if mode_value == SessionMode.project.value else None
    if not session_id:
        _print_recent_sessions(mode=mode_value, project_path=project_path, limit=limit)
        return

    if session_id == "list":
        _print_recent_sessions(mode=mode_value, project_path=project_path, limit=1000)
        return

    selected = _select_session_record(session_id, mode=mode_value, project_path=project_path)
    if selected is not None:
        session_id = selected.session_id
        resolved = selected.record_dir
    else:
        resolved = find_session_record(
            session_id,
            mode=mode_value,
            project_path=project_path,
            record_dir=record_dir,
        )
    if resolved is None:
        raise typer.BadParameter(f"Session not found: {session_id}")
    summary = build_replay_summary(resolved)
    if json_output:
        import json

        console.print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    session = summary["session"]
    console.print(f"[bold]session[/bold] {session.get('session_id', session_id)}")
    console.print(f"[dim]record_dir[/dim] {summary['record_dir']}")
    console.print(
        "[dim]counts[/dim] "
        f"messages={summary['message_count']} events={summary['event_count']} "
        f"tasks={summary['task_count']} turns={summary['turn_count']} "
        f"llm={summary['llm_request_count']}/{summary['llm_response_count']} "
        f"tools={summary['tool_call_count']}/{summary['tool_result_count']}"
    )
    for turn in summary["turns"]:
        console.print(f"\n[cyan]turn[/cyan] {turn.get('task_id', '')} [{turn.get('status', '')}]")
        if turn.get("user_message"):
            console.print(f"[bold]user[/bold] {turn['user_message']}")
        if turn.get("assistant_answer"):
            console.print(f"[bold]assistant[/bold] {turn['assistant_answer']}")
        if turn.get("error"):
            console.print(f"[red]error[/red] {turn['error']}")


def _select_session_record(selector: str, *, mode: str, project_path: Path | None) -> SessionRecord | None:
    if selector in {"latest", "last"}:
        latest = find_latest_session_record(mode=mode, project_path=project_path)
        if latest is None:
            raise typer.BadParameter("No persisted sessions found")
        return latest
    if not _is_negative_index(selector):
        return None
    index = abs(int(selector))
    records = list_session_records(mode=mode, project_path=project_path, limit=index)
    if len(records) < index:
        raise typer.BadParameter(f"No session found for {selector}; run 'bamboo replay list' to see available sessions")
    return records[index - 1]


def _resolve_resume_selector(
    selector: str,
    *,
    mode: str,
    project_path: Path | None,
    record_dir: Path | None,
) -> SessionRecord | None:
    """Resolve main/run --resume using replay-compatible selectors."""
    if selector == "list":
        _print_recent_sessions(mode=mode, project_path=project_path, limit=1000)
        return None
    selected = _select_session_record(selector, mode=mode, project_path=project_path)
    if selected is not None:
        return selected
    resolved = find_session_record(
        selector,
        mode=mode,
        project_path=project_path,
        record_dir=record_dir,
    )
    if resolved is None:
        raise typer.BadParameter(f"Session not found: {selector}")
    record = _load_record_metadata(resolved)
    if record is None:
        raise typer.BadParameter(f"Session record is invalid: {resolved}")
    return record


async def _run_resumed_session(run_params: RunParams, record_dir: str | None) -> object:
    return await _start_resumed_session(run_params, record_dir=record_dir)


async def _run_resumed_interactive_session(run_params: RunParams, record_dir: str | None) -> object:
    return await _start_resumed_interactive_session(run_params, record_dir=record_dir)


def _is_negative_index(value: str) -> bool:
    return len(value) > 1 and value.startswith("-") and value[1:].isdigit()


def _print_recent_sessions(*, mode: str, project_path: Path | None, limit: int) -> None:
    records = list_session_records(
        mode=mode,
        project_path=project_path,
        limit=limit,
    )
    if not records:
        console.print("[yellow]No persisted sessions found.[/yellow]")
        console.print("[dim]Run a task first, for example: bamboo main --msg \"hello\"[/dim]")
        return
    console.print("[bold]sessions[/bold]")
    console.print("[dim]Use: bamboo replay SESSION_ID | bamboo replay -1 | bamboo replay latest[/dim]")
    console.print("[dim]Resume: bamboo main --resume SESSION_ID | --resume -1 | --resume latest[/dim]\n")
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("index", no_wrap=True)
    table.add_column("session_id", no_wrap=True)
    table.add_column("mode", no_wrap=True)
    table.add_column("updated_at", no_wrap=True)
    table.add_column("topic")
    for index, record in enumerate(records, start=1):
        label = record.label.replace("\n", " ").strip()
        if len(label) > 70:
            label = label[:67] + "..."
        table.add_row(
            f"-{index}",
            record.session_id,
            record.mode or "-",
            record.updated_at or record.created_at,
            label,
        )
    console.print(table)


@eval_app.command("run")
def eval_run(
    case_dir: Path = typer.Argument(..., help="Eval case directory containing input.yaml and expected.yaml"),
    json_output: bool = typer.Option(False, "--json", help="Print raw eval report JSON"),
) -> None:
    """运行一个 eval/replay case。"""
    from bamboo.eval import EvalRunner, load_eval_case, render_report

    case = load_eval_case(case_dir)

    async def _run():
        return await EvalRunner().run_case(case)

    report = anyio.run(_run)
    console.print(render_report(report, json_output=json_output))
    if not report.passed:
        raise typer.Exit(1)


@eval_app.command("export")
def eval_export(
    session_id: str = typer.Argument(..., help="Persisted session id to export"),
    case_dir: Path = typer.Argument(..., help="Target eval case directory"),
    mode: SessionMode = SESSION_MODE_OPTION,
    project: Path | None = PROJECT_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing case files"),
) -> None:
    """把已有 session trace 导出为 replay eval fixture。"""
    from bamboo.eval import export_replay_case

    case = export_replay_case(
        session_id=session_id,
        case_dir=case_dir,
        mode=mode.value if isinstance(mode, SessionMode) else str(mode),
        project_path=project if mode == SessionMode.project else None,
        record_dir=record_dir,
        overwrite=overwrite,
    )
    console.print(f"[green]eval case exported[/green] {case.case_dir}")
    console.print(f"[dim]fixture[/dim] {case.input.fixture}")


@app.command()
def version() -> None:
    """输出当前 Bamboo 版本。"""
    from bamboo import __version__
    print(f"Bamboo v{__version__}")


@app.command("app")
def desktop_app(
    message: str | None = MSG_OPTION,
    image: list[Path] | None = IMAGE_OPTION,
    project: Path | None = PROJECT_OPTION,
    model: str | None = MODEL_OPTION,
    provider: str | None = PROVIDER_OPTION,
    permission: str | None = PERMISSION_OPTION,
    session_mode: SessionMode = SESSION_MODE_OPTION,
) -> None:
    """启动 Bamboo 本地桌面 App 窗口。"""
    from bamboo.adapters.app import AppDependencyError, launch_app

    _start_default_cron()
    try:
        launch_app(
            project=project,
            model=model or "",
            provider=provider or "",
            permission=permission or "default",
            session_mode=session_mode,
            initial_message=message or "",
            image_paths=image or [],
        )
    except AppDependencyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command("app-fancy")
def desktop_app_fancy(
    message: str | None = MSG_OPTION,
    image: list[Path] | None = IMAGE_OPTION,
    project: Path | None = PROJECT_OPTION,
    model: str | None = MODEL_OPTION,
    provider: str | None = PROVIDER_OPTION,
    permission: str | None = PERMISSION_OPTION,
    session_mode: SessionMode = SESSION_MODE_OPTION,
) -> None:
    """启动 Bamboo 高级本地桌面 App 窗口。"""
    from bamboo.adapters.app_fancy import AppDependencyError, launch_app

    _start_default_cron()
    try:
        launch_app(
            project=project,
            model=model or "",
            provider=provider or "",
            permission=permission or "default",
            session_mode=session_mode,
            initial_message=message or "",
            image_paths=image or [],
        )
    except AppDependencyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Web server host"),
    port: int = typer.Option(8899, "--port", "-p", help="Web server port"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open the Web UI in a browser"),
) -> None:
    """启动 Bamboo Web 对话入口。"""
    import uvicorn

    _start_default_cron()
    url = f"http://{host}:{port}"
    console.print(f"[green]Bamboo Web[/green] {url}")
    if not no_browser:
        _open_url_later(url)
    uvicorn.run("bamboo.adapters.web.app:app", host=host, port=port, reload=reload)


@app.command("web-fancy")
def web_fancy(
    host: str = typer.Option("127.0.0.1", "--host", help="Web server host"),
    port: int = typer.Option(8899, "--port", "-p", help="Web server port"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open the Web UI in a browser"),
) -> None:
    """启动 Bamboo Fancy Web 对话入口。"""
    import uvicorn

    _start_default_cron()
    url = f"http://{host}:{port}"
    console.print(f"[green]Bamboo Fancy Web[/green] {url}")
    if not no_browser:
        _open_url_later(url)
    uvicorn.run("bamboo.adapters.web_fancy.app:app", host=host, port=port, reload=reload)


@app.command()
def docs(
    host: str = typer.Option("127.0.0.1", "--host", help="Web server host"),
    port: int = typer.Option(8899, "--port", "-p", help="Web server port"),
    no_server: bool = typer.Option(False, "--no-server", help="Only open the docs URL; do not start Web server"),
) -> None:
    """启动 Web 服务并在浏览器中打开 Bamboo 使用说明页。"""
    url = f"http://{host}:{port}/docs"
    if no_server:
        console.print(f"[green]Bamboo docs[/green] {url}")
        _open_url(url)
        return
    import uvicorn

    _start_default_cron()
    console.print(f"[green]Bamboo docs[/green] {url}")
    console.print("[dim]Starting Bamboo Web for docs. Press Ctrl+C to stop.[/dim]")
    _open_url_later(url)
    uvicorn.run("bamboo.adapters.web.app:app", host=host, port=port, reload=False)


def _open_url_later(url: str, *, delay_seconds: float = 0.8) -> None:
    timer = threading.Timer(delay_seconds, _open_url, args=(url,))
    timer.daemon = True
    timer.start()


def _open_url(url: str) -> None:
    opened = webbrowser.open(url)
    if not opened:
        console.print("[yellow]browser open request was not accepted; open the URL manually[/yellow]")


def _start_default_cron() -> None:
    start_embedded_cron(interval_seconds=30.0)


@cron_app.command("start")
def cron_start(
    interval: float = typer.Option(30.0, "--interval", help="Heartbeat interval in seconds"),
) -> None:
    """启动 Cron heartbeat 调度器。"""
    store = CronStore()
    store.ensure()
    scheduler = CronScheduler(store=store)
    console.print(f"[green]cron heartbeat started[/green] interval={interval}s jobs={store.jobs_path}")
    heartbeat = HeartbeatConfig(interval_seconds=interval)

    async def _run() -> None:
        await scheduler.run_forever(heartbeat=heartbeat)

    anyio.run(_run)


@cron_app.command("tick")
def cron_tick() -> None:
    """执行一次 Cron 调度检查并退出。"""
    store = CronStore()
    store.ensure()
    records = anyio.run(CronScheduler(store=store).tick)
    console.print(f"[green]cron tick complete[/green] jobs={len(records)}")


@cron_app.command("list")
def cron_list() -> None:
    """列出 Cron jobs。"""
    store = CronStore()
    for job in store.load_jobs():
        status = "enabled" if job.enabled else "disabled"
        console.print(f"{job.name}\t{status}\t{job.schedule}\t{job.session}\t{job.prompt}")


@cron_app.command("add")
def cron_add(
    name: str = typer.Argument(..., help="Cron job name"),
    schedule: str = typer.Option(..., "--schedule", "-s", help="Five-field cron expression"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Prompt to run"),
    project: Path | None = typer.Option(None, "--project", help="Project path"),
    session: str = typer.Option("isolated", "--session", help="isolated/main"),
    delivery: str | None = typer.Option(None, "--delivery", help="Delivery mode: isolated/main"),
    session_id: str = typer.Option("", "--session-id", help="Target session id for main delivery"),
    record_dir: Path | None = typer.Option(None, "--record-dir", help="Target session record directory"),
    replace: bool = typer.Option(False, "--replace", help="Replace existing job"),
) -> None:
    """注册一个 Cron job。"""
    from bamboo.cron import CronJob

    resolved_delivery = delivery or session
    if session not in {"isolated", "main"}:
        raise typer.BadParameter("session must be isolated/main")
    if resolved_delivery not in {"isolated", "main"}:
        raise typer.BadParameter("delivery must be isolated/main")
    store = CronStore()
    store.register_job(
        CronJob(
            name=name,
            schedule=schedule,
            prompt=prompt,
            project=str(project) if project else "",
            session=session,  # type: ignore[arg-type]
            delivery=resolved_delivery,  # type: ignore[arg-type]
            session_id=session_id,
            record_dir=str(record_dir) if record_dir else "",
        ),
        replace=replace,
    )
    console.print(f"[green]cron job registered[/green] {name}")


@cron_app.command("enable")
def cron_enable(name: str = typer.Argument(..., help="Cron job name")) -> None:
    """启用 Cron job。"""
    job = CronStore().set_enabled(name, True)
    console.print(f"[green]cron job enabled[/green] {job.name}")


@cron_app.command("disable")
def cron_disable(name: str = typer.Argument(..., help="Cron job name")) -> None:
    """禁用 Cron job。"""
    job = CronStore().set_enabled(name, False)
    console.print(f"[yellow]cron job disabled[/yellow] {job.name}")


@models_app.command("discover")
def models_discover(
    provider: str = typer.Argument(..., help="Local provider: ollama/vllm"),
    base_url: str | None = typer.Option(None, "--base-url", help="Override local server base URL"),
    timeout: float = typer.Option(5.0, "--timeout", help="Discovery request timeout in seconds"),
    write: bool = typer.Option(False, "--write", help="Write discovered models to ~/.bamboo/configs/models.yaml"),
    set_default: bool = typer.Option(False, "--set-default", help="Set the first written model as default"),
    replace: bool = typer.Option(False, "--replace", help="Replace existing registrations with the same name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation when writing models.yaml"),
) -> None:
    """显式发现本地 Ollama/vLLM 模型，并可选写入 models.yaml。"""
    from bamboo.adapters.cli.models import discover_local_models, format_discovery_result, write_discovery_result

    normalized = provider.strip().lower()
    if normalized not in {"ollama", "vllm"}:
        raise typer.BadParameter("provider must be ollama/vllm")

    async def _discover():
        return await discover_local_models(normalized, base_url=base_url, timeout=timeout)

    result = anyio.run(_discover)
    console.print(format_discovery_result(result))
    if not result.ok:
        raise typer.Exit(1)
    if not write:
        return
    config_path = get_configs_dir() / "models.yaml"
    if not yes:
        confirmed = typer.confirm(f"Write {len(result.models)} discovered model(s) to {config_path}?", default=False)
        if not confirmed:
            console.print("[yellow]models.yaml unchanged[/yellow]")
            return
    write_result = write_discovery_result(
        result,
        config_path=config_path,
        set_default=set_default,
        replace=replace,
    )
    console.print(f"[green]models.yaml updated[/green] {write_result.path}")
    if write_result.backup_path is not None:
        console.print(f"[dim]backup[/dim] {write_result.backup_path}")
    if write_result.added:
        console.print(f"[dim]added[/dim] {', '.join(write_result.added)}")
    if write_result.skipped:
        console.print(f"[yellow]skipped existing[/yellow] {', '.join(write_result.skipped)}")
    console.print(f"[dim]default_model[/dim] {write_result.default_model}")


@skill_app.command("create")
def skill_create(
    name: str = typer.Argument(..., help="Skill name"),
    description: str = typer.Option("", "--description", "-d", help="Skill description"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing skill files"),
) -> None:
    """创建 Skill 源目录和状态文件。"""
    from bamboo.skills import SkillCreator

    result = SkillCreator().create(name, description=description, overwrite=overwrite)
    console.print(f"[green]skill created[/green] {result.name} status={result.status}")
    console.print(f"[dim]source[/dim] {result.source_path}")
    console.print(f"[dim]state[/dim] {result.state_path}")


@skill_app.command("list")
def skill_list(include_inactive: bool = typer.Option(False, "--all", help="Show inactive skills")) -> None:
    """列出已发现的 Skills。"""
    from bamboo.skills.cli import list_skills

    for name, status, health, trust_level, description in list_skills(include_inactive=include_inactive):
        console.print(f"{name}\t{status}\t{health}\t{trust_level}\t{description}")


@skill_app.command("install")
def skill_install(
    identifier: str = typer.Argument(..., help="Skill source, e.g. local:/path/to/skill"),
    trust_level: str = typer.Option("community", "--trust", help="Trust level: trusted/community/local"),
    force: bool = typer.Option(False, "--force", help="Allow install despite non-safe scan findings"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing skill with the same name"),
) -> None:
    """安装外部 Skill，先进入 quarantine 并通过 SkillGuard 扫描。"""
    from bamboo.skills.cli import install_skill
    from bamboo.skills.guard import format_scan_report

    result = install_skill(identifier, trust_level=trust_level, force=force, overwrite=overwrite)
    console.print(format_scan_report(result.scan_result))
    if not result.installed:
        console.print(f"[red]skill install blocked[/red] {result.name}: {result.reason}")
        raise typer.Exit(1)
    console.print(f"[green]skill installed[/green] {result.name} -> {result.destination}")


@skill_app.command("scan")
def skill_scan(path: Path = typer.Argument(..., help="Local skill directory to scan")) -> None:
    """扫描本地 Skill 目录，不执行安装。"""
    from bamboo.skills.cli import scan_skill_path

    console.print(scan_skill_path(path))


@skill_app.command("show")
def skill_show(name: str = typer.Argument(..., help="Skill name")) -> None:
    """显示 Skill 定义和状态摘要。"""
    from bamboo.skills import create_skill_registry

    registry = create_skill_registry()
    definition = registry.get(name, include_inactive=True)
    if definition is None:
        raise typer.BadParameter(f"Skill not found: {name}")
    state = registry.store.load_state(name)
    validation = registry.store.load_validation(name)
    console.print(f"[bold]{definition.name}[/bold] ({definition.source})")
    console.print(definition.description)
    console.print(f"[dim]source[/dim] {definition.source_path}")
    if state is not None:
        console.print(f"[dim]status[/dim] {state.status} [dim]health[/dim] {state.health}")
    if validation is not None:
        console.print(f"[dim]validation[/dim] ok={validation.ok} errors={validation.errors} warnings={validation.warnings}")


@skill_app.command("validate")
def skill_validate(name: str = typer.Argument(..., help="Skill name")) -> None:
    """重新校验 Skill。"""
    from bamboo.skills import create_skill_registry
    from bamboo.skills.models import SkillUsageEvent
    from bamboo.skills.store import utc_now

    registry = create_skill_registry()
    definition = registry.get(name, include_inactive=True)
    if definition is None:
        raise typer.BadParameter(f"Skill not found: {name}")
    result = registry.validator.validate(definition)
    registry.store.save_validation(name, result)
    registry.store.append_usage(SkillUsageEvent(ts=utc_now(), event="validated", skill_name=name))
    console.print(f"[green]validation complete[/green] {name} ok={result.ok}")
    if result.errors:
        console.print(f"[red]errors[/red] {result.errors}")
    if result.warnings:
        console.print(f"[yellow]warnings[/yellow] {result.warnings}")


@skill_app.command("disable")
def skill_disable(name: str = typer.Argument(..., help="Skill name")) -> None:
    """禁用 Skill。"""
    from bamboo.skills import SkillStore

    state = SkillStore().disable(name)
    console.print(f"[yellow]skill disabled[/yellow] {name} status={state.status}")


@skill_app.command("enable")
def skill_enable(name: str = typer.Argument(..., help="Skill name")) -> None:
    """启用 Skill。"""
    from bamboo.skills import SkillStore

    state = SkillStore().enable(name)
    console.print(f"[green]skill enabled[/green] {name} status={state.status}")


@plugin_app.command("validate")
def plugin_validate(path: Path = typer.Argument(..., help="Local plugin directory")) -> None:
    """校验并扫描本地 Plugin，但不安装。"""
    from bamboo.plugins import PluginInstaller

    result = PluginInstaller().validate(path)
    _print_plugin_scan(result.scan_result)
    if not result.scan_result.ok:
        raise typer.Exit(1)


@plugin_app.command("install")
def plugin_install(
    path: Path = typer.Argument(..., help="Local plugin directory"),
    force: bool = typer.Option(False, "--force", help="Allow install despite dangerous scan findings"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing installed component targets"),
) -> None:
    """安装本地 Plugin 包，写入 lock 和 audit。"""
    from bamboo.plugins import PluginInstaller

    result = PluginInstaller().install(path, force=force, overwrite=overwrite)
    _print_plugin_scan(result.scan_result)
    if not result.installed:
        console.print(f"[red]plugin install blocked[/red] {result.name}: {result.reason}")
        raise typer.Exit(1)
    files = len(result.lock_entry.files) if result.lock_entry is not None else 0
    console.print(f"[green]plugin installed[/green] {result.name} files={files}")


@plugin_app.command("list")
def plugin_list() -> None:
    """列出已安装 Plugin。"""
    from bamboo.plugins import PluginInstaller

    for entry in PluginInstaller().list():
        console.print(f"{entry.name}\t{entry.version}\t{entry.scan_level}\tfiles={len(entry.files)}\t{entry.description}")


@plugin_app.command("show")
def plugin_show(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """显示已安装 Plugin 的 lock 摘要。"""
    from bamboo.plugins import PluginInstaller

    entry = PluginInstaller().show(name)
    if entry is None:
        raise typer.BadParameter(f"Plugin not installed: {name}")
    console.print(f"[bold]{entry.name}[/bold] {entry.version}")
    console.print(entry.description)
    console.print(f"[dim]publisher[/dim] {entry.publisher}")
    console.print(f"[dim]source[/dim] {entry.source}")
    console.print(f"[dim]installed_at[/dim] {entry.installed_at}")
    console.print(f"[dim]scan[/dim] {entry.scan_level}")
    if entry.permissions:
        console.print(f"[dim]permissions[/dim] {', '.join(entry.permissions)}")
    for installed_file in entry.files:
        console.print(f"{installed_file.component_type}\t{installed_file.target}")


@plugin_app.command("remove")
def plugin_remove(
    name: str = typer.Argument(..., help="Plugin name"),
    force: bool = typer.Option(False, "--force", help="Delete user-modified installed files too"),
) -> None:
    """卸载 Plugin，默认保留用户修改过的文件。"""
    from bamboo.plugins import PluginInstaller

    result = PluginInstaller().remove(name, force=force)
    if result.kept_files:
        console.print(f"[yellow]plugin partially removed[/yellow] {name}: {result.reason}")
        for path in result.kept_files:
            console.print(f"[yellow]kept modified[/yellow] {path}")
        raise typer.Exit(1)
    if not result.removed:
        console.print(f"[red]plugin remove failed[/red] {name}: {result.reason}")
        raise typer.Exit(1)
    console.print(f"[green]plugin removed[/green] {name} deleted={len(result.deleted_files)}")


def _print_plugin_scan(scan_result) -> None:
    """Render plugin scan result for CLI."""
    if not scan_result.findings:
        console.print(f"Plugin scan {scan_result.level}: no findings")
        return
    console.print(f"Plugin scan {scan_result.level}: {len(scan_result.findings)} finding(s)")
    for finding in scan_result.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path or "-"
        console.print(f"- [{finding.severity}] {finding.category} {location}: {finding.message}")


def debug_main(
    message: str | None = None,
    project: Path | None = None,
    model: str | None = None,
    provider: str | None = None,
    permission: str | None = None,
    no_stream: bool = False,
    yes_all: bool = False,
    debug_events: bool = False,
    session_mode: SessionMode = SessionMode.auto,
) -> None:
    """直接调用主流程的调试入口。

    该函数目前主要给 VS Code 断点调试使用；Typer 的真实 CLI 命令
    仍然通过 app() 注册的子命令进入。
    """

    run_params = RunParams()
    run_params.platform = "cli"
    run_params.message = message
    run_params.project = project
    run_params.model = model
    run_params.provider = provider
    run_params.permission = permission
    run_params.no_stream = no_stream
    run_params.yes_all = yes_all
    run_params.debug_events = debug_events
    run_params.session_mode = session_mode
    run_params.task_id = str(uuid.uuid4())
    run_params.session_id = str(uuid.uuid4())

    anyio.run(_start_session, run_params)



if __name__ == "__main__":
    app()
