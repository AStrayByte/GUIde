"""The daemon's coordination layer: a store, an event bus, and one lock per batch.

Routes stay thin because everything that has to happen *around* a store call —
serialise concurrent writers, gate the version, tell every open page — happens
here. It also means the whole daemon can be exercised in tests without an HTTP
client.

Why a lock at all when the daemon is single-writer: a browser tab and a second
tab (or a stray ``PUT`` from a script) can land in the same event-loop tick, and
each answer write is a read-modify-write of the whole answers file. The lock is
per batch, so two sessions answering two different batches never wait on each
other.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from guide import FORMAT_VERSION
from guide.batch import validate_envelope
from guide.errors import BatchNotFound, IncompatibleVersion
from guide.store import Store
from guide.versioning import Gate, check

from .events import EventBus


class Daemon:
    """Everything the HTTP layer needs, with none of the HTTP."""

    def __init__(self, store: Store | None = None) -> None:
        """Wrap a store with an event bus and the per-batch write locks."""
        self.store = store or Store()
        self.events = EventBus()
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # -- Push -------------------------------------------------------------

    def push(self, document: Any) -> dict[str, Any]:
        """Store a pushed batch and announce it. Returns the stored document.

        The viewer gates versions too — it has to, since a batch can be opened
        over ``file://`` with no daemon involved. Gating here as well turns a
        batch this build could never render into a clear failure at ``guide
        push`` time, instead of a wall of refusal in the browser ten minutes
        later.

        Raises:
            InvalidBatch: the envelope is malformed.
            IncompatibleVersion: this build refuses to render it.
        """
        # Envelope first: "you forgot guide_version" is a better message than
        # "version 0.0.0 is incompatible", and the gate needs a version to read.
        validate_envelope(document)
        verdict = check(document["guide_version"], FORMAT_VERSION)
        if verdict.gate is Gate.HARD:
            raise IncompatibleVersion(verdict.message)

        batch = self.store.create(document)
        self.events.publish("batch.added", id=batch["id"])
        return batch

    # -- Answers ----------------------------------------------------------

    async def record(
        self,
        batch_id: str,
        card_id: str,
        values: dict[str, Any],
        *,
        degraded: bool = False,
        viewer_version: str | None = None,
    ) -> dict[str, Any]:
        """Record one card's answer, serialised against other writers."""
        async with self._lock_for(batch_id):
            answers = self.store.record(
                batch_id,
                card_id,
                values,
                degraded=degraded,
                viewer_version=viewer_version,
            )
        self.events.publish(
            "batch.answered", id=batch_id, card_id=card_id, stats=answers["stats"]
        )
        return answers

    async def set_complete(
        self,
        batch_id: str,
        *,
        complete: bool,
        degraded_cards: list[str] | None = None,
    ) -> dict[str, Any]:
        """Flip the flag ``guide wait`` blocks on, serialised against writers."""
        async with self._lock_for(batch_id):
            answers = self.store.set_complete(
                batch_id, complete=complete, degraded_cards=degraded_cards
            )
        self.events.publish("batch.completed", id=batch_id, complete=complete)
        return answers

    # -- Removal ----------------------------------------------------------

    async def remove(self, batch_id: str, *, archive: bool = False) -> None:
        """Delete or archive a batch, then drop its lock."""
        async with self._lock_for(batch_id):
            if archive:
                self.store.archive(batch_id)
            else:
                self.store.delete(batch_id)
        self._locks.pop(batch_id, None)
        self.events.publish("batch.removed", id=batch_id)

    # -- Internals --------------------------------------------------------

    def _lock_for(self, batch_id: str) -> asyncio.Lock:
        """The write lock for one batch, refusing to invent one for a stranger.

        Without the existence check, a stray request for a batch that is not here
        would leave a lock object behind for an id that will never come back.
        """
        if batch_id not in self._locks and batch_id not in self.store.ids():
            raise BatchNotFound(f"no batch {batch_id!r} in the store")
        return self._locks[batch_id]
