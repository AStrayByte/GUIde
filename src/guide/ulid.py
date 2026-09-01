"""ULIDs — sortable, collision-free batch ids.

Batch ids come from concurrent agent sessions, so two pushes in the same
millisecond must not collide, and ids should sort by creation time so the inbox
has a natural order without reading every file. That is exactly ULID.

48-bit millisecond timestamp followed by 80 bits of randomness, rendered as 26
Crockford base32 characters. Spec: https://github.com/ulid/spec

Hand-rolled rather than taken as a dependency: the encoder is twenty lines of
fully specified arithmetic, and ``tests/test_ulid.py`` pins it against the
spec's own vectors.
"""

from __future__ import annotations

import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Crockford base32: no I, L, O or U, so an id can't be misread aloud."""

_ENCODED_LENGTH = 26
_RANDOM_BITS = 80


def new_ulid(when_ms: int | None = None) -> str:
    """Return a fresh ULID.

    Args:
        when_ms: Unix time in milliseconds. Defaults to now. Only tests pass it.

    Returns:
        A 26-character Crockford base32 string.
    """
    timestamp = time.time_ns() // 1_000_000 if when_ms is None else when_ms
    randomness = secrets.randbits(_RANDOM_BITS)
    return encode(timestamp << _RANDOM_BITS | randomness)


def encode(value: int) -> str:
    """Encode a 128-bit integer as a 26-character Crockford base32 string."""
    digits = []
    for _ in range(_ENCODED_LENGTH):
        value, remainder = divmod(value, 32)
        digits.append(_ALPHABET[remainder])
    return "".join(reversed(digits))


def is_ulid(text: str) -> bool:
    """Whether ``text`` is a well-formed ULID.

    Used by the store to check any id it is about to turn into a path. Every id
    in the store was minted by :func:`new_ulid`, so anything else is either a
    typo or an attempt to walk out of the store directory — and a 26-character
    alphabet check rules out both without a special case for ``..``.

    Case-sensitive on purpose: the store joins the id to a path unchanged, so an
    id that only differs in case would resolve on a case-insensitive filesystem
    and not on a case-sensitive one.
    """
    return len(text) == _ENCODED_LENGTH and all(c in _ALPHABET for c in text)


def timestamp_ms(ulid: str) -> int:
    """Recover the creation time in milliseconds from a ULID."""
    value = 0
    for char in ulid.upper():
        value = value * 32 + _ALPHABET.index(char)
    return value >> _RANDOM_BITS
