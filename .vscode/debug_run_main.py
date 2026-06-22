"""VS Code debug entrypoint for calling bamboo.run.main directly."""

from pathlib import Path

from bamboo.helpers.constant import SessionMode
from bamboo.run import main


def run_debug_main() -> None:
    """Call bamboo.run.main with stable debug arguments."""
    main(
        message="debug from VS Code main()",
        project=Path.cwd(),
        model=None,
        provider=None,
        permission=None,
        no_stream=False,
        yes_all=False,
        session_mode=SessionMode.chat,
    )


if __name__ == "__main__":
    run_debug_main()
