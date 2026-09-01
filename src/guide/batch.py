"""Format-level helpers — what the daemon is allowed to know about a batch.

The rule from ``docs/architecture.md`` is that the renderer never learns your
domain. The daemon holds itself to something stricter: it never learns your
*content* either. It does not parse blocks, it does not interpret field values,
and it never touches ``meta``. It knows only the handful of keys it needs to
store a batch, join answers to cards by id, and count progress.

If you ever find yourself adding a block type to this module, the design has
gone wrong: block vocabulary belongs to the browser.
"""

from __future__ import annotations

from typing import Any

from guide.errors import InvalidBatch
from guide.versioning import MalformedVersion, parse

VERSION_KEY = "guide_version"

_REQUIRED_KEYS = (VERSION_KEY, "title", "cards")


def validate_envelope(document: Any) -> None:
    """Check that ``document`` is a batch this build can store.

    Only the envelope is checked. Blocks, fields and ``meta`` are opaque
    passthrough, and validating them here would break the additive-only promise
    the moment an agent targets a newer minor than the daemon.

    Raises:
        InvalidBatch: with a sentence the CLI can print verbatim.
    """
    if not isinstance(document, dict):
        raise InvalidBatch("a batch must be a JSON object")

    missing = [key for key in _REQUIRED_KEYS if key not in document]
    if missing:
        raise InvalidBatch(f"batch is missing required key(s): {', '.join(missing)}")

    # Checked before anything else is parsed, like an XML declaration — so a
    # document from the future fails cleanly instead of half-rendering.
    if next(iter(document)) != VERSION_KEY:
        raise InvalidBatch(f"{VERSION_KEY!r} must be the first key in the document")
    try:
        parse(document[VERSION_KEY])
    except MalformedVersion as exc:
        raise InvalidBatch(str(exc)) from exc

    if not isinstance(document["title"], str) or not document["title"].strip():
        raise InvalidBatch("'title' must be a non-empty string")

    _validate_cards(document["cards"])


def _validate_cards(cards: Any) -> None:
    """Check the card list: objects, with unique non-empty string ids."""
    if not isinstance(cards, list) or not cards:
        raise InvalidBatch("'cards' must be a non-empty array")

    seen: set[str] = set()
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            raise InvalidBatch(f"card {index} is not an object")
        card_id = card.get("id")
        if not isinstance(card_id, str) or not card_id:
            raise InvalidBatch(f"card {index} needs a non-empty string 'id'")
        # Answers join to cards by id alone, with no positional coupling — so a
        # duplicate id would silently merge two people's judgments into one.
        if card_id in seen:
            raise InvalidBatch(f"duplicate card id {card_id!r}")
        seen.add(card_id)


def response_of(card: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any] | None:
    """The response spec for a card, falling back to ``defaults.response``.

    Declaring the buttons once for a 200-card triage is the format's main
    ergonomic win, so the fallback is resolved everywhere rather than assumed.
    """
    response = card.get("response")
    if isinstance(response, dict):
        return response
    default = batch.get("defaults", {})
    default_response = default.get("response") if isinstance(default, dict) else None
    return default_response if isinstance(default_response, dict) else None


def fields_of(card: dict[str, Any], batch: dict[str, Any]) -> list[dict[str, Any]]:
    """The response fields for a card, after defaults are resolved."""
    response = response_of(card, batch)
    fields = response.get("fields") if response else None
    return [f for f in fields if isinstance(f, dict)] if isinstance(fields, list) else []


def is_answered(values: dict[str, Any], fields: list[dict[str, Any]]) -> bool:
    """Whether every required field has a value.

    This is the only progress logic in the system, and it is the whole of it.
    The browser layers one extra condition on top — a required field whose type
    it cannot draw *blocks* the card — but that is a viewer-side fact, so it is
    reported to the daemon rather than recomputed here.
    """
    return all(
        not field.get("required") or _has_value(values.get(field.get("id"))) for field in fields
    )


def _has_value(value: Any) -> bool:
    """Whether a field value counts as filled in.

    ``False`` and ``0`` are real answers from ``boolean`` and ``rating`` fields,
    so this cannot be a plain truthiness test.
    """
    if value is None or value == "":
        return False
    return not (isinstance(value, list) and not value)
