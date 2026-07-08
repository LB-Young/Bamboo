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
        permission="default",
        no_stream=False,
        yes_all=False,
        debug_events=False,
        session_mode=SessionMode.chat,
        resume=None,
        record_dir=None,
    )


if __name__ == "__main__":
    run_debug_main()
