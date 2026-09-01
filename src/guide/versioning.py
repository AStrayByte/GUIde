"""The ``guide_version`` compatibility contract.

For most formats a version mismatch means an ugly page. For this one it means a
human makes a judgment call on evidence they cannot fully see, and an agent then
acts on that judgment. So the rules are deliberately strict and the failure is
deliberately loud. The prose version lives in ``docs/versioning.md``.

The same rules are implemented in the browser (``web/render.js``) because the
page must gate a batch opened over ``file://`` with no daemon in the picture.
``tests/fixtures/version_compat.json`` is the shared truth table both sides are
checked against — change a rule there and both implementations must move.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class MalformedVersion(ValueError):
    """A version string that is not exactly ``major.minor.patch``."""


class Version(NamedTuple):
    """A parsed ``major.minor.patch`` triple."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        """Render back to the wire form."""
        return f"{self.major}.{self.minor}.{self.patch}"


def parse(text: str) -> Version:
    """Parse ``major.minor.patch``.

    Raises:
        MalformedVersion: on ranges, ``^`` prefixes, ``latest``, or two-part
            versions. The format admits exactly one spelling on purpose.
    """
    match = _VERSION_PATTERN.match(str(text))
    if match is None:
        raise MalformedVersion(f"expected major.minor.patch, got {text!r}")
    return Version(*(int(part) for part in match.groups()))


class Gate(StrEnum):
    """What the viewer is allowed to do with a batch."""

    OK = "ok"
    """Render normally. Nothing to say to the user."""

    WARN = "warn"
    """Render, but say so: the batch is minor-ahead and content may fall back."""

    HARD = "hard"
    """Refuse. Rendering this could show someone less than the whole picture."""


@dataclass(frozen=True, slots=True)
class Verdict:
    """The outcome of a version check, with the sentence to show the user."""

    gate: Gate
    reason: str
    message: str

    @property
    def readable(self) -> bool:
        """Whether the batch may be rendered at all."""
        return self.gate is not Gate.HARD


def check(batch_version: str, viewer_version: str) -> Verdict:
    """Decide whether ``viewer_version`` may render a batch at ``batch_version``.

    The rules, in the order they are applied:

    * different major — hard error, in *either* direction. A viewer reads one
      format major and no other.
    * pre-1.0, different minor — hard error too. While the format is ``0.x``,
      minor is allowed to break, so it acts as major.
    * batch minor ahead — render, and warn. Additive-only minors mean unknown
      blocks and fields degrade visibly rather than vanish.
    * batch minor behind, or any patch difference — silent. This is the
      forward-compatibility the additive-only rule buys.
    """
    batch, viewer = parse(batch_version), parse(viewer_version)

    if batch.major != viewer.major:
        return Verdict(
            Gate.HARD,
            "major",
            f"This batch declares GUIde {batch} and this viewer is {viewer}. "
            f"A major mismatch is a hard error.",
        )
    if batch.major == 0 and batch.minor != viewer.minor:
        return Verdict(
            Gate.HARD,
            "pre-1.0 minor",
            f"This batch declares GUIde {batch} and this viewer is {viewer}. "
            f"Pre-1.0, a minor bump is allowed to break the format, so this is "
            f"treated as a major mismatch and refused outright.",
        )
    if batch.minor > viewer.minor:
        return Verdict(
            Gate.WARN,
            "minor ahead",
            f"This batch uses GUIde {batch}; this viewer is {viewer}. Some "
            f"content may fall back, and every place it does says so on the "
            f"card where it happened.",
        )
    return Verdict(Gate.OK, "compatible", "")
