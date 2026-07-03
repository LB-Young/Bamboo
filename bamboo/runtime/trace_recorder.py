"""Persist EventBus events for a single task/session trace."""

from __future__ import annotations

from collections.abc import Callable

from bamboo.factory.event_bus import EventBus
from bamboo.helpers.utils import BaseEvent
from bamboo.memory.session_store import SessionMemoryStore


class TraceRecorder:
    """Subscribe to EventBus and append matching events to session storage."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        store: SessionMemoryStore,
        session_id: str,
        task_id: str = "",
    ) -> None:
        self.event_bus = event_bus
        self.store = store
        self.session_id = session_id
        self.task_id = task_id
        self._unsubscribe: Callable[[], None] | None = None

    def start(self) -> None:
        """Start recording events for the configured session/task."""
        if self._unsubscribe is not None:
            return
        self._unsubscribe = self.event_bus.subscribe(
            self.record,
            filter_fn=self._matches_event,
        )

    def close(self) -> None:
        """Stop recording future events."""
        if self._unsubscribe is None:
            return
        self._unsubscribe()
        self._unsubscribe = None

    def record(self, event: BaseEvent) -> None:
        """Persist one event."""
        self.store.append_event(event)

    def _matches_event(self, event: BaseEvent) -> bool:
        if event.session_id != self.session_id:
            return False
        if self.task_id and event.task_id and event.task_id != self.task_id:
            return False
        return True
