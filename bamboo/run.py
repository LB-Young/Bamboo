"""Bamboo 命令行入口。

这个脚本负责注册 Typer 命令，并把用户输入转换为 RunParams 后交给
CLI adapter 和 TaskRuntime。真实执行逻辑不放在这里，避免入口层变重。
"""
import uuid
from pathlib import Path

import anyio
import typer
from rich.console import Console

from bamboo.adapters.cli.main import (
    _start_interactive_session,
    _start_resumed_interactive_session,
    _start_resumed_session,
    _start_session,
)
from bamboo.cron import CronScheduler, CronStore, HeartbeatConfig
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.logging import setup_logging
from bamboo.helpers.requests_params import RunParams
from bamboo.memory.session_store import build_replay_summary, find_session_record
from bamboo.userspace.userspace import ensure_userspace, get_configs_dir

setup_logging()

console = Console()
MSG_OPTION = typer.Option(None, "--msg", "-m", help="Initial message")
PROJECT_OPTION = typer.Option(None, "--project", "-p", help="Project path")
MODEL_OPTION = typer.Option(None, "--model", help="Override model")
PROVIDER_OPTION = typer.Option(None, "--provider", help="LLM provider: deepseek/minimax/gpt/claude")
PERMISSION_OPTION = typer.Option(None, "--permission", help="Permission mode: default/auto/bypass/yolo")
NO_STREAM_OPTION = typer.Option(False, "--no-stream", help="Disable streaming")
YES_ALL_OPTION = typer.Option(False, "--yes", "-y", help="Auto-confirm all permission prompts")
DEBUG_EVENTS_OPTION = typer.Option(False, "--debug-events", help="Print raw EventBus events for this session")
RESUME_OPTION = typer.Option(None, "--resume", help="Resume a persisted session id")
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
    console.print("\n接下来请编辑配置文件，填写你的 LLM API Key等信息。")


@app.command()
def run(
    task: str = typer.Argument("", help="Task description to execute"),
    debug_events: bool = DEBUG_EVENTS_OPTION,
    resume: str | None = RESUME_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
) -> None:
    """运行一个命令行任务。"""
    # CLI 命令只负责组装参数；任务生命周期由 TaskRuntime 负责。
    run_params = RunParams()
    run_params.platform = "cli"
    run_params.message = task
    run_params.project = str(Path.cwd())
    run_params.model = ""
    run_params.provider = ""
    run_params.permission = ""
    run_params.no_stream = False
    run_params.yes_all = False
    run_params.debug_events = debug_events
    run_params.session_mode = SessionMode.chat
    run_params.task_id = str(uuid.uuid4())
    run_params.session_id = resume or str(uuid.uuid4())

    if resume:
        created_task = anyio.run(_start_resumed_session, run_params, record_dir=str(record_dir) if record_dir else None)
    else:
        created_task = anyio.run(_start_session, run_params)
    console.print(
        f"[green]task completed[/green] task_id={created_task.task_id} session_id={created_task.session_id}"
    )


@app.command()
def main(
    message: str | None = MSG_OPTION,
    project: Path | None = PROJECT_OPTION,
    model: str | None = MODEL_OPTION,
    provider: str | None = PROVIDER_OPTION,
    permission: str | None = PERMISSION_OPTION,
    no_stream: bool = NO_STREAM_OPTION,
    yes_all: bool = YES_ALL_OPTION,
    debug_events: bool = DEBUG_EVENTS_OPTION,
    session_mode: SessionMode = SESSION_MODE_OPTION,
    resume: str | None = RESUME_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
) -> None:
    """启动 Bamboo 会话；无 --msg 时进入交互式命令行对话。"""
    run_params = RunParams()
    run_params.platform = "cli"
    run_params.message = message or ""
    run_params.project = str(project or Path.cwd())
    run_params.model = model or ""
    run_params.provider = provider or ""
    run_params.permission = permission or "default"
    run_params.no_stream = no_stream
    run_params.yes_all = yes_all
    run_params.debug_events = debug_events
    run_params.session_mode = session_mode
    run_params.task_id = str(uuid.uuid4())
    run_params.session_id = resume or str(uuid.uuid4())

    if run_params.message:
        if resume:
            anyio.run(_start_resumed_session, run_params, record_dir=str(record_dir) if record_dir else None)
        else:
            anyio.run(_start_session, run_params)
        return

    if resume:
        anyio.run(_start_resumed_interactive_session, run_params, record_dir=str(record_dir) if record_dir else None)
        return

    anyio.run(_start_interactive_session, run_params)


@app.command()
def replay(
    session_id: str = typer.Argument(..., help="Persisted session id to replay"),
    mode: SessionMode = SESSION_MODE_OPTION,
    project: Path | None = PROJECT_OPTION,
    record_dir: Path | None = RECORD_DIR_OPTION,
    json_output: bool = typer.Option(False, "--json", help="Print raw replay summary JSON"),
) -> None:
    """离线回放一个已持久化 session 的执行摘要，不调用模型或工具。"""
    resolved = find_session_record(
        session_id,
        mode=mode.value if isinstance(mode, SessionMode) else str(mode),
        project_path=project if mode == SessionMode.project else None,
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


@app.command()
def version() -> None:
    """输出当前 Bamboo 版本。"""
    from bamboo import __version__
    print(f"Bamboo v{__version__}")


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Web server host"),
    port: int = typer.Option(8899, "--port", "-p", help="Web server port"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload"),
) -> None:
    """启动 Bamboo Web 对话入口。"""
    import uvicorn

    console.print(f"[green]Bamboo Web[/green] http://{host}:{port}")
    uvicorn.run("bamboo.adapters.web.app:app", host=host, port=port, reload=reload)


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
    replace: bool = typer.Option(False, "--replace", help="Replace existing job"),
) -> None:
    """注册一个 Cron job。"""
    from bamboo.cron import CronJob

    if session not in {"isolated", "main"}:
        raise typer.BadParameter("session must be isolated/main")
    store = CronStore()
    store.register_job(
        CronJob(
            name=name,
            schedule=schedule,
            prompt=prompt,
            project=str(project) if project else "",
            session=session,  # type: ignore[arg-type]
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
