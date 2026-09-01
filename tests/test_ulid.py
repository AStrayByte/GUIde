"""Pins the hand-rolled ULID encoder against the spec: alphabet, length, and time round-trip."""

from __future__ import annotations

from guide.ulid import _ALPHABET, is_ulid, new_ulid, timestamp_ms


def test_new_ulid_is_26_crockford_base32_characters() -> None:
    ulid = new_ulid()
    assert len(ulid) == 26
    assert all(char in _ALPHABET for char in ulid)


def test_new_ulid_sorts_by_creation_time_for_increasing_timestamps() -> None:
    ulids = [new_ulid(when_ms=ms) for ms in (1_000, 2_000, 3_000, 4_000)]
    assert sorted(ulids) == ulids


def test_timestamp_ms_round_trips_a_known_millisecond() -> None:
    known_ms = 1_700_000_000_123
    assert timestamp_ms(new_ulid(when_ms=known_ms)) == known_ms


def test_is_ulid_accepts_a_real_ulid() -> None:
    assert is_ulid(new_ulid()) is True


def test_is_ulid_rejects_a_short_string() -> None:
    assert is_ulid("abc") is False


def test_is_ulid_rejects_characters_outside_the_crockford_alphabet() -> None:
    for excluded_char in "ILOU":
        assert is_ulid(excluded_char * 26) is False


def test_is_ulid_rejects_the_empty_string() -> None:
    assert is_ulid("") is False
