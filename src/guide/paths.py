"""Where GUIde keeps its things.

Everything sits under ``~/.guide``, deliberately outside every working tree: a
batch may carry real client data, and a directory that is not in any repo cannot
be accidentally committed. That is a structural guarantee rather than a
``.gitignore`` line someone forgets to copy into the next project.

::

    ~/.guide/
    |-- daemon.json          how the CLI finds a running daemon
    |-- daemon.log           output of a daemon started in the background
    |-- batches/<ulid>/      batch.json + answers.json   (owned by store.Store)
    `-- archive/<ulid>/      what `guide clean --archive` keeps

Only the top-level files live here; the two directories belong to
:class:`guide.store.Store`, which derives them from the same root.

``GUIDE_HOME`` relocates the whole tree. The test suite leans on it; so can
anyone who wants batches on an encrypted volume.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV_VAR = "GUIDE_HOME"

WEB_DIR = Path(__file__).resolve().parent / "web"
"""The page, as shipped inside the package.

Here rather than in ``daemon/app.py`` so that the routes serving a file from it
do not have to import the application module they are mounted into.
"""


def home() -> Path:
    """The root of everything — ``$GUIDE_HOME`` or ``~/.guide``."""
    override = os.environ.get(HOME_ENV_VAR)
    return Path(override).expanduser() if override else Path.home() / ".guide"


def ensure_home(root: Path | None = None) -> Path:
    """Create the store root if it doesn't exist yet, and lock it to 0700 either way.

    Batches may hold real client data, so this root is not for other local
    accounts to read or even list — and directory traversal permission is
    per-component, so 0700 here alone denies access regardless of what mode
    its children end up at. ``mkdir(mode=...)`` only sets the mode at
    creation and is masked by the process umask besides, so it cannot be
    trusted alone; it is also a no-op on a directory that already exists,
    which is why the ``chmod`` after it is unconditional rather than only
    covering the just-created case. Every site that creates something under
    this root calls this first, so the guarantee has exactly one owner
    instead of each call site reasserting it on its own with the risk that
    one gets missed — which is exactly how it went missing before.
    """
    directory = root if root is not None else home()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory


def daemon_file() -> Path:
    """Discovery file: how the CLI finds a daemon that moved off the default port."""
    return home() / "daemon.json"


def log_file() -> Path:
    """Where a daemon started in the background sends its output."""
    return home() / "daemon.log"
