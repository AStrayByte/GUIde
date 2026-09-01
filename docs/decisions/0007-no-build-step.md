# ADR 0007 — No build step, and the classic scripts it costs

**Status:** accepted
**Date:** 2026-08-31

## Context

`docs/roadmap.md` bet that the page is vanilla HTML/CSS/JS with no build step,
and left an escape hatch: if it outgrows vanilla, port to Vite + Preact then, not
now.

The preview mock settled the question with evidence rather than argument. A
complete renderer — every block type, every field type, the inbox rail, the
version gate, the loud-degrade path, keyboard navigation and the answers builder
— came to roughly 570 lines of vanilla JavaScript, and nothing domain-specific
ever reached it across five sample batches in four shapes.

## Decision

**No build step, no framework, no bundler.** The shipped page is five files the
daemon serves as-is:

```
render.js      draws a card; knows the block and field vocabulary, and nothing else
ui.js          the small things both pages need: the API prefix, the theme toggle,
               the copy button
transport.js   where answers go: the daemon, or localStorage over file://
app.js         which batch is open, what the rail shows, where keystrokes go
style.css      the whole look, dark and light
```

`render.js` is pure. It does not fetch, does not save, and reaches for no global
state — it is handed a batch plus the values already answered, and returns DOM
plus a callback. That is what lets one renderer drive both transports.

## The forced trade: classic scripts, not ES modules

This is the real cost, and it is worth stating rather than discovering.

Browsers refuse ES module imports over `file://` — the module fetch is subject to
CORS, and a `file://` origin fails it. Opening a single batch straight off disk
with no process running is a documented feature (ADR 0002: _the single-file path
survives as a degenerate case_), and it matters precisely when a batch holds
client data and you would rather not run anything at all.

So the three scripts are classic `<script>` tags in dependency order, each
attaching to a `window.GUIde` namespace. No `import`, no `export`.

That is unfashionable, and it buys something concrete: the same `index.html` the
daemon serves also works when double-clicked.

## Consequences

- **No TypeScript on the page.** The Python side is fully typed and linted; the
  JavaScript is checked by tests and by reading it.
- **Script order is load-bearing.** `render.js`, then `ui.js`, then
  `transport.js`, then `app.js`. `index.html` says so in a comment, and
  `tests/test_web_assets.py` checks it.
- **`tests/test_web_assets.py` guards the seams a bundler would have caught**: a
  missing `src=` target, the viewer version drifting from `FORMAT_VERSION`, the
  JS field vocabulary drifting from `schema/batch.schema.json`, and an inline
  `style=` attribute reappearing (ADR 0006 forbids them).
- **The `file://` path is a real fallback, not a mock.** Same renderer, same
  continuous-save contract, with `localStorage` standing in for the answers file
  and a Copy JSON button to get the result out.

## Revisit if

- The page grows genuinely complex shared state. A rail, one open batch and a bag
  of answers is not that.
- The `file://` fallback stops being wanted. It is the only thing forcing classic
  scripts; without it this becomes a two-line change.
