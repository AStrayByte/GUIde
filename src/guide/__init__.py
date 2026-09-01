"""GUIde — a local inbox for the questions your agents need answered.

An agent writes a *batch* (a JSON file of questions plus the evidence needed to
answer them) and pushes it to a daemon on this machine. A browser page renders
the batch as cards; you click through them; the daemon writes an *answers* file
back to disk. The agent reads it and keeps working.

The layering, which the module boundaries follow exactly:

``versioning``  the compatibility contract for ``guide_version``
``batch``       format-level helpers — never domain-level, never rendering
``store``       what lives on disk under ``~/.guide/``
``daemon``      HTTP surface, SSE fan-out, process lifecycle
``cli``         ``push`` / ``wait`` / ``list`` / ``clean`` / ``serve`` / ``skill``
``web``         the page: no build step, so it also opens over ``file://``
"""

__version__ = "0.1.0"
"""The package version. Bumped for any release, including renderer-only fixes."""

FORMAT_VERSION = "0.1.0"
"""The batch/answers format this build speaks. Reported by ``guide --format-version``.

Distinct from ``__version__`` on purpose: a renderer bugfix ships a new package
without touching the contract agents write against.
"""

API_VERSION = "v0"
"""HTTP surface version. In the path, so a future shape can be served alongside."""

API_PREFIX = f"/api/{API_VERSION}"

__all__ = ["API_PREFIX", "API_VERSION", "FORMAT_VERSION", "__version__"]
