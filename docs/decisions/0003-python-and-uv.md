# ADR 0003 — Python, three dependencies, installed with uv

**Status:** accepted
**Date:** 2026-08-31
**Closes:** open question ★1

## Context

Everything downstream — the daemon's process model, the install story, who can
fix it at 11pm — hangs off the language. `docs/open-questions.md` left it open
and leaned Node, chiefly because `npx guide push …` means a new user installs
nothing at all.

Three options were scored against stated priorities in a decision-aid page
(since retired to `.superseded/architecture-options.html`, this ADR being what
it was for): a Python daemon with a vanilla page, a Node daemon with a vanilla
page, and Django + React.

## Decision

**Python 3.11+, with `fastapi` + `uvicorn` + `httpx` and nothing else.**
Distributed as `uv tool install guide-cli`. The front end stays vanilla, with no
build step, in either case — that half was settled by evidence rather than
argument (see ADR 0007).

Django + React was never close: it wants a database, and the design says
explicitly that answers are files and not a results database.

## Why

1. **The maintainer is the deciding factor.** All three options clear every hard
   constraint — browser UI, runs on a Mac, reads and writes local files. The
   constraints do not separate them. What separates them is which codebase can
   be read fluently when something breaks, and that is Python.

2. **Zero-install is a distribution win; maintainability is a daily one.** `npx`
   genuinely is the best install story here, and pretending otherwise would be
   dishonest. But this tool has roughly one user and will be edited far more
   often than it is installed.

3. **Pydantic pays for the framework.** The schema is the asset (ADR 0001), and
   FastAPI gives request validation, typed handlers and `StreamingResponse` for
   SSE in a few lines. Ajv would have to be chosen and wired by hand.

4. **`uv` closed the gap that made Python the awkward answer.** A single static
   binary, a project lockfile, and a managed interpreter that never touches the
   system Python or an existing pyenv. `uv tool install guide-cli` is one
   command, and `uvx guide` runs it without installing at all — which is most of
   what `npx` was buying.

## The dependency budget

Three, and each has to justify itself:

| Dependency | Why not stdlib                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| `fastapi`  | Routing, body validation and SSE. `http.server` is not a long-lived daemon.                                            |
| `uvicorn`  | The actual server. Also the only clean way to hand it a socket we bound ourselves, which ADR 0004 depends on entirely. |
| `httpx`    | One HTTP client for the CLI, shared with FastAPI's own test client.                                                    |

Things deliberately **not** taken as dependencies:

- **A ULID library** — the encoder is twenty lines of fully specified arithmetic
  (`src/guide/ulid.py`), pinned against the spec's vectors in the tests.
- **`watchfiles`** — nothing needs to watch a directory. `guide wait` polls one
  file's contents every 250ms, which at human answering speed is free.
- **A CLI framework** — `argparse` covers eight subcommands without ceremony.
- **`python-ulid`, `click`, `rich`, `pydantic-settings`** — decoration, not
  capability.

## Consequences

- A new user needs `uv`, or a Python 3.11+ they are willing to install into.
  That is the price paid, stated plainly.
- Two languages in one repo: a Python daemon and a JavaScript page. The seam is
  the HTTP surface, and it is small.
- The version gate is implemented twice — once in `versioning.py`, once in
  `render.js`, because a batch opened over `file://` has no daemon to ask.
  `tests/fixtures/version_compat.json` is the shared truth table both are
  written against, but **only the Python side executes it**: there is no
  JavaScript test runner in this repo (ADR 0007), so the browser copy is checked
  by reading it and by an out-of-tree jsdom pass before release. That is the real
  cost of the split. It is bounded at about ten lines, and it is the first thing
  a JS harness should cover if one ever arrives.
- Cold start is ~300ms rather than Node's ~80ms. Irrelevant for a process you
  start once and leave running for days.

## Revisit if

- Someone other than the author starts installing this regularly, and `uv` turns
  out to be the friction. `uvx guide` is the first answer; a published binary is
  the second.
- The daemon ever needs to be embedded in something that is already Node.
