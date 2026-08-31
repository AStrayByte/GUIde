# Open questions

Decisions not yet made. The starred one changes the design; the rest are details that
can wait until something's running.

**Settled already** (2026-08-31):

- Single-user, run locally. No hosting, no accounts, no sharing model — each person
  installs their own copy. This deleted most of what was open.
- A page driven by files, not a chat UI. [ADR 0001](decisions/0001-page-over-chat-ui.md).
- Field types for v0.1: `choice` + comment, A/B `compare`, `rating`. `rank` dropped.
- Many concurrent agent sessions, one daemon, one inbox.
  [ADR 0002](decisions/0002-daemon-with-an-inbox.md).
- `guide_version` is `major.minor.patch`, declared first, checked before parsing.
  [versioning.md](versioning.md).

---

## ★ 1. What language does it ship in?

This decides how someone else installs it, which is the only distribution question
left. The daemon requirement raises the stakes a little — it's a long-lived process now, not a
script.

|            | Install                  | Notes                                                                                                                                      |
| ---------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Node**   | `npx guide push …`       | Lowest friction — no install step. Front-end is JS anyway, so one language. Good process/watch story.                                      |
| **Python** | `pipx install guide-cli` | Your home turf. Stdlib covers it, but `http.server` is weak for a long-lived daemon; you'd want a real ASGI server, which is a dependency. |
| **Go**     | download a binary        | Best daemon story by far, single file, zero runtime deps. Most work, and you'd be writing Go.                                              |

Still leaning **Node**, and the daemon strengthens that: `npx` means a new user runs one
command and never installs anything, and Node's watch/serve primitives are exactly what
a small daemon needs.

## 2. How does the page find out a new batch arrived?

- **SSE** from the daemon — clean, one connection, natural fit.
- **Poll** every few seconds — dumber, and honestly fine at this scale.

Leaning SSE, but it's not worth blocking on. Either is a small amount of code.

## 3. Does the daemon auto-start, or is that too magical?

`guide push` starting a background process the user never asked for is convenient and
slightly rude. Options: always auto-start (proposed), auto-start with a one-line notice,
or require an explicit `guide serve` the first time.

Leaning auto-start **with a notice**, plus `guide stop`.

## 4. Notifications when you're not looking at the browser

Three sessions can queue up questions while you're in a terminal. Worth a macOS
notification on the first arrival? A menu-bar count? Or is the browser tab enough?

Probably nothing in Phase 1, but the daemon makes it trivially possible later, so don't
design it out.

## 5. Batch lifecycle and cleanup

Answered batches age out of the rail after N days — what's N? And does `guide clean`
delete them or archive them? Given batches may hold client data, **delete** is arguably
the safer default, with an explicit `--archive` to keep.

## 6. Should there be a Done button at all?

Answers write continuously, so nothing is at risk. But something must flip
`complete: true` so `guide wait` knows to stop blocking. So: yes, one Done button at the
bottom, and nothing else.

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
