---
name: guide
description: Ask the human a batch of judgment calls and get structured answers back. Use when you have more than a handful of decisions that need a person — triaging findings, A/B comparisons, rating outputs, confirming assumptions — instead of asking them one at a time in chat.
---

# guide

You write a JSON file of questions with the evidence needed to answer them. It
appears in the human's browser as a page of cards with buttons. They click
through it. You read the answers back as JSON.

**Write ~40 lines of JSON per card, never HTML.** The renderer is a fixed asset
that is already correct; every token you spend on markup is a token spent on a
chance to break the page.

## When to reach for this

- More than ~5 judgment calls that need a human.
- Each one needs evidence attached (rows, a diff, two candidate answers).
- You can carry on doing something else while they answer.

For one quick question, just ask in chat. This is for volume.

## The commands

```bash
guide --format-version                  # the format this build speaks — target it
guide push ./questions.json             # returns a batch id; starts the daemon if needed
guide push - < questions.json           # or from stdin
guide wait <id>                         # blocks until the human presses Done
guide wait <id> --timeout 1800          # give up after 30 minutes
guide list                              # everything waiting, across every session
guide read <id>                         # the answers, without blocking
```

`push` fills in `source.cwd`, `source.repo` and `source.branch` from the working
directory, so you do not have to. Add `--label "verifier triage"` — it is what
the human's inbox rail shows, and "Batch 01JQ8F…" tells them nothing.

**Do not block the human.** `push` returns immediately. If you have other work,
do it, and `wait` last.

## The batch

```jsonc
{
  "guide_version": "0.1.0", // FIRST key, always. Checked before anything is parsed.
  "title": "Verifier triage",
  "subtitle": "Was the checker right to complain?",
  "instructions": "For each complaint: was the answer actually fine, or genuinely wrong?",

  "defaults": { "response": {/* applied to every card that omits its own */} },
  "summary": {
    "progress": true,
    "counters": [
      { "label": "false alarms", "field": "verdict", "equals": "false_alarm" },
    ],
    "rates": [
      {
        "label": "false-alarm rate",
        "field": "verdict",
        "numerator": ["false_alarm"],
        "denominator": ["false_alarm", "good_catch"],
      },
    ],
  },

  "cards": [/* ... */],
}
```

Omit `id`. The daemon mints one.

## A card

```jsonc
{
  "id": "1", // unique in the batch; answers join on this
  "title": "Chart of partners vs non-partners",
  "tags": ["numeric_faithfulness", "run 78"],
  "blocks": [/* what they read */],
  "response": {/* what they do — omit to inherit defaults.response */},
  "meta": { "run": 78, "check": "numeric_faithfulness" }, // opaque; echoed back verbatim
}
```

## Blocks — what they read

Every block takes an optional `label` and `collapsed: true` (renders inside a
disclosure, which is how 60 rows hide behind one line).

| `type`     | Fields                                       | Renders as                  |
| ---------- | -------------------------------------------- | --------------------------- |
| `text`     | `text`, `format`: `plain`\|`pre`\|`markdown` | Paragraph, monospace, or md |
| `callout`  | `text`, `footnote`, `tone`                   | The "why this matters" box  |
| `code`     | `code`, `language`                           | A code block                |
| `table`    | `columns[]`, `rows[]`, `note`, `truncated`   | Scrollable table            |
| `keyvalue` | `pairs[]` of `{key, value}`                  | Two-column list             |
| `diff`     | `diff` (unified diff text)                   | Coloured +/- diff           |
| `json`     | `value`                                      | Pretty-printed JSON         |
| `image`    | `src` (**data URI only**), `alt`, `caption`  | An image                    |
| `columns`  | `columns[]` of `{label, blocks[]}`           | Side-by-side panes          |

`tone` is `info` · `warn` · `bad` · `good` · `mute`.

`table.rows` may be objects keyed by column name, or plain arrays in column order.

## Fields — what they do

| `type`        | Extra                                    | Notes                               |
| ------------- | ---------------------------------------- | ----------------------------------- |
| `choice`      | `options[]`                              | Button row. `key` binds a shortcut. |
| `text`        | `multiline`, `placeholder`, `max_length` | The comment box                     |
| `rating`      | `min`, `max`, `labels`                   | 1–5 / Likert                        |
| `compare`     | `options[]` naming pane labels           | A/B pick; pairs with `columns`      |
| `multichoice` | `options[]`                              | Checkboxes                          |
| `boolean`     | `true_label`, `false_label`              |                                     |

An option is `{ "value", "label", "tone"?, "key"? }`. A card is **answered**
when every `required: true` field has a value.

## Three worked cards

**A judgment call with evidence** — the common case.

```jsonc
{
  "id": "3",
  "title": "Checker says the partner percentage is wrong",
  "blocks": [
    {
      "type": "callout",
      "tone": "info",
      "label": "Why this check exists",
      "text": "Numbers in prose must be recomputable from the rows returned.",
      "footnote": "It fires on any figure it cannot reproduce.",
    },
    {
      "type": "text",
      "format": "pre",
      "label": "What the agent said",
      "text": "31% of accounts are partners.",
    },
    {
      "type": "table",
      "label": "Rows the agent had",
      "collapsed": true,
      "columns": ["segment", "accounts"],
      "rows": [
        { "segment": "partner", "accounts": 37 },
        { "segment": "direct", "accounts": 81 },
      ],
    },
  ],
  "response": {
    "prompt": "Your verdict",
    "fields": [
      {
        "id": "verdict",
        "type": "choice",
        "required": true,
        "options": [
          {
            "value": "false_alarm",
            "label": "✓ False alarm",
            "tone": "good",
            "key": "1",
          },
          {
            "value": "good_catch",
            "label": "✗ Good catch",
            "tone": "bad",
            "key": "2",
          },
          {
            "value": "unsure",
            "label": "? Not sure",
            "tone": "mute",
            "key": "3",
          },
        ],
      },
      {
        "id": "comment",
        "type": "text",
        "multiline": true,
        "placeholder": "Comments (optional)",
      },
    ],
  },
  "meta": { "run": 78, "check": "numeric_faithfulness" },
}
```

**An A/B comparison** — `compare` knows it is picking between `columns` panes,
so the winning pane gets highlighted.

```jsonc
{
  "id": "7",
  "title": "Which summary is better?",
  "blocks": [
    {
      "type": "columns",
      "columns": [
        {
          "label": "A",
          "blocks": [{ "type": "text", "format": "pre", "text": "…" }],
        },
        {
          "label": "B",
          "blocks": [{ "type": "text", "format": "pre", "text": "…" }],
        },
      ],
    },
  ],
  "response": {
    "fields": [
      {
        "id": "winner",
        "type": "compare",
        "required": true,
        "options": [
          { "value": "A", "label": "A is better", "key": "a" },
          { "value": "B", "label": "B is better", "key": "b" },
          { "value": "tie", "label": "Tie", "key": "t" },
        ],
      },
    ],
  },
}
```

**A rating.**

```jsonc
{
  "id": "12",
  "title": "How usable is this error message?",
  "blocks": [{ "type": "code", "language": "text", "code": "Error: EINVAL" }],
  "response": {
    "fields": [
      {
        "id": "score",
        "type": "rating",
        "required": true,
        "min": 1,
        "max": 5,
        "labels": ["useless", "perfect"],
      },
    ],
  },
}
```

## Rules

1. **Put the evidence in the batch.** The point is that they never have to go
   look anything up. If the judgment needs the raw rows, include the raw rows.
2. **Collapse the bulk.** `collapsed: true` on the 60-row table. Cards stay
   scannable; detail is one click away.
3. **Declare the response once** in `defaults.response` when every card asks the
   same thing. Do not repeat it 200 times.
4. **Say why the question exists.** A `callout` explaining the check is what
   makes a card answerable by someone who did not build the checker.
5. **Everything you want back goes in `meta`.** Run ids, file paths, case keys.
   It returns verbatim and saves you a re-lookup.
6. **Never fabricate evidence.** If a value is not in the source data, it does
   not go in a block. A review built on invented context is worse than none.
7. **One judgment per card.** Three unrelated decisions is three cards.
8. **Target the oldest version that works.** Only reach for a newer minor when
   you actually use something from it.

## Reading the answers

```jsonc
{
  "complete": true,
  "degraded": false, // ← check this first
  "degraded_cards": [],
  "stats": { "total": 17, "answered": 17 },
  "answers": [
    {
      "card_id": "1",
      "title": "Chart of partners vs non-partners", // echoed
      "meta": { "run": 78 }, // echoed verbatim
      "values": { "verdict": "false_alarm", "comment": "31% is 37/118, fine." },
    },
  ],
}
```

If `degraded` is `true`, the human answered at least one card while looking at
content the viewer could not fully draw. Those `card_id`s are in
`degraded_cards`; discount those answers or re-ask after updating GUIde.

Otherwise: `values` keyed by field id, with `title` and `meta` echoed so you do
not need the original batch in context.
