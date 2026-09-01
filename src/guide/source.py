"""Working out who is pushing a batch, so the agent doesn't have to say.

``source`` stopped being decorative the moment several sessions shared one
inbox: ``repo`` and ``label`` are what the rail groups by, and ``session_id`` is
how a waiting session recognises its own answers. An agent asked to fill this in
by hand will forget, or guess, so ``guide push`` works it out from the
environment and only fills in what the batch left blank.

Nothing here fails. A batch pushed from a directory that is not a git checkout
just has fewer keys in its ``source``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

_GIT_TIMEOUT = 2.0

_SESSION_ID_VARS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")
"""Where a Claude Code session announces itself.

``CLAUDE_CODE_SESSION_ID`` is the one Claude Code actually exports; the shorter
name is kept as a fallback because it is the obvious thing for another agent to
set. Getting this wrong is quiet and expensive: without a session id every
``guide wait`` falls back to matching on the working directory, so two sessions
in one repo would wake on each other's answers.
"""


def describe_environment() -> dict[str, Any]:
    """What can be discovered about the session doing the pushing."""
    cwd = Path.cwd()
    described: dict[str, Any] = {"agent": _agent(), "cwd": str(cwd)}

    session_id = next(
        (value for var in _SESSION_ID_VARS if (value := os.environ.get(var))), None
    )
    if session_id:
        described["session_id"] = session_id

    toplevel = _git(cwd, "rev-parse", "--show-toplevel")
    if toplevel:
        described["repo"] = Path(toplevel).name
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        described["branch"] = branch

    return described


def fill_source(batch: dict[str, Any], *, label: str | None = None) -> dict[str, Any]:
    """Return ``batch`` with a completed ``source``, without overwriting the agent.

    Anything the agent stated wins: it may know something the environment does
    not, such as which of several sessions in one repo it belongs to.
    """
    source = dict(batch.get("source") or {})
    for key, value in describe_environment().items():
        source.setdefault(key, value)
    if label:
        source["label"] = label
    source.setdefault("label", batch.get("title", "batch"))
    return {**batch, "source": source}


def _agent() -> str:
    """A best guess at what is driving this push."""
    if os.environ.get("CLAUDECODE") or any(map(os.environ.get, _SESSION_ID_VARS)):
        return "claude-code"
    return "cli"


def _git(cwd: Path, *args: str) -> str | None:
    """Run a read-only git command, or return ``None`` if that is not possible."""
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", *args],  # noqa: S607 — git is expected on PATH, absence is handled
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout.strip()
    return output if result.returncode == 0 and output else None
