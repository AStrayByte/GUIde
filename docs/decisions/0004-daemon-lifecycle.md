# ADR 0004 — Daemon lifecycle: the port bind is the lock

**Status:** accepted
**Date:** 2026-08-31
**Implements:** ADR 0002 · closes open question 3

## Context

ADR 0002 settled that there is one long-lived daemon with a global inbox, and
named the lifecycle as the part with real concurrency in it. This is that part,
written down.

The hazards, all of them real:

- Two `guide push` calls in the same second both find no daemon and both start
  one.
- Port 7777 is already taken by something that is not GUIde.
- `~/.guide/daemon.json` outlives the process that wrote it.
- A session is blocked in `guide wait` when the daemon is restarted or killed.

## Decision

### On-demand start, with a notice

Any command that needs the daemon calls `ensure_running()`, which starts one if
there isn't one and prints a single line to **stderr** when it does:

```
  started the guide daemon on http://127.0.0.1:7777
```

Starting a background process the user never asked for is convenient and
slightly rude. Saying so once, on stderr so it never pollutes piped JSON, makes
it only convenient. `guide stop` and `guide status` exist for the rest.

### The port bind is the lock

Two racing pushes both spawn a daemon; both children try to `bind()` 7777; one
wins. There is no lockfile because there does not need to be one — the kernel
already provides exactly one atomic winner.

**The loser must not scan upward.** This is the subtlety that makes the whole
thing work, and getting it wrong is how you end up with two daemons, two
inboxes, and a coin flip over which one a push reaches. So on `EADDRINUSE` the
loser asks _what is there_:

| What answers on the port           | What the starting daemon does           |
| ---------------------------------- | --------------------------------------- |
| `GET /api/v0/meta` → `name: guide` | It lost the race. Exit quietly, exit 0. |
| Anything else, or nothing          | Some other program. Try the next port.  |

Scanning runs from 7777 to 7796. `guide serve --port N` is honoured exactly or
fails — silently landing somewhere the user did not ask for is worse than an
error.

`SO_REUSEADDR` is deliberately **not** set. It would let a second daemon bind
alongside a lingering socket, and the refused bind is precisely the signal this
design runs on.

### Discovery is a file plus a probe, never a file alone

`~/.guide/daemon.json` records `{url, port, pid, version, started_at}`. It is a
_hint about where to look_; the answer always comes from a live probe. A stale
file from a crashed daemon costs one refused connection.

`discover()` tries the recorded URL and then the whole scan range. The scan
matters for one specific hole: if 7777 belongs to something else and the daemon
landed on 7778 with no usable `daemon.json`, a push that only checked 7777 would
conclude "nothing running", spawn a daemon that immediately discovers it lost
the race, and then wait forever for a URL nobody wrote down. Twenty probes to
closed loopback ports are refused instantly, so the scan is free.

### `guide wait` watches the file, not the daemon

`wait` never opens a socket. It polls `~/.guide/batches/<id>/answers.json` every
250ms and returns when `complete` is `true`. So a waiting session survives a
daemon restart, a `guide stop`, or a crash — and because answers are written
continuously and atomically (ADR 0002), whatever is on disk when it wakes is
complete and valid.

That is a small, deliberate redundancy, and it is the difference between "your
review is still there" and "start again".

An unqualified `guide wait` resolves to _this session's_ most recent unfinished
batch, matched on `source.session_id` when there is one and on `source.cwd`
otherwise. With several sessions in one inbox, "the newest batch" is the wrong
default: it could easily be someone else's.

### Stopping

`guide stop` posts to `/api/v0/shutdown`, which returns `202` and _then_ sends
itself `SIGTERM` from a background task, so the client gets a clean answer
rather than a dropped connection. A signal rather than a handle on the uvicorn
server means the same path works however the daemon was started. If the daemon
is recorded but not answering, `stop` falls back to signalling the recorded pid.

## Consequences

- `serve()` binds the socket itself and hands it to uvicorn, rather than letting
  uvicorn open its own. This is the only way to make the bind the lock.
- The daemon runs in its own process group (`start_new_session=True`), so
  closing the terminal — or the Claude session — that pushed does not take the
  inbox down. That is the entire point of a daemon here.
- Background output goes to `~/.guide/daemon.log`. Every "the daemon did not
  come up" message points at it.
- `guide clean` deletes through the daemon rather than off disk, so removal is
  serialised with writes like everything else.

## Alternatives rejected

- **A lockfile.** More state, more staleness, and strictly worse than the bind
  it would be guarding.
- **A fixed port with no fallback.** One occupied port would make the tool
  unusable with no way out.
- **`wait` subscribing to SSE.** It would then depend on the daemon staying up
  for the entire time a human takes to answer 200 cards — the one thing this
  design is trying not to depend on.
