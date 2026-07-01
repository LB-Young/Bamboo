"""验证 TodoWriteTool。"""

import anyio

from bamboo.tools.buildin.todo import TodoWriteTool


def test_todo_write_tool_updates_todos() -> None:
    """验证 todo_write 返回结构化 metadata 和摘要。"""
    tool = TodoWriteTool()

    async def run_test() -> None:
        result = await tool.execute(
            [
                {"id": "1", "content": "Read code", "status": "completed"},
                {"id": "2", "content": "Implement tool", "status": "in_progress"},
                {"id": "3", "content": "Run tests", "status": "pending"},
            ]
        )
        assert result.success is True
        assert "Updated 3 todos" in result.content
        assert result.metadata is not None
        assert result.metadata["counts"] == {"pending": 1, "in_progress": 1, "completed": 1}
        assert result.metadata["todos"][1]["status"] == "in_progress"

    anyio.run(run_test)


def test_todo_write_tool_rejects_multiple_in_progress() -> None:
    """验证同一时间只允许一个 in_progress。"""
    tool = TodoWriteTool()

    async def run_test() -> None:
        result = await tool.execute(
            [
                {"id": "1", "content": "One", "status": "in_progress"},
                {"id": "2", "content": "Two", "status": "in_progress"},
            ]
        )
        assert result.success is False
        assert result.error == "multiple_in_progress"

    anyio.run(run_test)


def test_todo_write_tool_rejects_duplicate_ids() -> None:
    """验证重复 todo id 会失败。"""
    tool = TodoWriteTool()

    async def run_test() -> None:
        result = await tool.execute(
            [
                {"id": "1", "content": "One", "status": "pending"},
                {"id": "1", "content": "Again", "status": "completed"},
            ]
        )
        assert result.success is False
        assert result.error == "duplicate_id"

    anyio.run(run_test)
