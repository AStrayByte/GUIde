# Preview mock

A clickable mock of the Phase 1 page from [../docs/architecture.md](../docs/architecture.md).
Not the product — a thing to argue with before any of it is built.

Open `index.html` in a browser. No server, no build step, no network. It works over
`file://`, which is the same property the real single-file path has to keep.

## What it demonstrates

| Thing                    | Where to look                                                                       |
| ------------------------ | ----------------------------------------------------------------------------------- |
| The inbox rail           | Left side. Five waiting batches across three repos, plus a Done section.            |
| `render(batch)`          | Every card on screen is drawn from `batches.js` by `render.js`. No markup.          |
| Block vocabulary         | Batch 1 for callout/text/table, 2 for `diff`, 3 for `code`/`json`, 4 for `columns`. |
| `collapsed: true`        | The "data the agent actually had" tables — one line until you want them.            |
| `defaults.response`      | All 8 cards in batch 1 share one three-button spec, declared once.                  |
| Field types              | `choice` (1), `boolean` + `multichoice` (2), `rating` (3), `compare` (4).           |
| Keyboard nav             | `j`/`k` to move, then the number or letter on each button. Auto-advances.           |
| Continuous save          | Answer something and reload. Nothing is lost, and there is no Save button.          |
| Summary counters + rates | Batch 1's header — false-alarm rate updates as you answer.                          |
| Degrading loudly         | **Batch 4, card 2** — an unsupported block falls back with its raw JSON.            |
| A blocked card           | **Batch 4, card 3** — unsupported _required_ field, so it can't be answered.        |
| The version gate         | **Batch 5** — declares `0.9.0`, refused outright rather than half-rendered.         |
| The answers file         | "Copy JSON" in the footer — the real `answers.json`, echoed `meta` and all.         |
| A batch arriving         | Wait ~12s. Toast in the corner; the rail updates; your place is untouched.          |

## What it fakes

- **No daemon.** `localStorage` stands in for `~/.guide/batches/<id>/answers.json`. Same
  contract (every change persists immediately), no process.
- **The rail's Done section** is static filler, apart from batches you finish yourself.
- **Markdown** is a ~30-line subset — enough for the sample cards, not a spec.
- **`md()` builds HTML from batch text.** It escapes first, but in the real thing batch
  content is agent-authored and this is the one place XSS could enter. Worth deciding
  properly (sanitizer, or no markdown block at all) before it's a product.

All data in `batches.js` is synthetic.

## Files

```
index.html    ~30 lines   shell: the rail and the main pane
style.css     ~420 lines  the whole look, dark and light
batches.js    ~700 lines  five sample batches + one that arrives late
render.js     ~570 lines  render(batch) -> cards, collect(page) -> answers
```

`render.js` is the load-bearing one, and it's roughly the size the real Phase 1 renderer
should be. That's the useful signal here: the vanilla-no-framework bet in the roadmap
looks right.
