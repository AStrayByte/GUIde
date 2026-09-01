"""The Claude Code skill, and the three ways of installing it.

``SKILL.md`` ships inside the package rather than in the repo root, so the copy
an agent installs is always the one that matches the ``guide`` binary it will be
calling. A skill that documents a format the installed daemon does not speak is
worse than no skill.

The three ways, in order of how much the user has to trust us:

* ``guide skill install`` — we write the file.
* the **Install the skill** page — a button that calls the same code, plus the
  file contents to copy by hand.
* :func:`install_prompt` — a paragraph to paste into Claude, which then writes
  the file itself. This is the path that works when someone would rather their
  agent did it, or when ``guide`` is not on their PATH yet.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

SKILL_NAME = "guide"
SKILL_FILENAME = "SKILL.md"


def markdown() -> str:
    """The skill file's contents."""
    return (resources.files(__package__) / SKILL_FILENAME).read_text(encoding="utf-8")


def default_install_dir() -> Path:
    """Where Claude Code looks for user-level skills."""
    return Path.home() / ".claude" / "skills" / SKILL_NAME


def install(directory: Path | None = None) -> Path:
    """Write ``SKILL.md`` into the skills directory. Returns the path written.

    Overwrites without asking, because the file is generated and the only
    correct version of it is the one shipped with this build.
    """
    target = (directory or default_install_dir()) / SKILL_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown(), encoding="utf-8")
    return target


def is_installed(directory: Path | None = None) -> bool:
    """Whether a skill file is already in place (any version of it)."""
    return ((directory or default_install_dir()) / SKILL_FILENAME).is_file()


def install_prompt() -> str:
    """A paragraph to paste into Claude, which makes it install the skill.

    Deliberately tells Claude to read the file off disk instead of embedding the
    skill's text: pasting a 200-line document into a chat window is miserable,
    and the copy on disk cannot drift from the installed binary.
    """
    source = resources.files(__package__) / SKILL_FILENAME
    return (
        f"Install the GUIde skill for me.\n\n"
        f"1. Read the skill file at: {source}\n"
        f"2. Write it, unchanged, to: {default_install_dir() / SKILL_FILENAME}\n"
        f"   (create the directory if it does not exist)\n"
        f"3. Confirm the file is there and tell me to restart Claude Code so it "
        f"picks up the new skill.\n\n"
        f"Do not edit or summarise the contents — copy the file verbatim."
    )
