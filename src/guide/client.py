"""The CLI's side of the HTTP surface.

Thin on purpose. Its whole job is to turn transport failures into the sentences
:mod:`guide.errors` promises the CLI can print without a traceback.

Note what is *not* here: ``guide wait``. Waiting watches the answers file on
disk rather than asking the daemon, so a session can keep waiting across a
daemon restart — see ``docs/decisions/0004-daemon-lifecycle.md``.
"""

from __future__ import annotations

from typing import Any

import httpx

from guide import API_PREFIX
from guide.daemon.lifecycle import ensure_running
from guide.errors import DaemonUnreachable, GuideError

_TIMEOUT = 10.0
_NO_CONTENT = 204


class Client:
    """A connection to a running daemon."""

    def __init__(self, url: str) -> None:
        """Point at a daemon that is already known to be running."""
        self.url = url.rstrip("/")

    @classmethod
    def connect(cls) -> tuple[Client, bool]:
        """Find a daemon, starting one if there isn't one.

        Returns:
            ``(client, started)`` — ``started`` says whether this call spawned
            the daemon, so the caller can print the notice exactly once.
        """
        url, started = ensure_running()
        return cls(url), started

    # -- Calls ------------------------------------------------------------

    def meta(self) -> dict[str, Any]:
        """Version and liveness information about the daemon."""
        return self._request("GET", "/meta")

    def push(self, document: Any) -> dict[str, Any]:
        """Store a batch. Returns ``{id, cards, waiting, url}``."""
        return self._request("POST", "/batches", json=document)

    def inbox(self) -> list[dict[str, Any]]:
        """Every batch in the store, oldest first."""
        result = self._request("GET", "/batches")
        return result if isinstance(result, list) else []

    def batch(self, batch_id: str) -> dict[str, Any]:
        """One batch document."""
        return self._request("GET", f"/batches/{batch_id}")

    def answers(self, batch_id: str) -> dict[str, Any]:
        """One answers document."""
        return self._request("GET", f"/batches/{batch_id}/answers")

    def remove(self, batch_id: str, *, archive: bool = False) -> None:
        """Delete a batch, or archive it."""
        self._request(
            "DELETE", f"/batches/{batch_id}", params={"archive": str(archive).lower()}
        )

    # -- Transport --------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make one call, translating every failure into a :class:`GuideError`."""
        try:
            response = httpx.request(
                method, f"{self.url}{API_PREFIX}{path}", timeout=_TIMEOUT, **kwargs
            )
        except httpx.HTTPError as exc:
            raise DaemonUnreachable(f"could not reach the daemon at {self.url}: {exc}") from exc

        if response.is_success:
            return None if response.status_code == _NO_CONTENT else response.json()
        raise GuideError(_explain(response))


def _explain(response: httpx.Response) -> str:
    """Turn an error response into one readable line.

    FastAPI reports a rejected body as ``{"detail": ...}``, where ``detail`` is
    our own sentence for a raised ``HTTPException`` and a list of field errors
    when Pydantic did the rejecting.
    """
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None

    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        location = " -> ".join(str(part) for part in first.get("loc", [])[1:])
        return f"{first.get('msg', 'invalid request')} at {location}".strip()
    return f"the daemon returned HTTP {response.status_code}"
