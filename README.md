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
