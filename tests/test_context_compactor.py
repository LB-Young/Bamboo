"""Tests for layered context compaction."""

from __future__ import annotations

from pathlib import Path

import anyio

from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.llms import LLMClient, LLMImage, LLMRequest, LLMResponse, LLMToolCall
from bamboo.llms.config import ModelConfig
from bamboo.runtime.context_compactor import ContextBudgetPolicy, ContextCompactor


class _CharacterTokenCounter:
    def count_request(self, request: LLMRequest) -> int:
        return len(request.system_prompt) + sum(len(message.content) for message in request.messages)

    def count_text(self, text: str) -> int:
        return len(text)


class _RecordingLLMClient(LLMClient):
    def __init__(self, content: str = "structured summary") -> None:
        self.content = content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.content, model="summary-model", provider="test")


def test_microcompact_strips_old_images_before_summary_call() -> None:
    session = _session()
    old = session.add_message(
        "user",
        "please inspect these images",
        images=[
            LLMImage(source="/tmp/a.png", media_type="image/png"),
            LLMImage(source="/tmp/b.jpg", media_type="image/jpeg"),
        ],
    )
    session.add_message("assistant", "old image answer")
    session.add_message("user", "current question")
    llm = _RecordingLLMClient()
    compactor = _compactor(llm)

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is True

    anyio.run(run_test)

    assert llm.requests == []
    assert old.images == []
    assert old.active_for_prompt is True
    assert "[images compacted from older context]" in old.content
    assert old.metadata["context_microcompact_images"] == 2
    assert old.metadata["context_microcompact_image_sources"] == ["/tmp/a.png", "/tmp/b.jpg"]


def test_microcompact_truncates_large_old_messages_before_summary_call() -> None:
    session = _session()
    old = session.add_message("assistant", "HEAD" + ("A" * 500) + "TAIL")
    session.add_message("user", "current question")
    llm = _RecordingLLMClient()
    compactor = _compactor(
        llm,
        policy=ContextBudgetPolicy(
            preserve_recent_messages=1,
            max_inline_message_tokens=180,
            preserve_message_head_chars=40,
            preserve_message_tail_chars=30,
        ),
    )

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is True

    anyio.run(run_test)

    assert llm.requests == []
    assert old.content.startswith("HEAD")
    assert old.content.endswith("TAIL")
    assert "message microcompacted" in old.content
    assert old.metadata["context_microcompacted"] is True
    assert old.metadata["context_microcompact_original_length"] == 508


def test_summary_prompt_requests_structured_session_memory_after_microcompact() -> None:
    session = _session()
    session.add_message("user", "old requirement")
    session.add_message("assistant", "old decision")
    session.add_message("user", "current question")
    llm = _RecordingLLMClient(content="## Goal\nContinue safely")
    compactor = _compactor(llm)

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is True

    anyio.run(run_test)

    assert len(llm.requests) == 1
    assert llm.requests[0].system_prompt.startswith("Compress the conversation history")
    assert "structured Bamboo session memory" in llm.requests[0].system_prompt
    assert "Goal" in llm.requests[0].system_prompt
    assert any(message.message_type == "compaction" for message in session.messages)


def test_compaction_keeps_assistant_tool_call_with_tool_result() -> None:
    session = _session()
    session.add_message("user", "old requirement")
    assistant = session.add_message(
        "assistant",
        "",
        tool_calls=[LLMToolCall(id="call-1", name="grep", arguments={"pattern": "x"})],
    )
    tool = session.add_message("tool", "grep result", tool_call_id="call-1", tool_name="grep")
    session.add_message("user", "current question")
    llm = _RecordingLLMClient(content="tool work summary")
    compactor = _compactor(llm)

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is True

    anyio.run(run_test)

    assert len(llm.requests) == 1
    assert "tool_calls=" in llm.requests[0].messages[0].content
    assert "tool_call_id=call-1" in llm.requests[0].messages[0].content
    assert assistant.compressed is True
    assert tool.compressed is True
    assert any(message.message_type == "compaction" for message in session.messages)


def test_compaction_boundary_does_not_split_dangling_tool_call_turn() -> None:
    session = _session()
    old_user = session.add_message("user", "old requirement")
    assistant = session.add_message(
        "assistant",
        "",
        tool_calls=[LLMToolCall(id="call-1", name="grep", arguments={"pattern": "x"})],
    )
    tool = session.add_message("tool", "grep result", tool_call_id="call-1", tool_name="grep")
    session.add_message("user", "current question")
    llm = _RecordingLLMClient(content="old user summary")
    compactor = _compactor(llm, policy=ContextBudgetPolicy(preserve_recent_messages=2))

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is False

    anyio.run(run_test)

    assert llm.requests == []
    assert old_user.active_for_prompt is True
    assert old_user.compressed is False
    assert assistant.active_for_prompt is True
    assert assistant.compressed is False
    assert tool.active_for_prompt is True
    assert tool.compressed is False


def test_compaction_boundary_backs_off_to_previous_complete_turn() -> None:
    session = _session()
    old_user = session.add_message("user", "old question")
    old_assistant = session.add_message("assistant", "old answer")
    followup_user = session.add_message("user", "follow-up question")
    current_assistant = session.add_message("assistant", "current answer")
    llm = _RecordingLLMClient(content="old turn summary")
    compactor = _compactor(llm, policy=ContextBudgetPolicy(preserve_recent_messages=1))

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is True

    anyio.run(run_test)

    assert len(llm.requests) == 1
    source = llm.requests[0].messages[0].content
    assert "old question" in source
    assert "old answer" in source
    assert "follow-up question" not in source
    assert old_user.compressed is True
    assert old_assistant.compressed is True
    assert followup_user.active_for_prompt is True
    assert current_assistant.active_for_prompt is True


def test_compaction_keeps_tool_turn_final_answer_with_results() -> None:
    session = _session()
    assistant = session.add_message(
        "assistant",
        "",
        tool_calls=[LLMToolCall(id="call-1", name="grep", arguments={"pattern": "x"})],
    )
    tool = session.add_message("tool", "grep result", tool_call_id="call-1", tool_name="grep")
    final_answer = session.add_message("assistant", "the result is x")
    session.add_message("user", "current question")
    llm = _RecordingLLMClient(content="tool turn summary")
    compactor = _compactor(llm, policy=ContextBudgetPolicy(preserve_recent_messages=1))

    async def run_test() -> None:
        compacted = await compactor.compact(session)
        assert compacted is True

    anyio.run(run_test)

    assert len(llm.requests) == 1
    source = llm.requests[0].messages[0].content
    assert "tool_calls=" in source
    assert "tool_call_id=call-1" in source
    assert "the result is x" in source
    assert assistant.compressed is True
    assert tool.compressed is True
    assert final_answer.compressed is True


def _session() -> Session:
    return Session(
        session_id="session-context",
        model="model",
        provider="provider",
        context=Context(
            session_id="session-context",
            project_root=Path.cwd(),
            memory_dir=Path.cwd(),
            system_prompt="system",
        ),
    )


def _compactor(
    llm: LLMClient,
    *,
    policy: ContextBudgetPolicy | None = None,
) -> ContextCompactor:
    return ContextCompactor(
        llm_client=llm,
        model_config=ModelConfig(
            name="model",
            provider="provider",
            model="provider-model",
            prompt_profile="provider",
            api_key="test-key",
            context_window=1000,
            max_tokens=100,
        ),
        token_counter=_CharacterTokenCounter(),
        policy=policy or ContextBudgetPolicy(preserve_recent_messages=1),
    )
