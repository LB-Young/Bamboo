"""验证任务快照工具。"""

import anyio

from bamboo.runtime.store import get_task_store, reset_task_store
from bamboo.tools.buildin.task import TaskCreateTool, TaskGetTool, TaskListTool, TaskStopTool


def test_task_tools_create_get_list_and_stop() -> None:
    """验证任务工具共享同一个进程内 TaskStore。"""
    reset_task_store()
    create_tool = TaskCreateTool()
    get_tool = TaskGetTool()
    list_tool = TaskListTool()
    stop_tool = TaskStopTool()

    async def run_test() -> None:
        created = await create_tool.execute(
            title="Investigate issue",
            description="Find the root cause",
            session_id="session-1",
            tags=["debug"],
            depends_on=["parent-task"],
        )
        assert created.success is True
        assert created.metadata is not None
        task_id = created.metadata["task"]["task_id"]

        fetched = await get_tool.execute(task_id)
        assert fetched.success is True
        assert "Investigate issue" in fetched.content
        assert fetched.metadata["task"]["metadata"]["tags"] == ["debug"]  # type: ignore[index]

        listed = await list_tool.execute(session_id="session-1")
        assert listed.success is True
        assert task_id in listed.content
        assert len(listed.metadata["tasks"]) == 1  # type: ignore[index]

        stopped = await stop_tool.execute(task_id, reason="No longer needed")
        assert stopped.success is True
        assert stopped.metadata["task"]["status"] == "cancelled"  # type: ignore[index]
        assert get_task_store().get(task_id).status == "cancelled"  # type: ignore[union-attr]

    anyio.run(run_test)


def test_task_tools_report_missing_task() -> None:
    """验证不存在的 task_id 返回失败。"""
    reset_task_store()
    get_tool = TaskGetTool()
    stop_tool = TaskStopTool()

    async def run_test() -> None:
        missing = await get_tool.execute("missing")
        assert missing.success is False
        assert missing.error == "task_not_found"

        stopped = await stop_tool.execute("missing")
        assert stopped.success is False
        assert stopped.error == "task_not_found"

    anyio.run(run_test)


def test_task_list_filters_status() -> None:
    """验证 task_list 支持 status 过滤。"""
    reset_task_store()
    store = get_task_store()
    first = store.create_task(task_id="one", session_id="s", title="One")
    second = store.create_task(task_id="two", session_id="s", title="Two")
    store.stop(second.task_id, "done")
    list_tool = TaskListTool()

    async def run_test() -> None:
        created = await list_tool.execute(status="created")
        assert created.metadata is not None
        assert [task["task_id"] for task in created.metadata["tasks"]] == [first.task_id]

        cancelled = await list_tool.execute(status="cancelled")
        assert cancelled.metadata is not None
        assert [task["task_id"] for task in cancelled.metadata["tasks"]] == [second.task_id]

    anyio.run(run_test)
