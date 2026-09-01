"""The on-disk store: ``~/.guide/batches/<ulid>/{batch.json,answers.json}``.

Two invariants hold this together.

**The daemon is the only writer.** Browsers and CLI sessions send changes; this
module applies them. Concurrent agent sessions therefore cannot interleave
writes to one answers file, which deletes a whole class of bug rather than
managing it.

**Every write is atomic.** Content goes to a temporary file in the same
directory, is flushed to the platter, and is then moved into place with
``os.replace``. A crash mid-write leaves the previous answers file intact; it
can never leave half of one. Answers are written continuously and there is no
Save button, so "the file on disk is always valid" is load-bearing.

``answers.json`` is derived state with no shadow copy: every update reads the
file, applies one change, recomputes the counters, and writes the whole thing
back. At human answering speed on a local disk that is free, and it means there
is exactly one source of truth to reason about.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from guide import FORMAT_VERSION
from guide.batch import fields_of, is_answered, validate_envelope
from guide.errors import AmbiguousBatchId, BatchNotFound, InvalidBatch
from guide.paths import home as default_home
from guide.ulid import is_ulid, new_ulid

BATCH_FILENAME = "batch.json"
ANSWERS_FILENAME = "answers.json"

_CANONICAL_BATCH_KEYS = (
    "guide_version",
    "id",
    "title",
    "subtitle",
    "instructions",
    "created_at",
    "source",
    "defaults",
    "summary",
    "cards",
)

_CANONICAL_ANSWERS_KEYS = (
    "guide_version",
    "batch_version",
    "viewer_version",
    "degraded",
    "degraded_cards",
    "batch_id",
    "session_id",
    "started_at",
    "updated_at",
    "complete",
    "stats",
    "answers",
)


def utc_now_iso() -> str:
    """The current time as a ``Z``-suffixed ISO 8601 string.

    The store stamps every timestamp in the system, so there is one clock and
    one format rather than a browser's idea of now competing with a daemon's.
    """
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class Summary:
    """One line of the inbox — everything the rail draws, and nothing more."""

    id: str
    title: str
    subtitle: str | None
    label: str | None
    repo: str | None
    branch: str | None
    cwd: str | None
    session_id: str | None
    guide_version: str
    created_at: str | None
    updated_at: str | None
    cards: int
    answered: int
    complete: bool

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready form, for the HTTP surface and ``guide list --json``.

        Derived from the fields rather than restated, so adding one to the
        dataclass cannot leave the wire format quietly behind.
        """
        return asdict(self)


class Store:
    """Batches and their answers, on disk.

    Args:
        home: The store root. Defaults to ``$GUIDE_HOME`` or ``~/.guide``.
            Passing it explicitly is how the tests get a store per temp
            directory without touching a real inbox.
    """

    def __init__(self, home: Path | None = None) -> None:
        """Root the store at ``home``, creating nothing until something is written."""
        self.home = home or default_home()
        self.root = self.home / "batches"
        self.archive_root = self.home / "archive"

    # -- Creating ---------------------------------------------------------

    def create(self, document: Any) -> dict[str, Any]:
        """Validate, stamp and store a pushed batch. Returns the stored form.

        The id is always minted here, and any id the agent supplied is
        discarded. Uniqueness within one store is the daemon's guarantee to
        make, not the pushing session's — and an agent asked to invent a
        collision-free sortable id would get it wrong.
        """
        validate_envelope(document)
        stored = _canonical_order(
            {
                **document,
                "id": new_ulid(),
                "created_at": document.get("created_at") or utc_now_iso(),
            }
        )
        directory = self.root / stored["id"]
        directory.mkdir(parents=True, exist_ok=True)
        _write_json(directory / BATCH_FILENAME, stored)
        _write_json(directory / ANSWERS_FILENAME, _blank_answers(stored))
        return stored

    # -- Reading ----------------------------------------------------------

    def read_batch(self, batch_id: str) -> dict[str, Any]:
        """The stored batch document."""
        return _read_json(self._file(batch_id, BATCH_FILENAME), batch_id)

    def read_answers(self, batch_id: str) -> dict[str, Any]:
        """The current answers document, always a complete and valid file."""
        return _read_json(self._file(batch_id, ANSWERS_FILENAME), batch_id)

    def ids(self) -> list[str]:
        """Every batch id in the store, oldest first — ULIDs sort by time."""
        if not self.root.is_dir():
            return []
        return sorted(
            entry.name for entry in self.root.iterdir() if (entry / BATCH_FILENAME).is_file()
        )

    def summaries(self) -> list[Summary]:
        """One :class:`Summary` per batch, oldest first.

        Unreadable directories are skipped rather than raised: one corrupt batch
        must not take the whole inbox down with it.
        """
        found = []
        for batch_id in self.ids():
            try:
                found.append(self._summarize(batch_id))
            except (BatchNotFound, json.JSONDecodeError, KeyError, TypeError):
                continue
        return found

    def resolve(self, id_or_prefix: str) -> str:
        """Expand an id prefix to a full batch id.

        ULIDs are 26 characters, so nobody types a whole one. The first eight
        are what ``guide push`` prints, and are what this is meant to take.

        Raises:
            BatchNotFound: nothing matches.
            AmbiguousBatchId: more than one batch matches.
        """
        wanted = id_or_prefix.strip().upper()
        matches = [batch_id for batch_id in self.ids() if batch_id.startswith(wanted)]
        if not matches:
            raise BatchNotFound(f"no batch matching {id_or_prefix!r}")
        if len(matches) > 1:
            raise AmbiguousBatchId(
                f"{id_or_prefix!r} matches {len(matches)} batches: "
                + ", ".join(match[:12] for match in matches)
            )
        return matches[0]

    # -- Writing answers --------------------------------------------------

    def record(
        self,
        batch_id: str,
        card_id: str,
        values: dict[str, Any],
        *,
        degraded: bool = False,
        viewer_version: str | None = None,
    ) -> dict[str, Any]:
        """Record one card's answer and return the rewritten answers document.

        An empty ``values`` removes the card's record, which is how un-answering
        works: the file only ever holds cards the human actually touched.

        ``title`` and ``meta`` are echoed from the batch here rather than taken
        from the caller, so the answers file is readable on its own *and* cannot
        be made to disagree with the batch it came from.

        Raises:
            InvalidBatch: ``card_id`` is not in this batch.
        """
        batch = self.read_batch(batch_id)
        card = _find_card(batch, card_id)

        answers = self.read_answers(batch_id)
        records = {record["card_id"]: record for record in answers["answers"]}

        if values:
            records[card_id] = {
                "card_id": card_id,
                "title": card.get("title"),
                "meta": card.get("meta"),
                "values": values,
                "answered_at": utc_now_iso(),
                "degraded": degraded,
            }
        else:
            records.pop(card_id, None)

        answers["answers"] = [
            records[card["id"]] for card in batch["cards"] if card["id"] in records
        ]
        if viewer_version:
            answers["viewer_version"] = viewer_version
        return self._recount_and_write(batch, answers)

    def set_complete(
        self,
        batch_id: str,
        *,
        complete: bool = True,
        degraded_cards: list[str] | None = None,
    ) -> dict[str, Any]:
        """Flip the ``complete`` flag — the one thing ``guide wait`` blocks on.

        Args:
            batch_id: which batch.
            complete: the flag. ``False`` undoes a Done, because nothing here
                should be a one-way door.
            degraded_cards: the viewer's own list, which is wider than the one
                derivable from answer records — see :meth:`_recount_and_write`.
        """
        batch = self.read_batch(batch_id)
        answers = self.read_answers(batch_id)
        answers["complete"] = complete
        # Merged in here rather than passed down, so `_recount_and_write` stays a
        # pure recompute of `batch` + `answers` with no side channel.
        answers["degraded_cards"] = sorted(
            set(answers.get("degraded_cards", [])) | set(degraded_cards or [])
        )
        return self._recount_and_write(batch, answers)

    # -- Removing ---------------------------------------------------------

    def delete(self, batch_id: str) -> None:
        """Remove a batch and its answers permanently."""
        shutil.rmtree(self._dir(batch_id), ignore_errors=True)

    def archive(self, batch_id: str) -> Path:
        """Move a batch out of the inbox and into ``~/.guide/archive/``."""
        source = self._dir(batch_id)
        destination = self.archive_root / batch_id
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(source), str(destination))
        return destination

    # -- Internals --------------------------------------------------------

    def _dir(self, batch_id: str) -> Path:
        """The directory for a batch, refusing an id that is not one.

        Every path this class builds goes through here. Ids are minted by the
        store itself, so an id that is not a ULID cannot name anything real —
        and checking the shape means no caller-supplied string is ever joined to
        the store root unvalidated.
        """
        # Same sentence a missing batch gets. An id that is not a ULID is not a
        # batch that exists, and the distinction is ours, not the caller's.
        if not is_ulid(batch_id):
            raise BatchNotFound(f"no batch {batch_id!r} in the store")
        return self.root / batch_id

    def _file(self, batch_id: str, filename: str) -> Path:
        return self._dir(batch_id) / filename

    def _summarize(self, batch_id: str) -> Summary:
        batch = self.read_batch(batch_id)
        answers = self.read_answers(batch_id)
        source = batch.get("source") or {}
        return Summary(
            id=batch_id,
            title=batch.get("title", "(untitled)"),
            subtitle=batch.get("subtitle"),
            label=source.get("label"),
            repo=source.get("repo"),
            branch=source.get("branch"),
            cwd=source.get("cwd"),
            session_id=source.get("session_id"),
            guide_version=batch.get("guide_version", "0.0.0"),
            created_at=batch.get("created_at"),
            updated_at=answers.get("updated_at"),
            cards=len(batch.get("cards", [])),
            answered=int(answers.get("stats", {}).get("answered", 0)),
            complete=bool(answers.get("complete")),
        )

    def _recount_and_write(
        self, batch: dict[str, Any], answers: dict[str, Any]
    ) -> dict[str, Any]:
        """Recompute every derived field, then write the file atomically.

        Reached only from :meth:`record` and :meth:`set_complete`, which are the
        two things a human does to a batch — so this is also where
        ``started_at`` gets its one and only definition: the first of them.
        """
        answers.setdefault("started_at", utc_now_iso())
        records = {record["card_id"]: record for record in answers["answers"]}
        answered = sum(
            is_answered(records.get(card["id"], {}).get("values", {}), fields_of(card, batch))
            for card in batch["cards"]
        )
        # Two sources, unioned. Per-card flags arrive with each answer; the list
        # already on the document arrives from the viewer at Done, and is the only
        # way a card that could never be answered — because a required field was
        # unrenderable — gets into the record at all.
        reported = set(answers.get("degraded_cards", []))
        degraded_cards = [
            card["id"]
            for card in batch["cards"]
            if records.get(card["id"], {}).get("degraded") or card["id"] in reported
        ]
        answers["degraded"] = bool(degraded_cards)
        answers["degraded_cards"] = degraded_cards
        answers["stats"] = {"total": len(batch["cards"]), "answered": answered}
        answers["updated_at"] = utc_now_iso()
        ordered = _reorder(answers, _CANONICAL_ANSWERS_KEYS)
        _write_json(self._file(batch["id"], ANSWERS_FILENAME), ordered)
        return ordered


def _blank_answers(batch: dict[str, Any]) -> dict[str, Any]:
    """A fresh answers file for a batch nobody has touched yet.

    Written at push time rather than at first answer, so ``guide wait`` has a
    file to watch from the moment the batch exists.
    """
    source = batch.get("source") or {}
    return {
        "guide_version": FORMAT_VERSION,
        "batch_version": batch["guide_version"],
        "viewer_version": FORMAT_VERSION,
        "degraded": False,
        "degraded_cards": [],
        "batch_id": batch["id"],
        "session_id": source.get("session_id"),
        "updated_at": utc_now_iso(),
        "complete": False,
        # Not hardcoded to zero: a batch whose cards have no required fields is
        # vacuously answered, and `guide list` should say so from the start rather
        # than jumping from 0/N to N/N on the first unrelated write.
        "stats": {
            "total": len(batch["cards"]),
            "answered": sum(is_answered({}, fields_of(card, batch)) for card in batch["cards"]),
        },
        "answers": [],
    }


def _canonical_order(batch: dict[str, Any]) -> dict[str, Any]:
    """Reorder a batch so ``guide_version`` is first and the file reads well."""
    return _reorder(batch, _CANONICAL_BATCH_KEYS)


def _reorder(document: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Put known keys in a fixed order, then append the rest.

    Both files declare ``guide_version`` first, which the format requires and
    the envelope check enforces. Keeping the remaining keys in a stable order
    is only courtesy to whoever opens the file in an editor — but unrecognised
    keys must survive, because a batch from a newer minor has to round-trip
    through this build untouched.
    """
    ordered = {key: document[key] for key in keys if key in document}
    ordered.update({k: v for k, v in document.items() if k not in ordered})
    return ordered


def _find_card(batch: dict[str, Any], card_id: str) -> dict[str, Any]:
    """The card with ``card_id``, or a raised :class:`InvalidBatch`."""
    for card in batch["cards"]:
        if card["id"] == card_id:
            return card
    raise InvalidBatch(f"batch {batch['id']} has no card {card_id!r}")


def _read_json(path: Path, batch_id: str) -> dict[str, Any]:
    """Read a JSON file, translating a missing one into :class:`BatchNotFound`."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BatchNotFound(f"no batch {batch_id!r} in the store") from exc


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON so that readers only ever see a whole file.

    ``os.replace`` is atomic within a filesystem, and the temporary file is a
    sibling of its destination to guarantee the two share one. The file's contents
    are fsync'd; the directory entry is not, so a power cut in the microsecond
    after the rename could still lose it. That is the right trade for a local tool,
    and it is stated rather than implied.
    """
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
