"""Allow ``python -m guide``.

The background daemon is spawned this way rather than through the ``guide``
console script, so it runs under the same interpreter as the process that
started it whether or not that interpreter's ``bin`` is on PATH.
"""

from guide.cli import main

raise SystemExit(main())
