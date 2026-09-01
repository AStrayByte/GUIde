"""The exceptions GUIde raises at its own boundaries.

Everything here inherits ``GuideError``, which the CLI catches once at the top
level and prints as a single readable line. Anything that escapes as a traceback
is a bug, not a user error.
"""

from __future__ import annotations


class GuideError(Exception):
    """Base class for every expected failure."""


class InvalidBatch(GuideError):
    """A pushed document is not a batch this build can store."""


class IncompatibleVersion(GuideError):
    """A batch declares a ``guide_version`` this build refuses to render."""


class BatchNotFound(GuideError):
    """No batch in the store matches the given id or prefix."""


class AmbiguousBatchId(GuideError):
    """An id prefix matches more than one batch."""


class DaemonUnreachable(GuideError):
    """The daemon could not be reached, and could not be started."""
