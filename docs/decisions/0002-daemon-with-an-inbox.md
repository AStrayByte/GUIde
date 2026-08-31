# ADR 0002 — One daemon with a global inbox

**Status:** proposed
**Date:** 2026-08-31

## Context

The original sketch was a process per batch: `guide ./questions.json` serves one file,
you answer it, it exits. Clean and small.

Then the requirement arrived: **several Claude Code sessions running at once**, in
different repos, each able to have questions waiting. A process per batch breaks
immediately — three sessions means three servers fighting over a port, three browser
tabs, and no way to see what's waiting overall.

## Decision

One long-lived daemon, started on demand, with a global batch store at `~/.guide/` and
an inbox UI listing everything waiting across all sessions.

Any `guide push` starts the daemon if it isn't running and attaches if it is. The user
never starts a server manually.

## Why

1. **The inbox is the actual feature.** With several agents working, the question isn't
   "render this file", it's "what needs me right now?" That's a queue, and a queue needs
   something persistent to live in.

2. **The daemon outlives the sessions.** Close a Claude session mid-review and the
   questions are still there. With a process per batch, killing the session that spawned
   the server loses the work.

3. **Global storage is safer than per-repo.** `~/.guide/` sits outside every working
   tree, so a batch containing client data cannot be accidentally committed. That's a
   structural guarantee, not a `.gitignore` line someone might not copy into the next
   repo.

4. **One writer removes a class of bugs.** The daemon is the only process writing
   answers files, so concurrent sessions can't interleave writes.

5. **It makes per-card "ask about this" tractable.** The daemon already knows which
   session owns which batch, so routing a question from card 42 back to the right Claude
   is bookkeeping it's already doing.

## Consequences

- **Phase 1 grows.** It's no longer "render a file" — it's a daemon, a store, an inbox
  rail, and push/wait CLI verbs. Still small, but roughly double what a single-file
  viewer would have been.
- **Lifecycle to get right:** on-demand start, port fallback, the start-up race between
  two simultaneous pushes (the port bind _is_ the lock — the loser retries as a client),
  and a discoverable `~/.guide/daemon.json` so the CLI can find a daemon on a
  non-default port.
- **`guide wait` watches the answers file, not the daemon.** So a waiting session
  survives a daemon restart. This is worth the small redundancy.
- **Batches accumulate.** Needs an age-out for answered batches and a `guide clean`.
- **The single-file path survives** as a degenerate case: the front-end still opens over
  `file://` against one batch with `localStorage`, for when you don't want a process at
  all.

## Alternatives rejected

- **A process per batch, multiplexed by port.** Users would have to track which port is
  which review. No.
- **No daemon; the page reads a folder directly over `file://`.** Browsers can't watch a
  directory or write files back. Kills continuous answer-saving, which is the feature
  that removes the handoff.
- **Per-repo `.guide/` stores.** Splits the inbox by repo, which defeats the point when
  the whole problem is _several repos at once_.
