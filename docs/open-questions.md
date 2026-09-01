# Open questions

Decisions not yet made — and, below the line, the ones that are.

Phase 1 is built, so most of this list is now history. What is left is genuinely
open.

**Settled** (2026-08-31):

- Single-user, run locally. No hosting, no accounts, no sharing model — each person
  installs their own copy. This deleted most of what was open.
- A page driven by files, not a chat UI. [ADR 0001](decisions/0001-page-over-chat-ui.md).
- Field types for v0.1: `choice` + comment, A/B `compare`, `rating`. `rank` dropped.
- Many concurrent agent sessions, one daemon, one inbox.
  [ADR 0002](decisions/0002-daemon-with-an-inbox.md).
- `guide_version` is `major.minor.patch`, declared first, checked before parsing.
  [versioning.md](versioning.md).
- Python, three dependencies, installed with `uv`.
  [ADR 0003](decisions/0003-python-and-uv.md). **Closes ★1.**
- Daemon lifecycle: the port bind is the lock, on-demand start with a notice,
  `wait` watches the file. [ADR 0004](decisions/0004-daemon-lifecycle.md).
  **Closes 3.**
- SSE over polling, and a versioned `/api/v0`.
  [ADR 0005](decisions/0005-http-surface-and-sse.md). **Closes 2.**
- The `markdown` block stays, safe by construction, behind a CSP.
  [ADR 0006](decisions/0006-markdown-by-construction.md).
- No build step; classic scripts so `file://` keeps working.
  [ADR 0007](decisions/0007-no-build-step.md).

---

## ~~★ 1. What language does it ship in?~~ — settled

**Python**, with `fastapi` + `uvicorn` + `httpx` and nothing else, installed
with `uv tool install guide-cli`. The reasoning, including an honest accounting
of what choosing it over `npx` costs, is
[ADR 0003](decisions/0003-python-and-uv.md).

## ~~2. How does the page find out a new batch arrived?~~ — settled

**SSE.** Not because of scale — polling really would have been fine — but
because `EventSource` reconnects on its own, so "the daemon restarted" costs
zero lines. [ADR 0005](decisions/0005-http-surface-and-sse.md).

## ~~3. Does the daemon auto-start, or is that too magical?~~ — settled

**Auto-start, with a one-line notice on stderr**, plus `guide stop` and
`guide status`. [ADR 0004](decisions/0004-daemon-lifecycle.md).

## 4. Notifications when you're not looking at the browser

Three sessions can queue up questions while you're in a terminal. Worth a macOS
notification on the first arrival? A menu-bar count? Or is the browser tab enough?

Probably nothing in Phase 1, but the daemon makes it trivially possible later, so don't
design it out.

## ~~5. Batch lifecycle and cleanup~~ — settled

N is **7 days**, and `guide clean` **deletes** by default, because batches may hold
client data and the safe default for data nobody asked to keep is not keeping it.
`--archive` moves to `~/.guide/archive/` instead; `--days` and `--all` override the
selection; `--yes` skips the prompt. Removal goes through the daemon so it is
serialised with writes like everything else.

## ~~6. Should there be a Done button at all?~~ — settled

Yes: exactly one, at the bottom, disabled until every answerable card is answered.
It flips `complete: true`, which is the single thing `guide wait` blocks on.
`POST /api/v0/batches/{id}/complete` also takes `{"complete": false}`, so it is
undoable — nothing in this design should be a one-way door.

## 7. Repo name

`GUIde` is good — GUI + guide. The case is load-bearing and GitHub URLs are
case-insensitive, so it'll read as `guide` in places. Fine. Alternatives if it grates:
`deckhand`, `askhuman`, `verdict`.

## 8. Public repo or private?

The code has no secrets and nothing sensitive is committed — batches live in `~/.guide/`
now, outside every working tree, so there's nothing to leak. Public is fine and makes
`npx` publishing trivial.

## 9. What's the second batch?

The format is only proven when a _different_ review runs through it. Candidates:
regression-bench case triage, peer-review finding triage, prompt A/B eval. The one
you'd actually run next tells us whether the block vocabulary is right — and it's
cheaper to find out before the renderer exists than after.

## 10. Reopening answers

If Claude acts on the answers and then you change your mind on card 7 — is there a
revision model, or do you just re-run the batch? Leaning **re-run**. Versioning answer
sets is a lot of machinery for a rare case.
