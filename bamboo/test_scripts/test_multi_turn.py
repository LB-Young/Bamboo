"""真实多轮对话测试：使用用户配置的 Agent 模型连续执行两轮对话。

运行方式：
    python bamboo/test_scripts/test_multi_turn.py

该脚本读取 `~/.bamboo/configs`，会真实调用模型平台并产生 API 费用。
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import anyio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bamboo.factory.event_bus import EventBus  # noqa: E402
from bamboo.factory.task_factory import Task, TaskFactory  # noqa: E402
from bamboo.helpers.config import BambooConfig  # noqa: E402
from bamboo.helpers.constant import TextFinishEvent  # noqa: E402
from bamboo.helpers.requests_params import RunParams  # noqa: E402
from bamboo.helpers.utils import BaseEvent  # noqa: E402
from bamboo.llms import LLMFactory  # noqa: E402
from bamboo.runtime.agent_runtime import AgentRuntime  # noqa: E402


def resolve_agent_models(config: BambooConfig, llm_factory: LLMFactory) -> tuple[str, str]:
    """从主 Agent 配置读取执行模型和可选压缩模型。"""
    agent_config = config.get("bamboo_main_agent", {})
    model_name = agent_config.get("model") if isinstance(agent_config, dict) else None
    if not isinstance(model_name, str) or not model_name:
        model_name = llm_factory.default_model_name

    compaction_model = agent_config.get("compaction_model") if isinstance(agent_config, dict) else None
    if not isinstance(compaction_model, str) or not compaction_model:
        compaction_model = model_name
    return model_name, compaction_model


async def run_agent_turn(
    *,
    task: Task,
    event_bus: EventBus,
    llm_factory: LLMFactory,
    model_name: str,
    compaction_model_name: str,
) -> str:
    """为当前 Session 创建一轮 AgentRuntime，并返回真实模型输出。"""
    runtime = AgentRuntime(
        event_bus=event_bus,
        llm_factory=llm_factory,
        model_name=model_name,
        compaction_model_name=compaction_model_name,
    )
    completed_task = await runtime.run(task)
    return completed_task.output


async def run_conversation() -> None:
    """真实执行两轮对话，并验证第二轮能够读取第一轮上下文。"""
    config = BambooConfig()
    llm_factory = LLMFactory.from_bamboo_config(config)
    model_name, compaction_model_name = resolve_agent_models(config, llm_factory)
    event_bus = EventBus()

    def render_answer(event: BaseEvent) -> None:
        """把每轮真实模型回答输出到终端。"""
        if isinstance(event, TextFinishEvent):
            print(f"assistant: {event.content}")

    event_bus.subscribe(render_answer, event_types="text-finish")

    verification_code = f"BAMBOO-{uuid.uuid4().hex[:8].upper()}"
    first_question = f"请记住校验码 {verification_code}。只回复：我已记住。"
    run_params = RunParams(
        message=first_question,
        model=model_name,
        project=str(PROJECT_ROOT),
    )
    task = TaskFactory(config=config).create(run_params)

    print(f"agent model: {model_name}")
    print(f"compaction model: {compaction_model_name}")
    print(f"user turn 1: {first_question}")
    first_answer = await run_agent_turn(
        task=task,
        event_bus=event_bus,
        llm_factory=llm_factory,
        model_name=model_name,
        compaction_model_name=compaction_model_name,
    )
    if not first_answer.strip():
        raise AssertionError("第一轮真实模型回答为空")

    second_question = "我上一轮让你记住的校验码是什么？只回复校验码。"
    task.session.add_message("user", second_question)
    task.user_query = second_question
    task.output = ""

    print(f"user turn 2: {second_question}")
    second_answer = await run_agent_turn(
        task=task,
        event_bus=event_bus,
        llm_factory=llm_factory,
        model_name=model_name,
        compaction_model_name=compaction_model_name,
    )

    if verification_code not in second_answer:
        raise AssertionError(
            f"第二轮回答没有包含第一轮校验码：expected={verification_code}, actual={second_answer!r}"
        )
    if len(task.session.active_messages()) != 4:
        raise AssertionError("两轮对话结束后 Session 应包含两条 user 和两条 assistant 消息")

    print("real multi-turn agent test passed")
    print(f"session messages: {len(task.session.active_messages())}")


def run_multi_turn_test() -> None:
    """从同步脚本入口启动真实异步多轮 Agent 测试。"""
    anyio.run(run_conversation)


if __name__ == "__main__":
    run_multi_turn_test()
