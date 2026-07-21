"""Tests for layered context compaction."""

from __future__ import annotations

from pathlib import Path

import anyio

from bamboo.factory.context import Context
from bamboo.factory.session import Session
from bamboo.llms import LLMClient, LLMImage, LLMRequest, LLMResponse
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
    session.add_message("assistant", "current answer")
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
