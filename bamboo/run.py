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
