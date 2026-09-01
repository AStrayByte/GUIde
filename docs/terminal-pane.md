# Answering in a terminal pane

The inbox is a web page, so it normally opens in a web browser. It can instead open in
a pane beside your agent, without leaving the terminal — a real browser, rendered into
the pane as pixels.

This is a **way to run the existing page**, not a second UI. Nothing in `src/guide/web/`
changes, and nothing here is required to use GUIde.

Verified working on 2026-09-01: herdr 0.8.2, terminal-browser v0.7.6, Ghostty on macOS.
Clicking, scrolling and keyboard shortcuts all behave.

## What it needs

| Requirement                                                        | Why                                                                     |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| [terminal-browser](https://github.com/zenbu-labs/terminal-browser) | The browser. Electron, so the page renders exactly as it does elsewhere |
| A terminal multiplexer it supports (herdr, tmux, …)                | It splits the pane for you                                              |
| **An outer terminal that speaks the kitty graphics protocol**      | It paints pixels, not text. No protocol, no picture                     |
| herdr **≥ 0.8** if you use herdr                                   | 0.7.5 is broken against terminal-browser v0.7.6 — see below             |

On macOS that means **Ghostty** or **Kitty**. **Apple Terminal does not work** — it has
neither kitty graphics nor sixel, and the failure is silent: the pane is simply black.

There is no fallback. terminal-browser renders through a native module
(`browser/native/pixel.node`) that drives the kitty graphics protocol; there is no sixel
mode, no half-block mode and no text mode anywhere in it. Turning graphics _off_ does not
give you a faster pane, it gives you an empty one.

## Setup

```sh
terminal-browser setup     # installs agent skills, enables the terminal settings it needs
```

For herdr, that means `~/.config/herdr/config.toml` gets:

```toml
[experimental]
kitty_graphics = true
```

Confirm it landed somewhere herdr actually reads:

```sh
herdr config check         # want: config: ok
```

> **Known setup bug.** `terminal-browser setup` appends the flag without checking which
> TOML table it lands in. If a `[ui]` section precedes it you get a bare
> `experimental.kitty_graphics = true` line _inside_ `[ui]`, which parses as
> `ui.experimental` and is ignored:
>
> ```
> unknown config key ui.experimental; ignoring key
> ```
>
> Delete that line. The top-level `[experimental]` block is the one that works.

## Opening it

```sh
guide push ./questions.json
terminal-browser open "http://127.0.0.1:7777/?batch=<id>" --split right --size 0.5 --no-toolbar
```

`--no-toolbar` drops the tab strip so the whole pane is the page. Adding `--app-mode
--app-name=GUIde` goes further into chromeless embedding — untested here, and it disables
browser features by design, so add it only once you know plain input works.

Half a pane is not a small viewport. Measured in a 143×80-cell pane, the page gets
**2223 × 2466 CSS px** with the rail at 268 — comfortably past the 720px breakpoint in
`style.css`, so you get the full desktop layout. Side-by-side `columns` cards render as
intended. Card width is not a reason to avoid this.

## Open it once, not once per push

The inbox is already cross-session — the rail lists every batch from every agent you have
running — and the page holds an `EventSource` on `/api/events`. A pane that is already
open **picks up new batches by itself**.

So the pane is opened once and left alone. Shelling out to `terminal-browser open --split`
on every `push` would stack a new pane per batch and give you three browsers for three
agents. Check `terminal-browser ls` first; if a GUIde browser is up, do nothing.

## Focus

`terminal-browser open --split` always passes `--focus` to the multiplexer, and there is
no flag to suppress it. It takes your keyboard.

That fights the premise in the README: `push` returns immediately so the human answers when
they feel like it, not the moment an agent has a question. To get a pane that appears
without interrupting, drive the split yourself:

```sh
pane=$(herdr pane split --current --direction right --ratio 0.5 --cwd "$PWD" --no-focus \
       | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['pane']['pane_id'])")
herdr pane run "$pane" terminal-browser open "http://127.0.0.1:7777/?batch=<id>"
```

Keyboard input in herdr follows pane focus, so a `--no-focus` pane is visible but not
typable until you focus it. That is the intended trade, not a bug — but it is worth knowing
before you conclude that input is broken.

## When it goes wrong

| Symptom                                               | Cause                                              | Fix                                   |
| ----------------------------------------------------- | -------------------------------------------------- | ------------------------------------- |
| Pane is black, `terminal-browser ls` shows it running | Outer terminal has no kitty graphics               | Use Ghostty or Kitty                  |
| Pane is black, `herdr config check` warns             | `kitty_graphics` written under `[ui]`              | Move it to top-level `[experimental]` |
| `unknown option: --right-click`                       | herdr older than terminal-browser expects          | `herdr update`                        |
| Renders, but clicks do nothing                        | herdr 0.7.5 does not forward mouse to the pane     | `herdr update`                        |
| Nothing typed reaches the page                        | Pane is not focused                                | Focus it                              |
| Scrolling is slow                                     | Old herdr graphics path — 0.8.2 is markedly better | `herdr update`                        |

The mouse case is worth stating plainly, because it looks like a configuration problem and
is not. terminal-browser requests mouse input correctly — `[?1003h` (any-event tracking),
`[?1006h` (SGR coordinates) and `[?1004h` (focus reporting) are all in `pixel.node` — and
herdr's own config documents that it forwards mouse to pane apps that ask:

```
# Capture mouse input for Herdr's mouse UI.
# Pane apps like lazygit and btop can still receive mouse when they request it.
# mouse_capture = true
```

Both halves were correct and clicks still went nowhere on herdr 0.7.5. Updating fixed it.
Do not go hunting through `mouse_capture` — check versions first.

**`herdr update` cannot run from inside a herdr session.** It exits with `run \`herdr
update\` outside herdr after detaching from the session`. Detach (`ctrl+b`then`q` by
default), update, reattach.

## Verifying without looking

The browser is scriptable, which is how you check a change rendered without a human
eyeballing the pane:

```sh
terminal-browser ls --all                                   # browser key, tab, pane
terminal-browser action --browser <key> -- snapshot         # accessibility tree
terminal-browser action --browser <key> -- get box body     # viewport size
terminal-browser action --browser <key> -- screenshot out.png
```

One caveat learned the hard way: **`snapshot` and `screenshot` go through the browser's own
renderer, not through the terminal.** They come back perfect while the human stares at a
black pane. They prove the page rendered; they prove nothing about whether it reached the
terminal. For that, look at the pane.

## If this ever becomes a `guide` subcommand

Notes for whoever picks this up. Not decided, not scheduled — see
[backlog](backlog/README.md).

- **The two call sites are `cli.py:61` and `cli.py:176`**, the existing `webbrowser.open()`
  calls in `cmd_push --open` and `cmd_open`.
- **Gate on `terminal-browser`, not on the multiplexer.** `HERDR_ENV=1` is tempting and
  wrong: terminal-browser also handles tmux, kitty and others, so testing for herdr makes
  the feature narrower than the capability for no gain. Test `command -v terminal-browser`.
- **Keep the OS browser the default.** This path costs a specific terminal and a graphics
  protocol. It should be a flag — `guide open --split` — not a behaviour that changes
  under people who never asked for it.
- **Split it yourself, `--no-focus`**, per the focus section above.
- **Do not re-split when a browser is already up**, per the SSE section above.
