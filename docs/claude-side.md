# The Claude side

How an agent produces a batch, and how the answers get back into its head.

## The key constraint

**Claude writes ~40 lines of JSON per card, not 120KB of HTML.**

The hand-built triage page worked, but generating it cost an enormous number of output
tokens, and every one of those tokens was a chance to break the page. With a batch, the
model writes only content; the renderer is a fixed asset that's already correct.

That's the efficiency argument and the correctness argument at once, and it's the same
insight as _"Claude just knows the syntax and the UI decodes it"_ — pointed at a page
instead of a chat bubble.

## The commands

```
/guide "triage these 17 verifier complaints"
```

1. Reads a compact authoring cheat-sheet (not the full JSON Schema — that's for
   validation, not for the model to re-read every time).
2. Checks the installed viewer's format version with `guide --format-version`, and
   targets it. See [versioning.md](versioning.md).
3. Builds the batch from what's in context. `source.session_id` is stamped by
   `guide push` from the environment, so the answers find their way home without the
   agent having to remember.
4. `guide push` — the daemon starts if it isn't running, and the batch appears in your
   inbox.

```
/guide wait
```

Blocks until **its own** batch is complete — matched by `session_id`, so three sessions
waiting at once never wake on each other's answers — then reads the answers, summarizes
the verdicts, and continues the work that prompted the questions.

```
/guide list          # what's waiting, across every session
/guide read <id>     # non-blocking, for a batch you answered yesterday
```

## Several sessions at once

Nothing special is required of the agent beyond stamping `source` honestly. The daemon
handles the multiplexing. What the skill must get right:

- **Always set `session_id`.** Without it, `guide wait` can't tell whose answers are
  whose, and a per-card question has nowhere to go back to.
- **Set a short `label`.** It's what the inbox rail shows. "verifier triage" beats
  "Batch 01JQ8FQ2X7K3M9VB4H0TZC5RWD".
- **Don't block the user.** `push` returns immediately. If the session has other work
  it can do while questions sit in the inbox, do that work first and `wait` last.
- **One batch per question set.** Don't append to a batch already in the inbox —
  someone may be halfway through answering it.

## The skill file

It exists: [`src/guide/skill/SKILL.md`](../src/guide/skill/SKILL.md). Not the whole
schema — a compact authoring guide, roughly one page:

- the batch skeleton, including the `guide_version` and `source` stanzas
- the block vocabulary, one line each
- the field types
- **three worked cards** covering the common shapes: a judgment call with evidence, an
  A/B comparison, a rating
- the rule that `meta` is the passthrough for anything domain-specific

It ships **inside the package** rather than at the repo root, so the copy an agent
installs always matches the `guide` binary it will be calling. A skill documenting a
format the installed daemon does not speak is worse than no skill.

### Installing it

```
guide skill install     # writes ~/.claude/skills/guide/SKILL.md
guide skill show        # print it
guide skill prompt      # a paragraph to paste into Claude, which installs it for you
guide skill page        # open the install page in a browser
```

The page at `http://127.0.0.1:7777/skill` offers all four, and knows whether the skill
is currently installed — so its instructions cannot go stale the way a README's do.

`source` is filled in for you. `guide push` reads the working directory, the git repo
and branch, and `$CLAUDE_CODE_SESSION_ID`, and only fills in what the batch left blank —
anything the agent stated wins.

## Authoring rules for the agent

Worth writing into the skill, because these are the mistakes a model will make:

1. **Put the evidence in the batch.** The whole point is that you don't have to go look
   anything up. If the judgment needs the raw rows, include the raw rows.
2. **Collapse the bulky stuff.** `collapsed: true` on the 60-row table. Cards should be
   scannable; detail is one click away.
3. **Declare the response once** in `defaults.response` when every card asks the same
   thing. Don't repeat it 200 times.
4. **Explain why the question exists.** The `callout` block in the triage page ("Why
   this check exists") is what made it answerable by someone who hadn't built the
   checker.
5. **Everything the agent needs back goes in `meta`.** Run ids, file paths, case keys.
   It returns verbatim and saves a re-lookup.
6. **Never fabricate evidence.** If a value isn't in the source data, it doesn't go in
   a block. A review built on invented context is worse than no review.
7. **One judgment per card.** If a card needs three unrelated decisions, it's three
   cards.
8. **Target the oldest format version that works.** Plain choice cards are `1.0.0` and
   every viewer can read them. Only reach for a newer minor when you actually use
   something from it.

## Reading the answers

Check `degraded` before you trust the results. If it's `true`, the human answered at
least one card while looking at content the viewer couldn't fully render — those
`card_id`s are listed in `degraded_cards`, and those answers deserve either a discount
or a re-ask after updating GUIde.

Otherwise: `answers[].values` keyed by field id, with `title` and `meta` echoed so you
don't need the original batch in context.

The daemon writes the answers file continuously, so by the time the human hits Done
it's already on disk. Copy-paste stays available as a fallback — the page has a Copy
JSON button, and it's how the original triage page worked — but it isn't the design.
