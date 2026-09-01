"""The ASGI application: API routes, the page, and the headers that fence it in.

Batch content is agent-authored, which makes the browser the one place in this
system where untrusted-ish text becomes markup. Two defences, deliberately
independent:

1. The renderer builds DOM nodes and sets ``textContent``. The only exception is
   the ``markdown`` text block, which escapes first and then emits a fixed set
   of tags — see ``docs/decisions/0006-markdown-by-construction.md``.
2. The Content-Security-Policy below, which means that even if (1) has a bug,
   the injected markup has nowhere to go: no inline script, no remote anything,
   no form target, no frame.

The policy also enforces a design rule the docs already state — *no outbound
requests from the page.* No CDN, no fonts, no analytics. A batch may hold client
data, and the page it is drawn on cannot phone home.

A third defence sits below both of the above, because they only hold if the
socket is only ever reached by this daemon's own page: ``LoopbackHostOnly``.
Binding 127.0.0.1 does not mean "nobody else is on the socket" — DNS rebinding
gets a browser to treat an attacker-controlled page as same-origin with this
daemon. The attacker registers a domain whose A record is 127.0.0.1 (or
rebinds it there after the page loads), serves a page from it, and that page's
``fetch()`` calls carry a ``Host`` header of the attacker's domain — which is
exactly what ``request.url.netloc`` in ``_same_origin`` reads. The Origin
sent by the browser matches that same Host, so ``SameOriginOnly`` passes it:
same-origin checks are only as trustworthy as the Host they are compared
against. ``LoopbackHostOnly`` closes that gap by checking the Host header
itself against a fixed allowlist, independent of what Origin claims.
"""

from __future__ import annotations

import os
import signal
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from guide.paths import WEB_DIR
from guide.store import Store

from .api import router
from .service import Daemon
from .skillpage import skill_router

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        # The `image` block carries data URIs and nothing else, by format rule.
        "img-src 'self' data:",
        # fetch() and EventSource back to this daemon. Nowhere else.
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    )
)

_SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})
"""What ``Host`` is allowed to name. Port-agnostic — a loopback bind can move.

``request.url.hostname`` (Starlette's parsed form of the ``Host`` header)
already strips the port and the IPv6 bracket syntax, so ``Host: [::1]:7777``
compares equal to ``"::1"`` here with no extra normalization. Verified against
``starlette.datastructures.URL`` directly rather than assumed.
"""


class SecurityHeaders(BaseHTTPMiddleware):
    """Attach the fixed header set to every response."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        """Add the headers on the way out."""
        response = await call_next(request)  # type: ignore[operator]
        response.headers.update(_SECURITY_HEADERS)
        return response


class SameOriginOnly(BaseHTTPMiddleware):
    """Refuse state-changing requests that a foreign web page set in motion.

    "Bound to 127.0.0.1, so there is nobody else on the socket" is not quite
    true: every web page in every open tab is on that socket too. A cross-origin
    ``POST`` with no custom headers is a *simple request* — no preflight, so the
    browser sends it and merely hides the response. That is enough for a side
    effect. Any page you visited could otherwise stop your daemon mid-review.

    The check is deliberately dumb. A browser labels its own requests
    (``Sec-Fetch-Site``, and ``Origin`` on anything cross-origin); the CLI, being
    a plain HTTP client, sends neither. So: trust an explicit same-origin label,
    trust the absence of any label, and refuse everything else.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        """Reject a cross-site write before it reaches a route."""
        if request.method not in SAFE_METHODS and not _same_origin(request):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "cross-site requests cannot change anything here. "
                    "Use the guide CLI, or the page served by this daemon."
                },
                headers=_SECURITY_HEADERS,
            )
        return await call_next(request)  # type: ignore[operator]


def _same_origin(request: Request) -> bool:
    """Whether a state-changing request came from this daemon's own page or the CLI."""
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        # "none" is a user-initiated navigation; anything cross-site says so.
        return fetch_site in {"same-origin", "none"}
    origin = request.headers.get("origin")
    if origin is None:
        return True  # not a browser: the CLI, an agent, curl
    return urlparse(origin).netloc == request.url.netloc


class LoopbackHostOnly(BaseHTTPMiddleware):
    """Refuse any request whose ``Host`` header does not name loopback.

    This is what actually stops DNS rebinding — ``SameOriginOnly`` compares
    Origin against Host, and a rebound page controls both sides of that
    comparison equally, so it always passes. Checking Host against a fixed
    allowlist instead gives the attacker nothing to spoof it with: they choose
    what domain resolves to 127.0.0.1, not what this middleware accepts.

    Unlike ``SameOriginOnly`` this covers every method, GET and HEAD included.
    A rebound page silently reading the inbox — batches "may hold real client
    data" — is the primary threat here, and an unauthenticated GET is enough
    to carry it out. "Safe" methods are not safe against a same-origin read.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        """Reject a non-loopback Host before it reaches anything else."""
        if request.url.hostname not in LOOPBACK_HOSTNAMES:
            return JSONResponse(
                status_code=421,
                content={
                    "detail": "this daemon only answers to a loopback Host header. "
                    "Use the guide CLI, or the page served by this daemon."
                },
                headers=_SECURITY_HEADERS,
            )
        return await call_next(request)  # type: ignore[operator]


def create_app(store: Store | None = None) -> FastAPI:
    """Build the daemon application.

    Args:
        store: The batch store. Tests pass one rooted in a temp directory;
            production leaves it to default to ``~/.guide``.
    """
    app = FastAPI(
        title="GUIde",
        description="A local inbox for the questions your agents need answered.",
        docs_url=None,
        redoc_url=None,
    )
    app.state.daemon = Daemon(store)
    app.state.request_shutdown = _request_shutdown

    # Starlette wraps outward-in from the last one added, so SameOriginOnly is
    # the outer layer and its 403 never passes through SecurityHeaders — which is
    # why that rejection attaches the headers itself. LoopbackHostOnly goes on
    # last of all, making it the true outermost layer: a rebound Host should
    # never even reach the Origin check, since Origin is derived from the same
    # attacker-controlled request that SameOriginOnly alone would trust. It
    # attaches the headers itself for the same reason SameOriginOnly does.
    app.add_middleware(SecurityHeaders)
    app.add_middleware(SameOriginOnly)
    app.add_middleware(LoopbackHostOnly)
    app.include_router(router)
    app.include_router(skill_router)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, bool]:
        """A body-free liveness check for anything that would rather not parse."""
        return {"ok": True}

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        """Serve the icon explicitly so the page makes no request that 404s."""
        return FileResponse(WEB_DIR / "favicon.svg", media_type="image/svg+xml")

    # Mounted last so every API path is matched before the page is considered.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def _request_shutdown() -> None:
    """Ask this process to stop, the way a terminal would.

    ``SIGTERM`` to ourselves rather than a handle on the uvicorn server, so
    ``guide stop`` works identically whether the daemon was started in the
    background by a push, in the foreground by ``guide serve``, or by some
    future supervisor.
    """
    os.kill(os.getpid(), signal.SIGTERM)
