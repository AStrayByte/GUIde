# ADR 0005 — The HTTP surface, and SSE over polling

**Status:** accepted
**Date:** 2026-08-31
**Closes:** open question 2

## Context

The daemon has two clients: the browser page and the `guide` CLI. Between them
they need to push a batch, list the inbox, read a batch and its answers, record
an answer, flip `complete`, remove a batch, and hear about changes.

The plan that preceded these ADRs put it plainly: it is small, but it is a
contract — version it or don't ship it.

## Decision

### One versioned surface at `/api/v0`

```
GET    /api/v0/meta                              versions, counts, liveness
POST   /api/v0/batches                           push (body is the batch itself)
GET    /api/v0/batches                           the inbox, as summaries
GET    /api/v0/batches/{id}                      the batch document
GET    /api/v0/batches/{id}/answers              the answers document
PUT    /api/v0/batches/{id}/answers/{card_id}    record one card
POST   /api/v0/batches/{id}/complete             the Done button, and its undo
DELETE /api/v0/batches/{id}[?archive=true]       clean
GET    /api/v0/events                            server-sent events
POST   /api/v0/shutdown                          guide stop
```

The version is in the path so a future shape can be served alongside this one
rather than replacing it under a live page.

### The daemon stores and counts; it never interprets

Blocks, fields, `meta` and every answer value are `Any` on the wire and opaque
on disk. The daemon parses exactly enough to store a batch, join answers to
cards by id, and count required fields.

This is stronger than the ADR 0001 rule that the _renderer_ never learns your
domain: the daemon never learns your _content_. It has to be. Modelling blocks
server-side would reject a batch using a block type newer than the installed
daemon, and additive-only minors would stop being additive.

### One card per write, and the daemon owns the derived fields

`PUT …/answers/{card_id}` carries `{values, degraded, viewer_version}` and
nothing else. The daemon echoes `title` and `meta` **from the batch it already
holds**, stamps `answered_at`, and recomputes `stats`, `degraded` and
`degraded_cards` on every write.

So the answers file cannot be made to disagree with the batch it came from, even
by a buggy page. The two fields that _do_ come from the browser are the two only
the browser can know: whether this renderer could draw every block on the card,
and which renderer it was.

An empty `values` removes the card's record. Un-answering has to be possible in
a tool whose whole job is recording considered judgments, and it means the page
never has to reason about whether a change is a create or an update.

### SSE, not polling

`GET /api/v0/events` streams named events — `batch.added`, `batch.answered`,
`batch.completed`, `batch.removed` — as `text/event-stream`.

Polling would have been fine at this scale, and the docs said so. SSE wins on a
detail that is not about scale: **`EventSource` reconnects on its own.** A daemon
restart, a closed laptop lid, a dropped connection — the browser handles all of
it, so the "daemon went away and came back" path costs zero lines. A
`StreamingResponse` over an `asyncio.Queue` is about forty lines the other way.

**The bus is deliberately lossy.** Each event is a _hint to refresh_, never a
delta the client must replay in order, so a subscriber that stops reading gets
its oldest events dropped rather than applying backpressure to the daemon. A
page that misses one and then sees the next still converges.

A 20-second heartbeat comment keeps the stream from being silently dropped by a
sleeping machine.

### No accounts — but the browser is not nobody

The daemon binds `127.0.0.1`, never `0.0.0.0`. There are no accounts and no
tokens, because the only *process* that can reach it is one already running as
you. Serving it on a network interface would be a different product with a
different threat model, and is not supported.

**"There is nobody else on the socket" is not quite true, and the first version
of this ADR said it anyway.** Every web page in every open tab is also on that
socket. A cross-origin `POST` with no custom headers is a CORS *simple request*:
no preflight, so the browser sends it and merely hides the response — which is
enough for a side effect. Any page you happened to visit could stop your daemon
mid-review, or trigger a skill install.

So state-changing requests are gated on origin, in one middleware rather than
route by route:

| What the request looks like                              | What happens |
| -------------------------------------------------------- | ------------ |
| `GET` / `HEAD` / `OPTIONS`, whatever the headers          | allowed      |
| `Sec-Fetch-Site: same-origin` or `none`                   | allowed      |
| No `Origin` and no `Sec-Fetch-Site` — the CLI, not a browser | allowed   |
| `Origin` matching this daemon                             | allowed      |
| Anything else                                             | **403**      |

The check is deliberately dumb. A browser labels its own requests; a plain HTTP
client does not. So: trust an explicit same-origin label, trust the absence of
any label, refuse everything else. The CSP does not help here — `form-action`
and `frame-ancestors` protect *our* page, not our endpoint.

Ids are also checked before they become paths. `Store` refuses any id that is
not a ULID, so a caller-supplied string can never be joined to the store root
and walked out of.

## Consequences

- A keystroke in a comment box is an HTTP round trip. Debounced at 120ms per
  card, so a burst of typing collapses into one write and the last value always
  lands.
- The page rebuilds a card on every change, which is cheap — except for the node
  someone is typing into, which is never rebuilt, because it would take the caret
  with it.
- Answers landing for the batch currently on screen are ignored by that page:
  they are almost always its own writes echoing back. The rail still updates.
- `DELETE` defaults to deleting rather than archiving. Batches may hold real
  client data, and the safe default for data nobody asked to keep is not keeping
  it (`?archive=true` and `guide clean --archive` for the other case).

## Alternatives rejected

- **A single `PUT …/answers` carrying the whole answer set.** Simpler surface,
  but it sends the entire document on every keystroke and makes the browser the
  authority on what an answers file looks like.
- **WebSockets.** Bidirectional, and nothing here is bidirectional. It would also
  mean writing the reconnect logic `EventSource` gives away.
- **Polling `/api/v0/batches` every few seconds.** Genuinely fine, and the
  fallback if SSE ever proves troublesome. It just does not do anything SSE does
  not already do for less.
