"""Routes behind the *Install the skill* page.

The daemon already knows two things a copy-pasted README cannot: the exact
``SKILL.md`` that matches this build, and whether it is installed right now. So
the install instructions live in the app, and they are accurate by construction.

The page offers three paths (see :mod:`guide.skill`); this module is just the
plumbing that hands them to the browser.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from guide import API_PREFIX, __version__
from guide.paths import WEB_DIR
from guide.skill import (
    SKILL_FILENAME,
    default_install_dir,
    install,
    install_prompt,
    is_installed,
    markdown,
)

skill_router = APIRouter()


@skill_router.get("/skill", include_in_schema=False)
def skill_page() -> FileResponse:
    """The install page itself. A friendly URL for ``/skill.html``."""
    return FileResponse(WEB_DIR / "skill.html", media_type="text/html")


@skill_router.get(f"{API_PREFIX}/skill")
def skill_info() -> dict[str, Any]:
    """Everything the install page renders: the file, where it goes, the prompt."""
    return {
        "name": SKILL_FILENAME,
        "guide_version": __version__,
        "install_path": str(default_install_dir() / SKILL_FILENAME),
        "installed": is_installed(),
        "command": "guide skill install",
        "prompt": install_prompt(),
        "content": markdown(),
    }


@skill_router.post(f"{API_PREFIX}/skill/install")
def skill_install() -> dict[str, Any]:
    """Write the skill file. What the page's one-click button calls."""
    try:
        written = install()
    except OSError as exc:
        raise HTTPException(500, f"could not write the skill file: {exc}") from exc
    return {"installed": True, "path": str(written)}
