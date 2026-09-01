# Architecture

This is the **product** architecture: what GUIde is, what the layers are, and what is
deliberately not built. For how it is actually implemented — module boundaries, the
daemon lifecycle, the HTTP surface, where a new file goes — read the
[engineering wiki](wiki/index.html), which opens straight from a clone.

## The one idea

**The UI is a pure function of a JSON file.**

```
render(batch)  -> a page of cards
collect(page)  -> answers
```

Nothing else here is load-bearing. The format, the daemon, the skill — all of it exists
to get a batch into that function and answers back out.

The corollary matters just as much: **the renderer never learns your domain.** It does
not know what a "verifier check" or a "regression case" is. Domain data rides along in
an opaque `meta` object that the renderer passes through untouched and echoes back in
the answers. That single rule is what stops GUIde from slowly becoming specific to any one project.

---

## What "single-user, local" buys us

This is a tool one person runs on their own machine for their own agents. Nobody
gets a link to your instance — they install GUIde and run their own.

That constraint deletes most of the hard parts:

| Doesn't exist                          | Because                                           |
| -------------------------------------- | ------------------------------------------------- |
| Accounts, auth, permissions            | Bound to `127.0.0.1`. The only user is you.       |
| A sharing model                        | Distribution is "install it", not "here's a URL". |
| Hosting, uptime, a database            | It's a local process with a filesystem.           |
| Encryption, unguessable IDs            | Nothing leaves the machine.                       |
| Multi-reviewer, merge, agreement views | One person answers.                               |
| Copy-paste as a permanent transport    | The daemon writes the answers file directly.      |

It also **upgrades** the design. A local process has a filesystem and sits on the same
machine as Claude Code, so the full loop — Claude asks, you answer, Claude reads —
works in **Phase 1**, not behind a hosted API later. There is no handoff step to
eliminate, because there never is one.

---

## Many Claude sessions, one inbox

You run several Claude Code sessions at once, across different repos. All of them can
have questions for you. So GUIde is **one long-lived daemon with an inbox**, not a
process per batch.

```
  Claude (search-api)  ─┐
  Claude (web-client)  ─┼─▶  guide daemon  ─▶  browser: an inbox of batches
  Claude (report-gen)  ─┘    127.0.0.1:7777     you work through them in any order
                                  │
                                  └──▶ ~/.guide/batches/<id>/answers.json ──▶ back to whichever session asked
```

### How it works

**One daemon, started on demand.** Any `guide push` starts it if it isn't running and
attaches if it is. You never think about starting a server. It survives every session
that pushed to it — close a Claude session mid-batch and the questions are still there.

**A global store, outside any repo:** `~/.guide/batches/<id>/{batch.json, answers.json}`.

Global rather than per-repo for two reasons. Sessions in different repos land in one
inbox, which is the whole point. And batches may hold real client data — keeping them
out of any working tree means they can never be accidentally committed, which is a
stronger guarantee than a `.gitignore` line.

**Every batch knows who asked.** `source.session_id`, `source.cwd`, `source.repo`. The
inbox groups by session so "the 17 verifier complaints" and "these 4 API doc questions"
don't blur together, and each session's `guide wait` only ever watches its own batch.

**Batch ids are ULIDs.** Two sessions pushing in the same millisecond can't collide,
and ids sort by creation time for free.

### The inbox

The UI grows a left rail. This is the main structural change from the single-file model:

```
┌──────────────────────────┬────────────────────────────────┐
│ Waiting                3 │  Verifier triage               │
│ ▸ Verifier triage        │  Was the checker right?        │
│   search-api · 17 cards  │                                │
│ ▸ Regression cases       │  ── card 4 of 17 ──────────    │
│   search-api · 8 cards   │  [ evidence ]                  │
│ ▸ API doc gaps           │  [ ✓ fine ] [ ✗ wrong ] [ ? ]  │
│   web-client · 4 cards   │                                │
├──────────────────────────┤                                │
│ Done                   7 │                                │
└──────────────────────────┴────────────────────────────────┘
```

A batch arriving while you're mid-answer on another shows a quiet toast and appears in
the rail. It never steals focus, never navigates you away. Interrupting someone at card
11 of 17 is how you get bad answers.

### Concurrency, honestly

The failure modes worth naming up front, because they're the ones that bite:

| Hazard                                    | Handling                                                                                                                   |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Two `guide push` race to start the daemon | Both try to bind; the loser gets `EADDRINUSE`, waits, connects to the winner. No lockfile needed — the port _is_ the lock. |
| Port 7777 taken by something else         | Scan upward, print the real URL. Write it to `~/.guide/daemon.json` so the CLI finds it.                                   |
| Concurrent writes to one answers file     | The daemon is the only writer. The browser sends changes; the daemon serializes them.                                      |
| Daemon dies mid-review                    | Answers are already on disk — writes are continuous. Restarting resumes exactly where you were.                            |
| `guide wait` outlives the daemon          | It watches the **answers file**, not the daemon. Works regardless of what the server is doing.                             |
| Stale batches piling up                   | Answered batches age out of the rail after N days; `guide clean` for the rest.                                             |

---

## The layers

Three. Each is independently useful; you can stop at any of them.

```
┌─ Layer 2   Live loop     the skill: push, wait, read; per-card "ask about this"
├─ Layer 1   The daemon    one local server, an inbox, a page, files on disk
└─ Layer 0   The format    batch.json + answers.json, versioned — the contract
```

### Layer 0 — The format

A versioned JSON shape for a batch and for an answer set. See [format.md](format.md)
for the shape and [versioning.md](versioning.md) for the compatibility contract.

This is the only thing that's expensive to change, so it gets the most thought and the
least code. It's also useful entirely on its own: with the format frozen and no UI at
all, Claude can still write batches — you'd be reading raw JSON, which is bad, but it
works.

### Layer 1 — The daemon (the MVP)

```
$ guide push ./questions.json
  daemon already running on http://127.0.0.1:7777
  pushed 01JQ8F… · 17 cards · 3 batches waiting
```

- serves the inbox and the cards
- **writes `answers.json` on every change** — no Save button, no lost work
- accepts pushes from any number of sessions
- tells every open page about a new batch over SSE

The front-end is a single page with no build step, so it also opens straight from
`file://` against one batch if you'd rather not run anything. The daemon is what makes
it good, not what makes it work. ([ADR 0007](decisions/0007-no-build-step.md) records
what keeping that property costs.)

`localStorage` still backs in-progress state as a belt-and-braces layer, but the file
on disk is the source of truth.

**This layer alone replaces everything the hand-built triage page did**, for any batch,
from any number of sessions, and closes the loop with Claude at the same time.

### Layer 2 — Live loop

A `guide` Claude Code skill, plus the small bit of daemon surface it needs:

- `/guide` — builds a batch from what's in context, pushes it, tells you it's waiting
- `/guide wait` — blocks until _its own_ batch is complete, then reads and summarizes
- **Per-card "ask about this"** — you're on card 42, you don't know what a column
  means, you type a question, and it reaches the session that created that batch,
  scoped to that card's evidence. The one piece of the chat-UI idea genuinely worth
  building, and cheap here because the daemon already knows which session owns which
  batch.

---

## The chat-UI question

The alternative you raised: instead of files, make GUIde a chat window where Claude
emits special syntax the UI decodes into live widgets inline.

**The idea underneath it is right and it's already the core of this design.** Claude
should emit structured blocks that a fixed renderer decodes — _not_ hand-write 120KB of
HTML per review. That's the whole point of Layer 0. The only question is where those
blocks land.

Building a chat window too would mean running inference yourself (an API key,
streaming, retries, history, token cost) to rebuild something you already have and
that's better: **Claude Code is your chat client.** It has your repo, your tools, your
context, your skills. The thing it's missing is a place to _render and collect_.

Running several sessions at once makes this sharper, not weaker. Three concurrent chats
would mean three chat windows to build and keep in sync. Three concurrent chats feeding
**one inbox** is the thing you actually want, and it's only expressible in the page
model.

Nothing here forecloses a chat surface. Same block vocabulary, same renderer — it'd be
a new front-end over the same parts. Recorded as
[ADR 0001](decisions/0001-page-over-chat-ui.md); the daemon and inbox as
[ADR 0002](decisions/0002-daemon-with-an-inbox.md).

---

## Data handling

Batches will contain real client data — the verifier triage one did, which is why that
file is gitignored.

The local-only model handles this by construction rather than by policy: nothing is
transmitted, because there's nothing to transmit to. The rules that remain:

- Bind to `127.0.0.1`, never `0.0.0.0`. Running it on your own server is an explicit
  flag and your problem.
- No outbound requests from the page. No CDN, no fonts, no analytics, no telemetry.
- Batches live in `~/.guide/`, outside every working tree, so they can't be committed.
- Nothing in `examples/` is real. Synthetic only, always.

---

## Deliberately not building

- Accounts, orgs, sharing, permissions
- A hosted service
- A generic form builder — this is review-shaped: a list of items, each with evidence
  and a judgment. Staying narrow is what makes it good.
- A results database. Answers are files.
- Anything collaborative or real-time between _people_. (Many agents, one human, is the
  supported shape. Many humans is not.)
