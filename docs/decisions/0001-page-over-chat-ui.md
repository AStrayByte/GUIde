# ADR 0001 — A page driven by files, not a chat UI

**Status:** proposed
**Date:** 2026-08-31

## Context

Two candidate architectures for getting structured questions from an agent to a human
and answers back.

**A. A page driven by files.** The agent writes a JSON file (a _batch_) describing a
list of questions plus their evidence. A local app renders it as a page of cards. You
answer. It writes a JSON answer file.

**B. A chat UI that decodes agent syntax.** A web chat client where the agent emits
fenced blocks the UI knows how to render as live widgets inline. Clicking a widget
becomes the next turn.

Both rest on the same real insight: **the agent should emit structured blocks that a
fixed renderer decodes, rather than hand-writing HTML.** They differ only in where
those blocks land.

Constraint established up front: this is a **single-user, locally-run tool**. Each
person runs their own copy for their own agent. There is no shared instance.

## Decision

Build A. Adopt B's insight — a fixed block vocabulary the UI decodes — as the core of
A rather than as a separate product.

## Why

1. **A chat client already exists and is better than one we'd build.** Claude Code has
   the repo, the tools, the context, the skills, the model. The missing piece is a
   place to _render and collect_, not a place to converse. Building a chat window to
   gain a rendering surface is paying a large cost for a small part of the value.

2. **B means running inference.** An API key, streaming, retries, history, token cost —
   all to reproduce a conversation you can already have.

3. **Volume wants a page, not a transcript.** 200 items with progress state, filters,
   and keyboard nav is a page. Review state that lives in a conversation is state you
   will lose.

4. **Local + single-user makes A's supposed weakness vanish.** The usual knock on the
   file model is the copy-paste handoff. But a local server has a filesystem and sits
   on the same machine as Claude Code, so it writes the answers file directly and the
   agent reads it. There is no handoff to eliminate later, because there never is one.

5. **B stays reachable.** Same block vocabulary, same renderer. A chat surface later is
   a new front-end over the same parts, not a rewrite. Nothing here forecloses it.

## Consequences

- The block vocabulary is the asset. It gets the design effort; everything else is
  transport and is meant to be swappable.
- The renderer must never learn the domain. Domain data rides in an opaque `meta`
  field. This is the rule that keeps GUIde from becoming specific to any one project.
- The _narrow_ version of B — a per-card "ask Claude about this" thread — stays on the
  roadmap (Phase 2). That's where a live connection genuinely earns its cost, and it's
  cheap because both processes are already local.
- Copy-paste survives as a fallback (a Copy JSON button), not as the design.

## Revisit if

- Batches stop being batch-shaped. If the common case becomes "one question, needs a
  follow-up, then another question", that's a conversation and B wins.
- The per-card ask-about-this thread turns out to be where all the value is, in which
  case the page is really a chat client with a good sidebar and we should say so.
