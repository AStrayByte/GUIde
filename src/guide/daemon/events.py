"""Server-sent events: how the page finds out a new batch arrived.

Chosen over polling because the browser side is already written for us —
``EventSource`` reconnects on its own, so the "daemon restarted" case costs zero
lines. See ``docs/decisions/0005-sse-over-polling.md``.

The bus is deliberately lossy. A subscriber that stops reading gets its oldest
events dropped rather than applying backpressure to the daemon, because every
event is a *hint to refresh*, never a delta the client must replay in order. A
page that misses one and then sees the next still ends up correct.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

_QUEUE_LIMIT = 64
"""Events held for one slow subscriber before the oldest start falling off."""

_HEARTBEAT_SECONDS = 20
"""Comment frames keep proxies and sleeping laptops from silently dropping the stream."""


class EventBus:
    """Fan-out of daemon events to every connected page."""

    def __init__(self) -> None:
        """Start with no subscribers; pages attach as they connect."""
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    @property
    def subscriber_count(self) -> int:
        """How many pages are currently listening."""
        return len(self._subscribers)

    def publish(self, kind: str, **payload: Any) -> None:
        """Broadcast one event to every subscriber.

        Safe to call from anywhere in the daemon: it never awaits and never
        raises, so no route has to care whether a browser is attached.
        """
        event = {"kind": kind, **payload}
        for queue in self._subscribers:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        """Register a queue for the lifetime of one connection."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_LIMIT)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def stream(self) -> AsyncIterator[str]:
        """Yield ``text/event-stream`` frames until the client disconnects."""
        async with self.subscribe() as queue:
            yield _comment("connected")
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), _HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield _comment("keep-alive")
                    continue
                yield _frame(event)


def _frame(event: dict[str, Any]) -> str:
    """One SSE message: a named event carrying a JSON payload."""
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event['kind']}\ndata: {data}\n\n"


def _comment(text: str) -> str:
    """An SSE comment. Ignored by ``EventSource``, but it keeps the socket warm."""
    return f": {text}\n\n"
