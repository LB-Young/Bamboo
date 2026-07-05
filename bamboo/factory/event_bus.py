"""Bamboo 运行时异步事件总线。

EventBus 只负责通知和分发，不保存业务状态，也不决定任务流程。
CLI、Web、日志、审计等外部消费者都应通过订阅事件获取运行状态。
"""

from __future__ import annotations

import asyncio
import fnmatch
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from loguru import logger

from bamboo.helpers.constant import BambooEvent
from bamboo.helpers.utils import BaseEvent


EventHandler = Callable[[BaseEvent], Awaitable[None] | None]
EventFilter = Callable[[BaseEvent], bool]


@dataclass(slots=True)
class Subscription:
    """描述一个事件订阅。"""

    handler: EventHandler
    filter_fn: EventFilter | None = None
    event_types: set[str] | None = None
    patterns: set[str] | None = None

    def matches(self, event: BaseEvent) -> bool:
        """判断当前订阅是否应该接收某个事件。"""
        if self.event_types is not None and event.type not in self.event_types:
            return False
        if self.patterns is not None and not any(
            _event_type_matches_pattern(event.type, pattern) for pattern in self.patterns
        ):
            return False
        if self.filter_fn is not None and not self.filter_fn(event):
            return False
        return True


class EventBus:
    """向解耦的订阅者发布运行时事件。"""

    def __init__(self) -> None:
        """初始化进程内事件总线。"""
        self._subscriptions: list[Subscription] = []
        self._lock = asyncio.Lock()
        self._logger = logger.bind(name="EventBus")

    def subscribe(
        self,
        handler: EventHandler,
        *,
        event_types: str | list[str] | set[str] | None = None,
        patterns: str | list[str] | set[str] | None = None,
        pattern: str | None = None,
        filter_fn: EventFilter | None = None,
    ) -> Callable[[], None]:
        """注册事件处理函数，并返回取消订阅函数。"""
        normalized_types = self._normalize_event_types(event_types)
        normalized_patterns = self._normalize_patterns(patterns, pattern)
        subscription = Subscription(
            handler=handler,
            filter_fn=filter_fn,
            event_types=normalized_types,
            patterns=normalized_patterns,
        )
        self._subscriptions.append(subscription)
        self._logger.debug(
            "subscribed event_types={types} patterns={patterns}",
            types=normalized_types,
            patterns=normalized_patterns,
        )
        return lambda: self.unsubscribe(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        """移除指定 handler 的所有订阅。"""
        self._subscriptions = [subscription for subscription in self._subscriptions if subscription.handler != handler]

    async def emit(self, event: BambooEvent) -> None:
        """把一个事件发布给所有匹配的订阅者。"""
        async with self._lock:
            # 复制订阅列表，避免 handler 内部增删订阅影响本轮发布。
            subscriptions = list(self._subscriptions)

        awaitables: list[Awaitable[None]] = []
        for subscription in subscriptions:
            if not subscription.matches(event):
                continue
            try:
                result = subscription.handler(event)
            except Exception as exc:
                self._logger.warning(
                    "event handler failed before await handler={handler} event={event}: {error}",
                    handler=subscription.handler,
                    event=event.type,
                    error=exc,
                )
                continue
            if asyncio.iscoroutine(result):
                awaitables.append(result)

        if awaitables:
            results = await asyncio.gather(*awaitables, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self._logger.warning("event handler failed: {error}", error=result)

    async def stream(
        self,
        session_id: str,
        *,
        patterns: str | list[str] | set[str] | None = None,
        event_types: str | list[str] | set[str] | None = None,
    ) -> AsyncIterator[BambooEvent]:
        """按 session_id 生成异步事件流。"""
        queue: asyncio.Queue[BambooEvent] = asyncio.Queue()

        async def _enqueue(event: BaseEvent) -> None:
            """把匹配事件放入队列。"""
            await queue.put(event)  # type: ignore[arg-type]

        unsubscribe = self.subscribe(
            _enqueue,
            event_types=event_types,
            patterns=patterns,
            filter_fn=lambda event: event.session_id == session_id,
        )
        try:
            while True:
                yield await queue.get()
        finally:
            unsubscribe()

    def count_subscribers(self, event_type: str | None = None) -> int:
        """统计订阅者数量，可按事件类型过滤。"""
        if event_type is None:
            return len(self._subscriptions)
        return sum(
            1
            for subscription in self._subscriptions
            if (
                (subscription.event_types is None or event_type in subscription.event_types)
                and (
                    subscription.patterns is None
                    or any(_event_type_matches_pattern(event_type, pattern) for pattern in subscription.patterns)
                )
            )
        )

    def _normalize_event_types(self, event_types: str | list[str] | set[str] | None) -> set[str] | None:
        """把事件类型参数标准化为集合。"""
        if event_types is None:
            return None
        if isinstance(event_types, str):
            return {event_types}
        return set(event_types)

    def _normalize_patterns(
        self,
        patterns: str | list[str] | set[str] | None,
        pattern: str | None,
    ) -> set[str] | None:
        """把 pattern 参数标准化为集合。"""
        normalized: set[str] = set()
        if patterns is not None:
            if isinstance(patterns, str):
                normalized.add(patterns)
            else:
                normalized.update(patterns)
        if pattern:
            normalized.add(pattern)
        return normalized or None


def _event_type_matches_pattern(event_type: str, pattern: str) -> bool:
    """支持 `tool.*` 同时匹配 `tool.call` 和当前兼容事件名 `tool-call`。"""
    if pattern == "*":
        return True
    normalized_event_type = event_type.replace("-", ".")
    normalized_pattern = pattern.replace("-", ".")
    return fnmatch.fnmatchcase(normalized_event_type, normalized_pattern)


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取进程级 EventBus 单例。"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
