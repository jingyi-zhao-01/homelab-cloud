from __future__ import annotations

"""Minimal async event bus for in-process event-driven orchestration."""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any


EventHandler = Callable[[Any], Awaitable[None]]


class AsyncEventBus:
    """Publish typed events to subscribed async handlers within one process."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """Register one async handler for a concrete event type."""

        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        """Deliver one event to all handlers registered for its concrete type."""

        for handler in self._handlers.get(type(event), []):
            await handler(event)
