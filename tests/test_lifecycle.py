"""Pins the daemon lifecycle contract: discovery, the port-bind-as-lock race, start-up, stop."""

from __future__ import annotations

import contextlib
import errno
import os
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from guide import API_PREFIX
from guide.daemon import lifecycle
from guide.daemon.lifecycle import AlreadyRunning, DaemonInfo, DaemonUnreachable
from guide.errors import GuideError

# -- Small local test doubles ---------------------------------------------


class _Response:
    """A stand-in for ``httpx.Response``, just enough for ``probe()`` to use."""

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _UnparsableResponse:
    """A response whose body is not JSON at all."""

    def json(self) -> object:
        raise ValueError("not json")


def _free_port() -> int:
    """A loopback port nothing is listening on right now."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as finder:
        finder.bind((lifecycle.HOST, 0))
        return finder.getsockname()[1]


@contextlib.contextmanager
def _occupy_port() -> Iterator[int]:
    """Hold a free loopback port with a plain, non-HTTP socket for the block."""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind((lifecycle.HOST, 0))
    holder.listen(1)
    try:
        yield holder.getsockname()[1]
    finally:
        holder.close()


def _make_info(**overrides: object) -> DaemonInfo:
    defaults = {
        "url": "http://127.0.0.1:7777",
        "port": 7777,
        "pid": os.getpid(),
        "version": "0.1.0",
        "started_at": "2026-08-31T00:00:00+00:00",
    }
    defaults.update(overrides)
    return DaemonInfo(**defaults)  # type: ignore[arg-type]


# -- The discovery file -----------------------------------------------------


def test_read_info_returns_none_for_a_missing_file(guide_home: Path) -> None:
    assert lifecycle.read_info() is None


def test_read_info_returns_none_for_malformed_json(guide_home: Path) -> None:
    lifecycle.daemon_file().write_text("not json at all", encoding="utf-8")
    assert lifecycle.read_info() is None


def test_read_info_returns_none_when_required_keys_are_missing(guide_home: Path) -> None:
    lifecycle.daemon_file().write_text('{"url": "http://x", "port": 1}', encoding="utf-8")
    assert lifecycle.read_info() is None


def test_read_info_parses_a_well_formed_file(guide_home: Path) -> None:
    info = _make_info()
    lifecycle._write_info(info)
    assert lifecycle.read_info() == info


def test_write_info_then_read_info_round_trips(guide_home: Path) -> None:
    info = _make_info(url="http://127.0.0.1:7781", port=7781, pid=4242)
    lifecycle._write_info(info)
    assert lifecycle.read_info() == info


def test_clear_info_removes_the_file_when_it_names_the_current_process(
    guide_home: Path,
) -> None:
    lifecycle._write_info(_make_info(pid=os.getpid()))
    lifecycle._clear_info()
    assert not lifecycle.daemon_file().exists()


def test_clear_info_removes_the_file_when_the_named_pid_no_longer_exists(
    guide_home: Path,
) -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()  # fully reaped: the pid is now free

    lifecycle._write_info(_make_info(pid=proc.pid))
    lifecycle._clear_info()

    assert not lifecycle.daemon_file().exists()


def test_clear_info_keeps_the_file_when_the_named_pid_is_a_live_foreign_process(
    guide_home: Path,
) -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        lifecycle._write_info(_make_info(pid=proc.pid))
        lifecycle._clear_info()
        assert lifecycle.daemon_file().exists()
    finally:
        proc.terminate()
        proc.wait()


# -- probe() -----------------------------------------------------------------


def test_probe_returns_the_payload_when_a_guide_daemon_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"name": "guide", "version": "0.1.0"}
    monkeypatch.setattr(lifecycle.httpx, "get", lambda *a, **k: _Response(payload))
    assert lifecycle.probe("http://127.0.0.1:7777") == payload


def test_probe_returns_none_when_something_else_entirely_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"name": "some-other-app"}
    monkeypatch.setattr(lifecycle.httpx, "get", lambda *a, **k: _Response(payload))
    assert lifecycle.probe("http://127.0.0.1:7777") is None


def test_probe_returns_none_for_a_non_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle.httpx, "get", lambda *a, **k: _UnparsableResponse())
    assert lifecycle.probe("http://127.0.0.1:7777") is None


def test_probe_returns_none_when_the_connection_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(lifecycle.httpx, "get", fake_get)
    assert lifecycle.probe("http://127.0.0.1:7777") is None


class _StillStarting:
    """A stand-in for a spawned daemon that has not exited."""

    returncode = None

    def poll(self) -> None:
        """Still running."""
        return None


# -- discover() ---------------------------------------------------------------


def test_discover_returns_the_recorded_url_when_it_answers(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "http://127.0.0.1:19001"
    lifecycle._write_info(_make_info(url=url, port=19001))
    monkeypatch.setattr(lifecycle, "DEFAULT_PORT", 19100)
    monkeypatch.setattr(lifecycle, "PORT_SCAN_LIMIT", 2)

    calls: list[str] = []

    def fake_get(target_url: str, **kwargs: object) -> _Response:
        calls.append(target_url)
        if target_url.startswith(url):
            return _Response({"name": "guide", "home": str(guide_home)})
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(lifecycle.httpx, "get", fake_get)

    assert lifecycle.discover() == url
    assert calls[0].startswith(url)


def test_discover_falls_through_to_the_scan_range_when_the_recorded_url_is_dead(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lifecycle, "DEFAULT_PORT", 19000)
    monkeypatch.setattr(lifecycle, "PORT_SCAN_LIMIT", 5)
    live_url = "http://127.0.0.1:19002"
    lifecycle._write_info(_make_info(url="http://127.0.0.1:19999", port=19999))

    def fake_get(target_url: str, **kwargs: object) -> httpx.Response:
        if target_url.startswith(live_url):
            return _Response({"name": "guide", "home": str(guide_home)})
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(lifecycle.httpx, "get", fake_get)

    assert lifecycle.discover() == live_url


def test_discover_returns_none_when_nothing_answers_anywhere(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lifecycle, "DEFAULT_PORT", 19000)
    monkeypatch.setattr(lifecycle, "PORT_SCAN_LIMIT", 3)

    def fake_get(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(lifecycle.httpx, "get", fake_get)
    assert lifecycle.discover() is None


def test_discover_does_not_probe_the_same_url_twice(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lifecycle, "DEFAULT_PORT", 19000)
    monkeypatch.setattr(lifecycle, "PORT_SCAN_LIMIT", 3)
    # The recorded URL duplicates one that the scan range would try anyway.
    lifecycle._write_info(_make_info(url="http://127.0.0.1:19001", port=19001))

    calls: list[str] = []

    def fake_get(target_url: str, **kwargs: object) -> None:
        calls.append(target_url)
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(lifecycle.httpx, "get", fake_get)

    assert lifecycle.discover() is None
    assert len(calls) == len(set(calls)) == 3  # 19000, 19001, 19002 - probed once each


# -- _bind_one(): the loser of the race must not scan upward -----------------


def test_bind_one_on_a_free_port_returns_a_listening_socket_on_loopback() -> None:
    port = _free_port()
    listener = lifecycle._bind_one(port)
    try:
        assert listener.getsockname() == (lifecycle.HOST, port)
        probe_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with contextlib.closing(probe_sock):
            probe_sock.settimeout(1)
            probe_sock.connect((lifecycle.HOST, port))  # does not raise: it is listening
    finally:
        listener.close()


def test_bind_one_raises_oserror_when_a_non_guide_process_holds_the_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Nothing GUIde-shaped answers there, so this must not be mistaken for a race loss.
    monkeypatch.setattr(lifecycle, "probe", lambda url, timeout=lifecycle._PROBE_TIMEOUT: None)

    with _occupy_port() as port, pytest.raises(OSError) as exc_info:
        lifecycle._bind_one(port)

    assert exc_info.value.errno == errno.EADDRINUSE
    assert not isinstance(exc_info.value, AlreadyRunning)


def test_bind_one_raises_already_running_when_another_guide_daemon_holds_the_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lifecycle, "probe", lambda url, timeout=lifecycle._PROBE_TIMEOUT: {"name": "guide"}
    )

    with _occupy_port() as port, pytest.raises(AlreadyRunning) as exc_info:
        lifecycle._bind_one(port)

    assert exc_info.value.url == f"http://{lifecycle.HOST}:{port}"


# -- _bind(): the scan itself --------------------------------------------------


def test_bind_none_skips_a_port_held_by_a_non_guide_process_and_scans_upward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "_who_holds", lambda port, attempts=1: False)
    attempted_ports: list[int] = []
    real_bind_one = lifecycle._bind_one

    def spy_bind_one(port: int, **kwargs: object) -> socket.socket:
        attempted_ports.append(port)
        return real_bind_one(port, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(lifecycle, "_bind_one", spy_bind_one)

    with _occupy_port() as occupied_port:
        monkeypatch.setattr(lifecycle, "DEFAULT_PORT", occupied_port)
        monkeypatch.setattr(lifecycle, "PORT_SCAN_LIMIT", 5)

        listener, port = lifecycle._bind(None)
        try:
            # The occupied port is tried first and then moved past. Asserting on
            # the *sequence* rather than on `occupied_port + 1` keeps this
            # deterministic: an unrelated process on the machine may hold the
            # next port too, and routing around that is the behaviour under test.
            assert attempted_ports[0] == occupied_port
            assert port != occupied_port
            assert port > occupied_port
        finally:
            listener.close()


def test_bind_none_propagates_already_running_instead_of_continuing_the_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ADR's central claim: the loser of the race must stop, not scan upward."""
    monkeypatch.setattr(
        lifecycle, "probe", lambda url, timeout=lifecycle._PROBE_TIMEOUT: {"name": "guide"}
    )
    attempted_ports: list[int] = []
    real_bind_one = lifecycle._bind_one

    def spy_bind_one(port: int, **kwargs: object) -> socket.socket:
        attempted_ports.append(port)
        return real_bind_one(port, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(lifecycle, "_bind_one", spy_bind_one)

    with _occupy_port() as occupied_port:
        monkeypatch.setattr(lifecycle, "DEFAULT_PORT", occupied_port)
        monkeypatch.setattr(lifecycle, "PORT_SCAN_LIMIT", 5)

        with pytest.raises(AlreadyRunning):
            lifecycle._bind(None)

    assert attempted_ports == [occupied_port]


def test_bind_explicit_port_on_an_occupied_non_guide_port_raises_rather_than_scanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "_who_holds", lambda port, attempts=1: False)

    with _occupy_port() as occupied_port, pytest.raises(GuideError) as exc_info:
        lifecycle._bind(occupied_port)

    # A named port is honoured or it fails, and it fails readably — never as a
    # traceback, and never by silently landing somewhere else.
    assert str(occupied_port) in str(exc_info.value)
    assert "--port" in str(exc_info.value)


# -- ensure_running() ----------------------------------------------------------


def test_ensure_running_returns_the_existing_daemon_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "discover", lambda: "http://127.0.0.1:7777")
    spawned = False

    def fake_spawn() -> None:
        nonlocal spawned
        spawned = True

    monkeypatch.setattr(lifecycle, "_spawn", fake_spawn)

    result = lifecycle.ensure_running()

    assert result == ("http://127.0.0.1:7777", False)
    assert spawned is False


def test_ensure_running_spawns_and_returns_the_url_once_the_new_daemon_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([None, "http://127.0.0.1:7778"])
    monkeypatch.setattr(lifecycle, "discover", lambda: next(responses))
    monkeypatch.setattr(lifecycle, "_STARTUP_POLL", 0.01)
    spawned = False

    def fake_spawn() -> None:
        nonlocal spawned
        spawned = True

    monkeypatch.setattr(lifecycle, "_spawn", fake_spawn)

    result = lifecycle.ensure_running()

    assert result == ("http://127.0.0.1:7778", True)
    assert spawned is True


def test_ensure_running_raises_daemon_unreachable_naming_the_log_file(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lifecycle, "discover", lambda: None)
    monkeypatch.setattr(lifecycle, "_spawn", _StillStarting)
    monkeypatch.setattr(lifecycle, "_STARTUP_TIMEOUT", 0.05)
    monkeypatch.setattr(lifecycle, "_STARTUP_POLL", 0.01)

    with pytest.raises(DaemonUnreachable) as exc_info:
        lifecycle.ensure_running()

    assert str(lifecycle.log_file()) in str(exc_info.value)


# -- stop() ---------------------------------------------------------------------


def test_stop_with_no_daemon_and_no_info_file_returns_none(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lifecycle, "discover", lambda: None)
    assert lifecycle.stop() is None


def test_stop_posts_shutdown_waits_for_quiet_and_clears_the_file(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "http://127.0.0.1:7777"
    lifecycle._write_info(_make_info(url=url, port=7777, pid=os.getpid()))
    monkeypatch.setattr(lifecycle, "discover", lambda: url)

    posted: dict[str, object] = {}

    def fake_post(target_url: str, timeout: float | None = None) -> None:
        posted["url"] = target_url

    monkeypatch.setattr(lifecycle.httpx, "post", fake_post)
    # The daemon has already gone quiet by the time we check.
    monkeypatch.setattr(lifecycle, "probe", lambda u, timeout=lifecycle._PROBE_TIMEOUT: None)

    result = lifecycle.stop()

    assert result == url
    assert posted["url"] == f"{url}{API_PREFIX}/shutdown"
    assert not lifecycle.daemon_file().exists()


def test_stop_tolerates_the_daemon_dying_before_it_answers_the_shutdown_post(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "http://127.0.0.1:7777"
    lifecycle._write_info(_make_info(url=url, port=7777, pid=os.getpid()))
    monkeypatch.setattr(lifecycle, "discover", lambda: url)

    def fake_post(target_url: str, timeout: float | None = None) -> None:
        raise httpx.ConnectError("connection reset")

    monkeypatch.setattr(lifecycle.httpx, "post", fake_post)
    monkeypatch.setattr(lifecycle, "probe", lambda u, timeout=lifecycle._PROBE_TIMEOUT: None)

    assert lifecycle.stop() == url


def test_stop_signals_the_recorded_pid_when_discover_finds_nothing(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "http://127.0.0.1:7777"
    lifecycle._write_info(_make_info(url=url, port=7777, pid=424242))
    monkeypatch.setattr(lifecycle, "discover", lambda: None)

    killed: dict[str, object] = {}

    def fake_kill(pid: int, sig: int) -> None:
        killed["pid"] = pid
        killed["sig"] = sig

    # Alive until it is signalled, then gone — stop() waits for that transition
    # before reporting, so the test has to model it.
    monkeypatch.setattr(lifecycle, "_pid_alive", lambda pid: "pid" not in killed)
    monkeypatch.setattr(lifecycle.os, "kill", fake_kill)

    result = lifecycle.stop()

    assert result == url
    assert killed == {"pid": 424242, "sig": signal.SIGTERM}
    assert not lifecycle.daemon_file().exists()


def test_stop_refuses_to_claim_success_when_the_process_ignores_sigterm(
    guide_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wedged daemon still holds the port; saying "stopped" would send the next
    push scanning upward, and two daemons is the one outcome ADR 0004 forbids."""
    lifecycle._write_info(_make_info(url="http://127.0.0.1:7777", port=7777, pid=424242))
    monkeypatch.setattr(lifecycle, "discover", lambda: None)
    monkeypatch.setattr(lifecycle, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(lifecycle.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(lifecycle, "_STOP_TIMEOUT", 0.05)
    monkeypatch.setattr(lifecycle, "_STARTUP_POLL", 0.01)

    with pytest.raises(GuideError, match="still running"):
        lifecycle.stop()
