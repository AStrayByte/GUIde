"""Pins the batch envelope contract: what ``validate_envelope`` gates before parsing."""

from __future__ import annotations

from typing import Any

import pytest

from conftest import make_batch
from guide.batch import VERSION_KEY, fields_of, is_answered, response_of, validate_envelope
from guide.errors import InvalidBatch

# -- validate_envelope: shape of the document itself -----------------------


def test_validate_envelope_accepts_a_well_formed_batch() -> None:
    validate_envelope(make_batch())  # must not raise


@pytest.mark.parametrize("document", [[], "not a dict", None, 42, ("t",)])
def test_validate_envelope_rejects_a_document_that_is_not_an_object(document: Any) -> None:
    with pytest.raises(InvalidBatch, match="object"):
        validate_envelope(document)


@pytest.mark.parametrize("missing_key", [VERSION_KEY, "title", "cards"])
def test_validate_envelope_rejects_a_missing_required_key(missing_key: str) -> None:
    document = make_batch()
    del document[missing_key]
    with pytest.raises(InvalidBatch, match="missing required key"):
        validate_envelope(document)


def test_validate_envelope_requires_guide_version_to_be_the_first_key() -> None:
    """XML-declaration rule: a document from the future must fail before it is parsed."""
    document = make_batch()
    reordered = {
        "title": document["title"],
        VERSION_KEY: document[VERSION_KEY],
        "cards": document["cards"],
    }
    with pytest.raises(InvalidBatch, match="first key"):
        validate_envelope(reordered)


@pytest.mark.parametrize("bad_version", ["1.2", "^1.2.3", "latest", "1.2.3.4", ""])
def test_validate_envelope_rejects_a_malformed_version(bad_version: str) -> None:
    with pytest.raises(InvalidBatch):
        validate_envelope(make_batch(guide_version=bad_version))


@pytest.mark.parametrize("bad_title", ["", "   ", 42, None])
def test_validate_envelope_rejects_a_non_string_or_blank_title(bad_title: Any) -> None:
    with pytest.raises(InvalidBatch, match="title"):
        validate_envelope(make_batch(title=bad_title))


# -- validate_envelope: cards ------------------------------------------------


def test_validate_envelope_rejects_an_empty_cards_list() -> None:
    with pytest.raises(InvalidBatch, match="non-empty array"):
        validate_envelope(make_batch(cards=[]))


@pytest.mark.parametrize("cards", [["not a dict"], [None], [{"id": "1"}, 42]])
def test_validate_envelope_rejects_a_card_that_is_not_an_object(cards: list[Any]) -> None:
    with pytest.raises(InvalidBatch, match="not an object"):
        validate_envelope(make_batch(cards=cards))


@pytest.mark.parametrize("card", [{}, {"id": ""}, {"id": None}, {"title": "no id here"}])
def test_validate_envelope_rejects_a_card_with_no_usable_id(card: dict[str, Any]) -> None:
    with pytest.raises(InvalidBatch, match="'id'"):
        validate_envelope(make_batch(cards=[card]))


def test_validate_envelope_rejects_duplicate_card_ids() -> None:
    with pytest.raises(InvalidBatch, match="duplicate card id"):
        validate_envelope(make_batch(cards=[{"id": "1"}, {"id": "1"}]))


# -- response_of / fields_of: default resolution ----------------------------


def test_response_of_falls_back_to_batch_defaults() -> None:
    batch = make_batch()
    card_without_its_own_response = batch["cards"][1]
    assert response_of(card_without_its_own_response, batch) == batch["defaults"]["response"]


def test_response_of_prefers_the_cards_own_response_over_defaults() -> None:
    own_response = {"fields": [{"id": "x", "type": "text"}]}
    batch = make_batch(cards=[{"id": "1", "response": own_response}])
    assert response_of(batch["cards"][0], batch) == own_response


def test_response_of_returns_none_without_a_response_or_defaults() -> None:
    batch = make_batch(cards=[{"id": "1"}], defaults={})
    assert response_of(batch["cards"][0], batch) is None


def test_fields_of_resolves_the_default_response_fields() -> None:
    batch = make_batch()
    card_without_its_own_response = batch["cards"][1]
    fields = fields_of(card_without_its_own_response, batch)
    assert [field["id"] for field in fields] == ["verdict", "comment"]


def test_fields_of_uses_a_cards_own_response_instead_of_defaults() -> None:
    batch = make_batch(
        cards=[{"id": "1", "response": {"fields": [{"id": "only", "type": "text"}]}}]
    )
    fields = fields_of(batch["cards"][0], batch)
    assert [field["id"] for field in fields] == ["only"]


def test_fields_of_returns_an_empty_list_without_a_response() -> None:
    batch = make_batch(cards=[{"id": "1"}], defaults={})
    assert fields_of(batch["cards"][0], batch) == []


# -- is_answered --------------------------------------------------------------

_REQUIRED_TEXT_FIELD = [{"id": "note", "type": "text", "required": True}]


def test_is_answered_true_when_no_field_is_required() -> None:
    assert is_answered({}, [{"id": "comment", "type": "text"}]) is True


def test_is_answered_true_when_every_required_field_has_a_value() -> None:
    assert is_answered({"note": "looks fine"}, _REQUIRED_TEXT_FIELD) is True


def test_is_answered_false_when_a_required_field_is_absent() -> None:
    assert is_answered({}, _REQUIRED_TEXT_FIELD) is False


@pytest.mark.parametrize("blank_value", [None, ""])
def test_is_answered_false_for_none_or_empty_string(blank_value: Any) -> None:
    assert is_answered({"note": blank_value}, _REQUIRED_TEXT_FIELD) is False


def test_is_answered_false_for_an_empty_list() -> None:
    fields = [{"id": "tags", "type": "multichoice", "required": True}]
    assert is_answered({"tags": []}, fields) is False


@pytest.mark.parametrize("real_answer", [False, 0])
def test_is_answered_true_for_false_and_zero_as_real_answers(real_answer: Any) -> None:
    """False and 0 are genuine boolean/rating answers, not "missing"."""
    fields = [{"id": "flag", "type": "boolean", "required": True}]
    assert is_answered({"flag": real_answer}, fields) is True


def test_is_answered_false_when_any_one_required_field_is_missing() -> None:
    fields = [
        {"id": "a", "type": "text", "required": True},
        {"id": "b", "type": "text", "required": True},
    ]
    assert is_answered({"a": "ok"}, fields) is False
