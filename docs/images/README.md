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

The sample data is real-shaped — a Claude session's own design calls (schema, style,
CLI, config), not placeholder text — because these are the first thing a visitor sees
and they should look like the tool doing its actual job. Eight batches between them
exercise every block type, every field type, the loud-degrade fallback, and the hard
version gate; none of it is checked in, the same way `.superseded/` never was.

Roughly:

1. Build the batches as plain dicts and write them straight in with
   `guide.store.Store(home=...).create(document)` — skips the HTTP layer entirely, so
   there's no daemon to keep alive while you iterate on content. Record answers with
   `store.record(batch_id, card_id, values)` and mark the done ones with
   `store.set_complete(batch_id, complete=True)`.
2. The `0.9.0` batch (`Payload schema v2`) has to go in the same way — `Store.create`
   bypasses the gate that `guide push` and the HTTP `POST /batches` both enforce, which
   is exactly the state `version-gate.png` documents. `store.record` doesn't gate at
   all, so it can still hold one answer.
3. Point a real daemon at that store — `GUIDE_HOME=/tmp/shots uv run guide serve --port
   7801` — never the real `~/.guide`, which may hold client data.
4. Drive Chromium with Playwright (`uv run --with playwright playwright install
   chromium`, then a `sync_playwright` script) at a 1440-wide viewport,
   `device_scale_factor=2`, `color_scheme="dark"`. Two things it doesn't do for free:
   a collapsed `<details>` doesn't reliably toggle on a synthetic click in headless
   Chromium, so set `.open = true` directly; and the sticky footer paints over a tall
   card on an element screenshot, so hide it (`display: none`) for the `card.png` shot.

`example.png` is the odd one out: it is the README's own worked example, pushed from a
throwaway git repo (`payments-api`, branch `flake-triage`, one commit) so that
`source.repo` and `source.branch` resolve and the header reads like a real session.

By hand instead: open the page with `guide open`, set up the state you want, then `⌘⇧4`
plus space to grab a window, or `⌘⇧5` for a region.
