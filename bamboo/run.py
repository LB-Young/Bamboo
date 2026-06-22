"""Bamboo 命令行入口。

这个脚本负责注册 Typer 命令，并把用户输入转换为 RunParams 后交给
CLI adapter 和 TaskRuntime。真实执行逻辑不放在这里，避免入口层变重。
"""
import uuid
import typer
import anyio
from pathlib import Path
from rich.console import Console

from bamboo.helpers.constant import SessionMode
from bamboo.adapters.cli.main import _start_session
from bamboo.userspace.userspace import ensure_userspace
from bamboo.helpers.requests_params import RunParams
from bamboo.helpers.logging import get_logger, setup_logging

setup_logging()

console = Console()


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
    console.print(f"\n接下来请编辑配置文件，填写你的 LLM API Key等信息。")


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
def version() -> None:
    """输出当前 Bamboo 版本。"""
    from bamboo import __version__
    print(f"Bamboo v{__version__}")


def main(
    message: str | None = typer.Option(None, "--msg", "-m", help="Initial message"),
    project: Path | None = typer.Option(None, "--project", "-p", help="Project path"),
    model: str | None = typer.Option(None, "--model", help="Override model"),
    provider: str | None = typer.Option(None, "--provider", help="LLM provider: anthropic/minimax"),
    permission: str | None = typer.Option(None, "--permission", help="Permission mode: default/auto/bypass/yolo"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming"),
    yes_all: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm all permission prompts"),
    session_mode: SessionMode = typer.Option(
        SessionMode.auto,
        "--session-mode",
        help="Session mode: auto / project / chat",
    ),
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

    anyio.run(
        _start_session,
        run_params,
    )



if __name__ == "__main__":
    app()
