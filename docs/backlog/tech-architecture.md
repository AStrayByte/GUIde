# Backlog

Things to work on later, or turn into tickets — but not right now.

---

## [ ] Plan the tech architecture

**Status:** not started · **Blocks:** Phase 1 · **Do this with Claude, in a session.**

[docs/architecture.md](../architecture.md) is a _product_ architecture — it settles what
the thing is, what the layers are, and what's deliberately not built. It does not settle
how any of it is implemented. That's the gap this closes, and Phase 1 shouldn't start
until it is.

### What has to come out of it

| Decision                    | Notes                                                                                                                 |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Language + runtime**      | Open question ★1, and the one that gates everything else. Leaning Node/`npx`. Decide it first, write it up as an ADR. |
| **Daemon process model**    | On-demand start, the port-bind-as-lock race, upward port scan, `~/.guide/daemon.json` discovery, `guide stop`.        |
| **Store layout**            | What's actually on disk under `~/.guide/batches/<id>/`, and how a partial write can't corrupt an answers file.        |
| **HTTP surface**            | The endpoints the page and the CLI need. Small, but it's a contract — version it or don't ship it.                    |
| **Page ↔ daemon transport** | Open question 2: SSE vs poll. Pick one and note why.                                                                  |
| **Renderer structure**      | Block dispatch, field dispatch, the version gate, where the fallback path lives. See the notes below.                 |
| **CLI shape**               | `push` / `wait` / `list` / `clean`, and how `wait` watches the answers file rather than the daemon.                   |
| **Test strategy**           | Chiefly: how the format contract gets tested independently of the UI.                                                 |

### What the preview mock already tells us

[`preview/`](../../preview/) is a working renderer over the real format, so some of this
is answered by evidence rather than argument:

- **The no-framework bet holds.** A complete renderer — every block type, every field
  type, the inbox rail, the version gate, the loud-degrade path, keyboard nav and the
  answers builder — is about 570 lines of vanilla JS. Reach for Vite + Preact only if
  something concrete outgrows that.
- **Rendering is genuinely a pure function of the batch.** Nothing domain-specific
  reached the renderer while building five sample batches across four shapes.
- **`defaults.response` earns its place immediately.** Eight cards, one declaration.
- **One thing the mock does badly and the real one must decide properly:** the
  `markdown` text block builds HTML from batch content. Batches are agent-authored, so
  that's the one place untrusted-ish input becomes markup. Either sanitize it, or drop
  the markdown format and keep `plain`/`pre`. Worth an explicit call, not a default.

### Sequence

1. Settle ★1 (language) — it constrains the rest.
2. Write the daemon lifecycle up properly; it's the part with real concurrency in it.
3. ADR each decision as it lands, under [`docs/decisions/`](../decisions/). Delete the
   working plan when the ADRs exist — per the repo's own doc rules, the ADRs are the
   durable artifact and the plan is not.
