"""Starting, finding and stopping the daemon.

The only part of GUIde with real concurrency in it, so the rules are written
down rather than implied.

**The port bind is the lock.** Two ``guide push`` calls in the same second both
decide no daemon is running and both spawn one. They race to bind 7777; one
wins. There is no lockfile, because there does not need to be one.

**The loser must not scan upward.** This is the subtlety. Scanning up on
``EADDRINUSE`` is right when something *else* holds the port, and catastrophic
when another GUIde daemon does — you would end up with two daemons, two inboxes
and a coin flip over which one a push reaches. So on a refused bind we ask what
is there: a GUIde daemon means we lost the race and exit quietly; anything else
means we try the next port.

**Discovery is a file plus a probe, never a file alone.** ``~/.guide/daemon.json``
can outlive the process that wrote it. It is a hint about where to look; the
answer always comes from ``GET /api/v0/meta``.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import httpx
import uvicorn

from guide import API_PREFIX, __version__
from guide.errors import DaemonUnreachable, GuideError
from guide.paths import daemon_file, ensure_home, home, log_file
from guide.store import Store, utc_now_iso

from .app import create_app

HOST = "127.0.0.1"
"""Loopback, never ``0.0.0.0``.

There is still no per-request auth token — but "no one else here" turned out
to be qualified: a page served from a domain that resolves to 127.0.0.1 (DNS
rebinding) is on this socket too, from the browser's point of view. What
actually stands in for auth is ``LoopbackHostOnly`` in ``daemon/app.py``,
which checks the Host header a rebound request cannot spoof its way around.
"""

DEFAULT_PORT = 7777
PORT_SCAN_LIMIT = 20

_PROBE_TIMEOUT = 0.75
_STARTUP_TIMEOUT = 15.0
_STARTUP_POLL = 0.1
_STOP_TIMEOUT = 5.0

_RACE_PROBE_ATTEMPTS = 3
"""How many times to ask who holds a *contested* port before concluding "not GUIde".

The loser of a start-up race probes the winner in the window between its
``bind()`` and the moment uvicorn answers — measured at about 40ms against a
750ms budget, so a single probe is nearly always enough. Nearly is the wrong word
for a decision whose wrong branch produces two daemons and two inboxes, so the
contested port is asked three times.

Only the contested one. Retrying every port in the scan would multiply 20 ports
by three timeouts, and a machine with a busy range would blow the start-up budget
before the daemon ever came up — turning a fixed race into a worse hang.
"""

_SCAN_PROBE_TIMEOUT = 0.25
"""Budget for the "is that GUIde?" question on a port we are merely passing.

A local daemon answers ``/meta`` in single-digit milliseconds, and a port held by
something that is not a web server refuses or hangs. Waiting the full probe
timeout on each of twenty of those is the difference between a slow start and a
failed one.
"""


class AlreadyRunning(GuideError):
    """Another daemon owns the port. Raised by the loser of a start-up race."""

    def __init__(self, url: str) -> None:
        """Record which daemon won the race, so the caller can report it."""
        super().__init__(f"a GUIde daemon is already running on {url}")
        self.url = url


@dataclass(frozen=True, slots=True)
class DaemonInfo:
    """What ``~/.guide/daemon.json`` records about a running daemon."""

    url: str
    port: int
    pid: int
    version: str
    started_at: str

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready form, derived from the fields rather than restated."""
        return asdict(self)


# -- Discovery ------------------------------------------------------------


def probe(
    url: str, timeout: float = _PROBE_TIMEOUT, *, serving: str | None = None
) -> dict[str, Any] | None:
    """Ask what is listening at ``url``.

    Args:
        url: the origin to ask.
        timeout: how long to wait for an answer.
        serving: a store root the daemon must be serving to count as ours. A
            daemon started under a different ``$GUIDE_HOME`` is a stranger with
            the same name: attaching to it would push a batch into someone
            else's inbox and then report nothing waiting. Pass ``None`` to accept
            any GUIde daemon, which is what a bare health check wants.

    Returns:
        The daemon's ``/meta`` payload, or ``None`` — for a timeout, a refused
        connection, something else entirely on the port, or the wrong store.
    """
    try:
        response = httpx.get(f"{url}{API_PREFIX}/meta", timeout=timeout)
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("name") != "guide":
        return None
    if serving is not None and payload.get("home") != serving:
        return None
    return payload


def read_info() -> DaemonInfo | None:
    """The recorded daemon, if the file exists and parses. Not proof it is alive."""
    try:
        raw = json.loads(daemon_file().read_text(encoding="utf-8"))
        return DaemonInfo(
            url=raw["url"],
            port=int(raw["port"]),
            pid=int(raw["pid"]),
            version=raw.get("version", "?"),
            started_at=raw.get("started_at", "?"),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def discover() -> str | None:
    """The URL of a daemon that is actually answering, or ``None``.

    The recorded URL is tried first, then the whole scan range. Scanning matters
    for the case where 7777 belongs to something else and the daemon landed on
    7778 with no usable ``daemon.json`` — without it, a push would conclude
    "nothing running", spawn a daemon that immediately discovers it lost the
    race, and then wait for a URL nobody ever wrote down.

    It costs nothing: a closed loopback port refuses the connection instantly.
    """
    ours = str(home())
    info = read_info()
    candidates = [info.url] if info else []
    candidates += [
        f"http://{HOST}:{port}" for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT)
    ]

    seen = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        if probe(url, serving=ours):
            return url
    return None


# -- Starting -------------------------------------------------------------


def ensure_running() -> tuple[str, bool]:
    """Return the URL of a live daemon, starting one if necessary.

    Returns:
        ``(url, started)`` — ``started`` is ``True`` if this call spawned it, so
        callers can print the one-line notice. Starting a background process the
        user did not ask for is convenient and slightly rude; saying so once
        makes it only convenient.

    Raises:
        DaemonUnreachable: nothing came up within the start-up timeout.
    """
    existing = discover()
    if existing:
        return existing, False

    child = _spawn()
    deadline = time.monotonic() + _STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        url = discover()
        if url:
            return url, True
        # A child that has already exited is never going to answer. Without this
        # a broken install costs fifteen seconds of silence before saying so.
        if child.poll() is not None:
            raise DaemonUnreachable(
                f"the daemon exited immediately (status {child.returncode}). "
                f"Run `guide serve` to see why, or read {log_file()}."
            )
        time.sleep(_STARTUP_POLL)

    raise DaemonUnreachable(
        f"the daemon did not come up within {_STARTUP_TIMEOUT:.0f}s. "
        f"Try `guide serve` in another terminal to see why, or read {log_file()}."
    )


def _spawn() -> subprocess.Popen[bytes]:
    """Launch a detached daemon whose output goes to ``~/.guide/daemon.log``.

    The handle is returned, not discarded: it is the only way the caller can tell
    "still starting" from "already dead".

    ``start_new_session`` puts it in its own process group, so closing the
    terminal that pushed — or the Claude session that pushed — does not take the
    inbox down with it. That is the whole point of a daemon here.
    """
    ensure_home()
    with log_file().open("a", encoding="utf-8") as log:
        log.write(f"\n--- starting guide {__version__} at {utc_now_iso()} ---\n")
        log.flush()
        # Fixed argv, no shell, nothing from user input.
        return subprocess.Popen(
            [sys.executable, "-m", "guide", "serve"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )


# -- Serving --------------------------------------------------------------


def serve(port: int | None = None, store: Store | None = None) -> None:
    """Run the daemon in the foreground until it is asked to stop.

    Args:
        port: An exact port to bind. Omit to take 7777 or the first free port
            above it. An explicit port is honoured or it fails — silently
            landing somewhere else is worse than a clear error.
        store: The batch store, for tests.

    Raises:
        AlreadyRunning: another daemon holds the port. Not an error at the
            command line, just news; ``guide serve`` reports it and exits 0.
    """
    # `_write_info`, below, routes its `daemon_file().parent` creation through
    # `paths.ensure_home()`, which reasserts 0700 unconditionally — including
    # on an install that predates that guarantee and already sits at the old
    # 0755 default. That covers every `serve` (foreground or spawned) without
    # a separate check here. This does not touch anything already written
    # under ~/.guide with the old, looser mode — see `store._write_json` and
    # the mkdir call sites for the per-file/per-batch story — but a 0700 home
    # is unreadable and untraversable by anyone else on the machine regardless
    # of what its children are still set to.
    listener, bound_port = _bind(port)
    url = f"http://{HOST}:{bound_port}"
    _write_info(
        DaemonInfo(
            url=url,
            port=bound_port,
            pid=os.getpid(),
            version=__version__,
            started_at=utc_now_iso(),
        )
    )
    try:
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(store),
                log_level="warning",
                access_log=False,
            )
        )
        # Hand uvicorn the socket we already bound rather than letting it open
        # its own. This is the load-bearing line of the whole design: the bind
        # is the lock, and reopening the port would release and retake it.
        server.run(sockets=[listener])
    finally:
        _clear_info()
        listener.close()


def _bind(preferred: int | None) -> tuple[socket.socket, int]:
    """Take a port, or work out who already has it.

    An explicit ``preferred`` is tried once. Otherwise the default port is tried
    and then scanned upward, because a port taken by an unrelated process is a
    thing to route around, not a thing to fail on.
    """
    if preferred is not None:
        # One port, so no scan to multiply: ask properly.
        try:
            return _bind_one(preferred, attempts=_RACE_PROBE_ATTEMPTS), preferred
        except OSError as exc:
            # An explicit port is honoured or it fails, and it fails in one line:
            # a traceback out of the CLI is a bug, not a user error.
            raise GuideError(
                f"port {preferred} is not available — {exc}. "
                f"Omit --port to take the first free port from {DEFAULT_PORT}."
            ) from exc

    for offset, port in enumerate(range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT)):
        try:
            # The race only ever happens on the first port: that is where two
            # simultaneous starts both begin. Everything above it is somebody
            # else's process, and gets one quick question.
            attempts = _RACE_PROBE_ATTEMPTS if offset == 0 else 1
            return _bind_one(port, attempts=attempts), port
        except OSError as exc:
            if exc.errno not in (errno.EADDRINUSE, errno.EACCES):
                raise GuideError(f"could not bind {HOST}:{port} — {exc}") from exc
    raise GuideError(
        f"no free port between {DEFAULT_PORT} and "
        f"{DEFAULT_PORT + PORT_SCAN_LIMIT - 1}. Pass --port to choose one."
    )


def _bind_one(port: int, *, attempts: int = 1) -> socket.socket:
    """Bind a single port, or explain who has it.

    Args:
        port: the port to take.
        attempts: how many times to ask who holds it if the bind is refused.
            More than one only where being wrong would produce two daemons.

    Raises:
        AlreadyRunning: a GUIde daemon answers there — we lost the race.
        OSError: the port is taken by something else, or unusable.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Deliberately no SO_REUSEADDR: on macOS and Linux it would let a second
    # daemon bind alongside a lingering socket, and the bind refusal is exactly
    # the signal this design depends on.
    try:
        listener.bind((HOST, port))
        listener.listen(128)
    except OSError as exc:
        listener.close()
        if exc.errno == errno.EADDRINUSE and _who_holds(port, attempts):
            raise AlreadyRunning(f"http://{HOST}:{port}") from exc
        raise
    return listener


def _who_holds(port: int, attempts: int = 1) -> bool:
    """Whether a GUIde daemon is what is occupying ``port``.

    Deliberately not filtered by store root: two daemons must never share a port
    whatever they happen to be serving.

    A single unanswered probe on a contested port would send us to the next one
    and leave two daemons running — the outcome ADR 0004 calls catastrophic — so
    the caller asks for more attempts there, and only there.
    """
    url = f"http://{HOST}:{port}"
    timeout = _PROBE_TIMEOUT if attempts > 1 else _SCAN_PROBE_TIMEOUT
    for attempt in range(attempts):
        if probe(url, timeout=timeout):
            return True
        if attempt + 1 < attempts:
            time.sleep(_STARTUP_POLL)
    return False


# -- Stopping -------------------------------------------------------------


def stop() -> str | None:
    """Stop the running daemon. Returns the URL it was on, or ``None``.

    Asks over HTTP first so the daemon shuts down cleanly, and falls back to a
    signal if the recorded process is alive but not answering.
    """
    info = read_info()
    url = discover()

    if url:
        # A daemon that dies before answering has still done what we asked.
        with contextlib.suppress(httpx.HTTPError):
            httpx.post(f"{url}{API_PREFIX}/shutdown", timeout=_PROBE_TIMEOUT)
        if not _wait_until(lambda: probe(url, timeout=0.2) is None):
            raise GuideError(f"the daemon on {url} did not stop. Kill it by hand.")
        _clear_info()
        return url

    if info and _pid_alive(info.pid):
        os.kill(info.pid, signal.SIGTERM)
        # Wait for it to actually go. Reporting "stopped" while a wedged daemon
        # still holds the port would send the next push scanning upward, and two
        # daemons is exactly what the port-as-lock design exists to prevent.
        if not _wait_until(lambda: not _pid_alive(info.pid)):
            raise GuideError(
                f"sent SIGTERM to pid {info.pid} but it is still running. "
                f"Kill it by hand, then run `guide status`."
            )
        _clear_info()
        return info.url

    _clear_info()
    return None


def _wait_until(gone: Callable[[], bool], timeout: float | None = None) -> bool:
    """Poll until ``gone()`` is true, so ``stop`` never reports what it did not verify.

    The default is read here rather than bound as a default argument, so a test
    can shorten it by patching the module constant — a default argument is
    evaluated once at import and would quietly ignore that.
    """
    deadline = time.monotonic() + (_STOP_TIMEOUT if timeout is None else timeout)
    while time.monotonic() < deadline:
        if gone():
            return True
        time.sleep(_STARTUP_POLL)
    return gone()


def _pid_alive(pid: int) -> bool:
    """Whether a process with this id exists and is ours to signal."""
    try:
        os.kill(pid, 0)
    except OSError:
        # ProcessLookupError (gone) and PermissionError (someone else's) are both
        # "not a daemon we can signal".
        return False
    return True


# -- The discovery file ---------------------------------------------------


def _write_info(info: DaemonInfo) -> None:
    """Record where this daemon is listening.

    ``daemon.json`` is discovery metadata, not batch content, but it is still
    written 0600 up front — same reasoning and same ``os.open`` mechanism as
    ``store._write_json``: ``Path.write_text`` has no mode argument, and a
    ``chmod`` after the write would leave the file briefly at the umask's
    default mode instead of never existing at anything but 0600.
    """
    ensure_home(daemon_file().parent)
    payload = json.dumps(info.as_dict(), indent=2) + "\n"
    descriptor = os.open(daemon_file(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    # The mode above only applies on create — an existing file (e.g. an upgrade
    # over an old install written 0644) keeps its old mode through O_TRUNC.
    # fchmod forces 0600 unconditionally regardless of whether it pre-existed.
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(payload)


def _clear_info() -> None:
    """Remove the discovery file, but only if it still describes this process."""
    info = read_info()
    if info is None or info.pid == os.getpid() or not _pid_alive(info.pid):
        daemon_file().unlink(missing_ok=True)
