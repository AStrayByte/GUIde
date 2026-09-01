# Roadmap

Three phases. Each ships something usable on its own. The rule: **no phase exists only
to enable a later phase.** If Phase 1 is all this ever becomes, it should still have
been worth building.

---

## Phase 0 — Freeze the format · **shipped**

Settle `batch.schema.json`, `answers.schema.json`, and the version-compatibility rules
in [versioning.md](versioning.md). Convert one real review by hand to prove the format
survives contact with reality.

**Ships:** a contract. Claude can start writing batches immediately, even with no UI —
you'd be reading raw JSON, which is bad, but it works.

**Done when:** the verifier triage batch round-trips without a single domain-specific
key in the schema.

---

## Phase 1 — The daemon and the inbox · **shipped 2026-08-31** ◀ the MVP

```
$ guide push ./questions.json
  started the guide daemon on http://127.0.0.1:7777
  pushed 01JQ8FQ2X7K3… · 17 cards
  3 batches waiting · http://127.0.0.1:7777/?batch=01JQ8FQ2X7K3M9VB4H0TZC5RWD
```

How it is actually built: [wiki/](wiki/index.html) for the tour,
[decisions/](decisions/) 0003–0007 for why each piece is the way it is.

**The daemon** — one process, started on demand, bound to `127.0.0.1`:

- accepts pushes from any number of Claude sessions
- stores batches at `~/.guide/batches/<id>/`, outside every working tree
- writes `answers.json` continuously — no Save button, no lost work
- is the only writer, so concurrent sessions can't interleave
- survives the sessions that pushed to it
- port-bind race handling, upward port scan, `~/.guide/daemon.json` for discovery

**The page** — one file, no build step, vanilla HTML/CSS/JS:

- **inbox rail** grouping waiting batches by session and repo
- new batches appear quietly; they never steal focus mid-card
- renders every block type in the vocabulary
- `choice` / `text` / `rating` / `compare` fields, with keyboard shortcuts
- progress bar and counters driven by the `summary` spec
- **version gate**: hard-fail on a major mismatch, per-card warnings on minor-ahead
- dark mode, because you'll be staring at it

**The CLI** — `push`, `wait`, `list`, `clean`. `wait` watches the answers file rather
than the daemon, so it survives a restart.

**Ships:** everything the hand-built triage page did, for any batch, from any number of
sessions at once, with the loop back to Claude already closed.

> **Why no framework.** The page this replaces is ~200 lines of vanilla JS and it's
> fine. No build step means it also opens over `file://` against a single batch, which
> matters when a batch has client data in it. If it outgrows vanilla, port to Vite +
> Preact then, not now.

---

## Phase 2 — Live loop · _ongoing_

The `guide` Claude Code skill, plus the small bit of daemon surface it needs:

- `/guide` — builds a batch from what's in context, pushes it, says it's waiting
- `/guide wait` — blocks until _its own_ batch is complete, then reads and summarizes
- **Per-card "ask about this"** — you're on card 42, you don't know what a column
  means, you type a question, it reaches the session that created that batch, scoped to
  that card's evidence. The one piece of the chat-UI idea worth building, and cheap
  because the daemon already tracks which session owns which batch.

**Ships:** you stop moving files around.

---

## Not on the roadmap

Things that will come up, and should be told no at least twice first:

- Accounts, permissions, sharing links
- A hosted or multi-tenant version
- Multiple _humans_ on one batch (many agents, one human, is the supported shape)
- A visual batch builder
- A results database
- Being a general-purpose form tool
