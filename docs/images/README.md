# Screenshots

Captured from the **shipped page** — a real `guide` daemon serving real batches out of a
throwaway `GUIDE_HOME` — in headless Chromium at `device_scale_factor=2` for retina.
All six are referenced from the root README.

| File               | State captured                                                       |
| ------------------ | -------------------------------------------------------------------- |
| `inbox.png`        | The flagship batch, 5 of 8 cards answered — rail, counters, progress |
| `example.png`      | The README's worked example, pushed from a repo-shaped `cwd`         |
| `card.png`         | Card 1 close up, collapsed evidence table opened                     |
| `degraded.png`     | Cards 2–3 of the A/B batch — unsupported block, and a blocked card   |
| `version-gate.png` | A stored batch declaring `0.9.0` — refused outright                  |
| `answers.png`      | The Copy JSON sheet — the answers file the daemon will write         |

## Retaking them

The sample data is deliberately ridiculous — the point is the shape, not the subject. It
lives in `.superseded/preview/batches.js` (five batches that between them exercise every
block type, every field type, the loud-degrade fallback, and the hard version gate).

Roughly:

1. `GUIDE_HOME=/tmp/shots uv run guide serve --port 7801` — never the real `~/.guide`,
   which may hold client data.
2. Push the four compatible batches with `guide push`. The `0.9.0` one has to be written
   straight into the store with `guide.store.Store.create`, because `push` refuses it —
   which is exactly the state `version-gate.png` documents.
3. Record answers through `PUT /api/v0/batches/<id>/answers/<card_id>` so the state
   survives a page reload; the browser is not the source of truth here.
4. Drive Chromium with Playwright at a 1440-wide viewport, `device_scale_factor=2`,
   `color_scheme="dark"`.

`example.png` is the odd one out: it is the README's own worked example, pushed from a
throwaway git repo (`payments-api`, branch `flake-triage`, one commit) so that
`source.repo` and `source.branch` resolve and the header reads like a real session.

By hand instead: open the page with `guide open`, set up the state you want, then `⌘⇧4`
plus space to grab a window, or `⌘⇧5` for a region.
