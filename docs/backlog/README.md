# Backlog

Things to work on later, or turn into tickets — but not right now.

Next up is Phase 2 in [../roadmap.md](../roadmap.md), and whatever
[../open-questions.md](../open-questions.md) still has open.

## `guide open --split`

Open the inbox in a terminal pane beside the agent rather than in a browser window.
Proven by hand on 2026-09-01 — herdr 0.8.2, terminal-browser v0.7.6, Ghostty — with the
page, its layout and its keyboard shortcuts all working unmodified. Written up in
[../terminal-pane.md](../terminal-pane.md), including the constraints and the two call
sites it would touch.

Not scheduled. It is a convenience for one terminal setup, it costs a kitty-graphics
terminal and a second binary, and the OS browser has to stay the default either way.

## Retired

Empty as of 2026-08-31: planning the tech architecture was the only item, and it is done.
The decisions it was meant to produce are ADRs
[0003](../decisions/0003-python-and-uv.md) through
[0007](../decisions/0007-no-build-step.md), and the working plan and the decision-aid page
that produced them have been retired to `.superseded/` — per this repo's doc rules, the
ADRs are the durable artifact and the plan is not.
