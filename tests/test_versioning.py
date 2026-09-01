"""Pins the ``guide_version`` compatibility gate shared with ``web/render.js``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from guide.versioning import Gate, MalformedVersion, Verdict, Version, check, parse

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "version_compat.json"
_COMPAT: dict[str, Any] = json.loads(_FIXTURE_PATH.read_text())


def _cases(table: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    viewer = table["viewer"]
    return [(viewer, case["batch"], case["gate"], case["why"]) for case in table["cases"]]


_MAIN_CASES = _cases(_COMPAT)
_PRE_1_0_CASES = _cases(_COMPAT["pre_1_0"])


def test_version_compat_fixture_matches_the_conftest_loader(
    version_compat: dict[str, Any],
) -> None:
    """The fixture the ``version_compat`` fixture loads is the same file this module reads."""
    assert version_compat == _COMPAT


@pytest.mark.parametrize(
    ("viewer", "batch", "expected_gate", "why"),
    _MAIN_CASES,
    ids=[f"{batch}_vs_{viewer}_{gate}" for viewer, batch, gate, _ in _MAIN_CASES],
)
def test_check_matches_the_1x_compat_table(
    viewer: str, batch: str, expected_gate: str, why: str
) -> None:
    verdict: Verdict = check(batch, viewer)
    assert verdict.gate is Gate(expected_gate), why


@pytest.mark.parametrize(
    ("viewer", "batch", "expected_gate", "why"),
    _PRE_1_0_CASES,
    ids=[f"{batch}_vs_{viewer}_{gate}" for viewer, batch, gate, _ in _PRE_1_0_CASES],
)
def test_check_matches_the_pre_1_0_compat_table(
    viewer: str, batch: str, expected_gate: str, why: str
) -> None:
    verdict: Verdict = check(batch, viewer)
    assert verdict.gate is Gate(expected_gate), why


def test_pre_1_0_minor_is_a_hard_gate() -> None:
    """While the format is 0.x, a minor bump is refused exactly like a major one."""
    assert check("0.2.0", "0.1.0").gate is Gate.HARD
    assert check("0.0.9", "0.1.0").gate is Gate.HARD


def test_verdict_readable_is_false_only_for_the_hard_gate() -> None:
    assert check("1.4.2", "1.4.2").readable is True
    assert check("1.6.0", "1.4.2").readable is True
    assert check("2.0.0", "1.4.2").readable is False


@pytest.mark.parametrize("text", ["1.2", "^1.2.3", "latest", "1.2.3.4", ""])
def test_parse_rejects_anything_that_is_not_major_minor_patch(text: str) -> None:
    with pytest.raises(MalformedVersion):
        parse(text)


def test_parse_accepts_major_minor_patch() -> None:
    assert parse("1.2.3") == Version(1, 2, 3)


def test_version_str_round_trips_to_the_wire_form() -> None:
    assert str(parse("1.2.3")) == "1.2.3"
