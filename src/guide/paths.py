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


def daemon_file() -> Path:
    """Discovery file: how the CLI finds a daemon that moved off the default port."""
    return home() / "daemon.json"


def log_file() -> Path:
    """Where a daemon started in the background sends its output."""
    return home() / "daemon.log"
