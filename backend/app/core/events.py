"""In-process event bus feeding the WebSocket timeline.

Single-process by design (see plan.md §3): the scale-out path swaps this for Redis
pub/sub behind the same publish/subscribe interface.
"""

import asyncio
from collections import defaultdict

from app.core.models import AgentEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[AgentEvent]]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue[AgentEvent]:
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=1000)
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[AgentEvent]) -> None:
        self._subscribers[run_id].discard(queue)
        if not self._subscribers[run_id]:
            self._subscribers.pop(run_id, None)

    def publish(self, event: AgentEvent) -> None:
        for queue in list(self._subscribers.get(event.run_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow consumer; it can catch up through event replay


event_bus = EventBus()
