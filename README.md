# GUIde

**A local inbox for the questions your agents need answered.**

Claude writes a JSON file: a list of questions, each with the evidence needed to answer
it. It pushes that to `guide`, running on your own machine. A browser page shows an
inbox of everything waiting — from every Claude session you have open — and renders
each question as a card with buttons. You click through them. It writes your answers
back to a JSON file. Claude reads it and keeps working.

That's the whole product.

## The words

Four terms, used consistently everywhere in these docs:

| Term        | What it is                                                                 |
| ----------- | -------------------------------------------------------------------------- |
| **batch**   | One JSON file — a list of questions an agent wants answered, with evidence |
| **card**    | One question in that batch, as drawn on screen: title, evidence, buttons   |
| **answers** | The JSON file that comes back out when you're done                         |
| **inbox**   | Every batch currently waiting on you, across all your sessions             |

## Why

Agents are good at generating 200 things that need a human judgment call, and terrible
at getting those judgments back. Today's options are all bad:

- **Ask in chat, one at a time** — burns context, loses your place, no progress state.
- **Dump a markdown table** — unreadable past ~10 rows, nowhere to attach evidence.
- **Build a one-off HTML page** — works great, which is the problem. You rebuild it
  every time, and the review data ends up welded to the review UI.

That last one is what this generalizes. It came from
a hand-built `.reviews/verifier-triage.html`: 17 verifier complaints, each with the
question, the answer, the raw data rows the agent had, and three buttons. It worked
well enough to obviously be a tool rather than a file.

## Shape

```
  Claude (search-api)  ─┐
  Claude (web-client)  ─┼─▶  guide daemon  ─▶  browser: an inbox of batches
  Claude (report-gen)  ─┘    127.0.0.1:7777     you work through them in any order
                                  │
                                  └──▶ answers.json ──▶ back to whichever session asked
```

Everything runs on your machine. No accounts, no hosting, no shared server, no auth.
Nobody gets a link — they install it and run their own copy for their own agents.

## What it looks like

A clickable mock lives in [preview/](preview/) — open `preview/index.html`, no server and
no build step. The sample batches are deliberately ridiculous; the point is the shape,
not the subject.

![The inbox and a batch in progress](docs/images/inbox.png)

Several agent sessions push into one inbox. The left rail groups by repo and survives
the sessions that filled it. The header counters and the false-alarm rate are declared
by the batch — the renderer doesn't know what a "cried wolf" is.

![One card: evidence, then the buttons](docs/images/card.png)

One judgment per card, with the evidence needed to make it. Bulky data collapses behind
one line, so cards stay scannable. Every card in this batch shares a single
`defaults.response` declaration rather than repeating it eight times.

![Degrading loudly on unsupported content](docs/images/degraded.png)

When the viewer meets something it can't draw, it says so **on the card where it
happened** and hands you the raw JSON. An unsupported *required* field blocks its card
outright — better an obviously-stuck card than a silently skipped one.

![Refusing a batch from a newer GUIde](docs/images/version-gate.png)

A version mismatch it can't handle safely is refused rather than half-rendered. A
silently degraded review means someone judges on evidence they can't see, and an agent
acts on that judgment.

![The answers file](docs/images/answers.png)

What goes back to Claude. `title` and `meta` are echoed verbatim so the answers file is
actionable without the original batch in context, and `degraded` tells the agent whether
to trust it.

## Status

Design phase, nothing built. Read in order:

| Doc                                              |                                                        |
| ------------------------------------------------ | ------------------------------------------------------ |
| [docs/architecture.md](docs/architecture.md)     | How it's put together, and why it's this small         |
| [docs/format.md](docs/format.md)                 | The batch + answers JSON, annotated                    |
| [docs/versioning.md](docs/versioning.md)         | The version declaration and what happens on a mismatch |
| [docs/roadmap.md](docs/roadmap.md)               | Three phases                                           |
| [docs/claude-side.md](docs/claude-side.md)       | How Claude writes a batch and reads answers            |
| [docs/open-questions.md](docs/open-questions.md) | Not yet decided                                        |
| [docs/decisions/](docs/decisions/)               | ADRs — why it's a page not a chat, why a daemon        |
| [schema/](schema/)                               | Machine-readable contract                              |
| [examples/](examples/)                           | Sample batches — synthetic data only, always           |
| [preview/](preview/)                             | Clickable mock of the Phase 1 page — open `index.html` |
| [docs/backlog/](docs/backlog/)                   | Next up: planning the tech architecture                |
