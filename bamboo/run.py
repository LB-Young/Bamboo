"""Bamboo 命令行入口。

这个脚本负责注册 Typer 命令，并把用户输入转换为 RunParams 后交给
CLI adapter 和 TaskRuntime。真实执行逻辑不放在这里，避免入口层变重。
"""
import uuid
from pathlib import Path

import anyio
import typer
from rich.console import Console

from bamboo.adapters.cli.main import _start_interactive_session, _start_session
from bamboo.helpers.constant import SessionMode
from bamboo.helpers.logging import setup_logging
from bamboo.helpers.requests_params import RunParams
from bamboo.userspace.userspace import ensure_userspace

setup_logging()

console = Console()
MSG_OPTION = typer.Option(None, "--msg", "-m", help="Initial message")
PROJECT_OPTION = typer.Option(None, "--project", "-p", help="Project path")
MODEL_OPTION = typer.Option(None, "--model", help="Override model")
PROVIDER_OPTION = typer.Option(None, "--provider", help="LLM provider: deepseek/minimax/gpt/claude")
PERMISSION_OPTION = typer.Option(None, "--permission", help="Permission mode: default/auto/bypass/yolo")
NO_STREAM_OPTION = typer.Option(False, "--no-stream", help="Disable streaming")
YES_ALL_OPTION = typer.Option(False, "--yes", "-y", help="Auto-confirm all permission prompts")
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


@app.command()
def init() -> None:
    """初始化 Bamboo 用户目录。"""
    layout = ensure_userspace()
    console.print(f"[green]✓ 用户目录已就绪：{layout.root}[/green]")
    console.print("\n接下来请编辑配置文件，填写你的 LLM API Key等信息。")


@app.command()
def run(
    task: str = typer.Argument("", help="Task description to execute"),
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
    run_params.session_mode = SessionMode.chat
    run_params.task_id = str(uuid.uuid4())
    run_params.session_id = str(uuid.uuid4())

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
    session_mode: SessionMode = SESSION_MODE_OPTION,
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
    run_params.session_mode = session_mode
    run_params.task_id = str(uuid.uuid4())
    run_params.session_id = str(uuid.uuid4())

    if run_params.message:
        anyio.run(_start_session, run_params)
        return

    anyio.run(_start_interactive_session, run_params)


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
    from bamboo.skills import create_skill_registry

    registry = create_skill_registry()
    for definition in registry.list(include_inactive=include_inactive):
        state = registry.store.load_state(definition.name)
        status = state.status if state is not None else "unknown"
        health = state.health if state is not None else "unknown"
        console.print(f"{definition.name}\t{status}\t{health}\t{definition.description}")


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
    run_params.session_mode = session_mode
    run_params.task_id = str(uuid.uuid4())
    run_params.session_id = str(uuid.uuid4())

    anyio.run(_start_session, run_params)



if __name__ == "__main__":
    app()
