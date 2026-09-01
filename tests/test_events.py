"""Pins the SSE fan-out contract: lossy delivery, live subscriber counts, and frame shape."""

from __future__ import annotations

import asyncio
import json

from guide.daemon.events import _QUEUE_LIMIT, EventBus, _frame


async def test_a_subscriber_receives_a_published_event() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue:
        bus.publish("batch.added", id="abc123")
        event = await asyncio.wait_for(queue.get(), timeout=1)
    assert event == {"kind": "batch.added", "id": "abc123"}


async def test_publish_with_no_subscribers_is_a_silent_no_op() -> None:
    bus = EventBus()
    bus.publish("batch.added", id="nobody-listening")  # must not raise


async def test_the_queue_is_lossy_rather_than_blocking_when_it_overflows() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue:
        for index in range(_QUEUE_LIMIT + 6):
            bus.publish("batch.answered", id=str(index))  # never raises QueueFull

        assert queue.qsize() == _QUEUE_LIMIT

        drained = []
        while not queue.empty():
            drained.append(await queue.get())

    # The oldest events fell off; only the most recent _QUEUE_LIMIT survive.
    assert [event["id"] for event in drained] == [str(i) for i in range(6, _QUEUE_LIMIT + 6)]


async def test_subscriber_count_tracks_subscribe_and_unsubscribe() -> None:
    bus = EventBus()
    assert bus.subscriber_count == 0

    async with bus.subscribe():
        assert bus.subscriber_count == 1
        async with bus.subscribe():
            assert bus.subscriber_count == 2
        assert bus.subscriber_count == 1

    assert bus.subscriber_count == 0


def test_frame_renders_well_formed_sse_text() -> None:
    text = _frame({"kind": "batch.completed", "id": "xyz"})

    assert text.startswith("event: batch.completed\n")
    assert text.endswith("\n\n")

    _, data_line, *_rest = text.splitlines()
    assert data_line.startswith("data: ")
    assert json.loads(data_line.removeprefix("data: ")) == {
        "kind": "batch.completed",
        "id": "xyz",
    }
