"""Pins the on-disk store contract: id minting, atomic writes, and derived answers state."""

from __future__ import annotations

import json

import pytest

from conftest import make_batch
from guide.errors import AmbiguousBatchId, BatchNotFound, InvalidBatch
from guide.store import ANSWERS_FILENAME, BATCH_FILENAME, Store


def test_create_mints_a_ulid_and_ignores_a_client_supplied_id(store: Store) -> None:
    stored = store.create(make_batch(id="client-supplied-junk"))
    assert stored["id"] != "client-supplied-junk"
    assert len(stored["id"]) == 26


def test_create_writes_guide_version_as_the_first_key_on_disk(store: Store) -> None:
    stored = store.create(make_batch())
    on_disk = json.loads((store.root / stored["id"] / BATCH_FILENAME).read_text())
    assert next(iter(on_disk)) == "guide_version"


def test_create_writes_a_blank_answers_file_immediately(store: Store) -> None:
    stored = store.create(make_batch())
    answers = store.read_answers(stored["id"])
    assert answers["complete"] is False
    assert answers["answers"] == []
    assert answers["stats"] == {"total": 2, "answered": 0}


def test_create_with_no_required_fields_reports_every_card_answered_from_the_start(
    store: Store,
) -> None:
    """A batch with nothing required is vacuously answered — not 0/N until some
    unrelated write happens to recompute it."""
    stored = store.create(make_batch(defaults={}))
    answers = store.read_answers(stored["id"])
    assert answers["stats"] == {"total": 2, "answered": 2}


def test_record_echoes_title_and_meta_from_the_batch_not_the_caller(store: Store) -> None:
    """A malicious ``values`` payload cannot spoof the echoed title/meta."""
    stored = store.create(make_batch())
    junk_values = {"title": "SPOOFED TITLE", "meta": {"evil": True}, "verdict": "yes"}

    answers = store.record(stored["id"], "1", junk_values)

    [record] = answers["answers"]
    assert record["title"] == stored["cards"][0]["title"]
    assert record["meta"] == stored["cards"][0]["meta"]
    assert record["values"] == junk_values


def test_record_with_empty_values_removes_the_record(store: Store) -> None:
    stored = store.create(make_batch())
    store.record(stored["id"], "1", {"verdict": "yes"})

    answers = store.record(stored["id"], "1", {})

    assert answers["answers"] == []


def test_record_rejects_an_unknown_card_id(store: Store) -> None:
    stored = store.create(make_batch())
    with pytest.raises(InvalidBatch):
        store.record(stored["id"], "no-such-card", {"verdict": "yes"})


def test_stats_answered_tracks_required_field_satisfaction(store: Store) -> None:
    stored = store.create(make_batch())

    answered = store.record(stored["id"], "2", {"verdict": "yes"})
    assert answered["stats"]["answered"] == 1

    unanswered = store.record(stored["id"], "2", {"comment": "only the optional field"})
    assert unanswered["stats"]["answered"] == 0


def test_degraded_and_degraded_cards_derive_from_per_card_flags(store: Store) -> None:
    stored = store.create(make_batch())
    store.record(stored["id"], "1", {"verdict": "yes"}, degraded=True)

    answers = store.record(stored["id"], "2", {"verdict": "no"}, degraded=False)

    assert answers["degraded"] is True
    assert answers["degraded_cards"] == ["1"]


def test_answers_come_back_in_batch_card_order_not_recording_order(store: Store) -> None:
    stored = store.create(make_batch())
    store.record(stored["id"], "2", {"verdict": "no"})

    answers = store.record(stored["id"], "1", {"verdict": "yes"})

    assert [record["card_id"] for record in answers["answers"]] == ["1", "2"]


def test_set_complete_flips_the_flag(store: Store) -> None:
    stored = store.create(make_batch())

    assert store.set_complete(stored["id"])["complete"] is True
    assert store.set_complete(stored["id"], complete=False)["complete"] is False


def test_set_complete_on_a_batch_nobody_answered_still_sets_started_at(store: Store) -> None:
    stored = store.create(make_batch())

    answers = store.set_complete(stored["id"])

    assert answers.get("started_at")


def test_resolve_expands_an_id_prefix(store: Store) -> None:
    stored = store.create(make_batch())
    assert store.resolve(stored["id"][:8].lower()) == stored["id"]


def test_resolve_raises_batch_not_found_for_no_match(store: Store) -> None:
    with pytest.raises(BatchNotFound):
        store.resolve("NOSUCHBATCH")


def test_resolve_raises_ambiguous_batch_id_for_multiple_matches(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = iter(["AAAAAAAAAAAAAAAAAAAAAAAAAA", "AAAAAAAAAAAAAAAAAAAAAAAAAB"])
    monkeypatch.setattr("guide.store.new_ulid", lambda: next(ids))
    store.create(make_batch())
    store.create(make_batch())

    with pytest.raises(AmbiguousBatchId):
        store.resolve("AAAAAAAA")


def test_summaries_skips_a_corrupt_batch_directory(store: Store) -> None:
    good = store.create(make_batch())
    corrupt = store.create(make_batch())
    (store.root / corrupt["id"] / BATCH_FILENAME).write_text("{not json", encoding="utf-8")

    summaries = store.summaries()

    assert [summary.id for summary in summaries] == [good["id"]]


def test_archive_moves_the_batch_directory(store: Store) -> None:
    stored = store.create(make_batch())

    destination = store.archive(stored["id"])

    assert not (store.root / stored["id"]).exists()
    assert (destination / BATCH_FILENAME).is_file()
    assert (destination / ANSWERS_FILENAME).is_file()


def test_unknown_top_level_and_card_keys_survive_the_round_trip(store: Store) -> None:
    """Additive-only minors depend on unrecognised keys passing through untouched."""
    document = make_batch(future_top_level={"widget": "timeline"})
    document["cards"][0]["future_card_key"] = "value from a newer minor"

    stored = store.create(document)

    assert stored["future_top_level"] == {"widget": "timeline"}
    assert stored["cards"][0]["future_card_key"] == "value from a newer minor"
