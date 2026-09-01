# The batch format

Two files. A **batch** goes in, an **answer set** comes out. Both open with a
`guide_version` declaration, and both are plain JSON with no cleverness.

Machine-readable versions live in [`../schema/`](../schema/). The compatibility rules
around `guide_version` are in [versioning.md](versioning.md) — read that too; it's
short, and for a review tool a silently degraded render is a correctness bug.

---

## Design rules

The constraints that keep this from rotting:

1. **The renderer never learns your domain.** Anything domain-specific goes in `meta`,
   which the renderer treats as opaque and echoes back verbatim in the answers. If you
   ever want to write `"type": "verifier_complaint"`, you've made a mistake.
2. **Blocks are what you read; fields are what you do.** A card is a stack of blocks
   plus a small set of fields. Never mix them.
3. **Unknown block types render as a visible fallback, never an error** — but the
   fallback _announces itself_ on the card where it happened. Degrading is fine;
   degrading silently is not.
4. **Answers join to the batch by `card_id` alone.** No positional coupling.
5. **A batch is self-contained.** No external fetches, no `$ref`, no image URLs that
   need the network. Data URIs or nothing.
6. **`guide_version` is checked before anything else is parsed.** Like an XML
   declaration. A batch from a future major fails cleanly instead of half-rendering.

---

## Batch

```jsonc
{
  "guide_version": "0.1.0", // FIRST key, always. Checked before parsing.
  "id": "01JQ8FQ2X7K3M9VB4H0TZC5RWD", // ULID — collision-free across sessions
  "title": "Verifier triage",
  "subtitle": "Was the checker right to complain?",
  "instructions": "For each complaint: was the answer actually fine (the checker cried wolf), or was it genuinely wrong?",
  "created_at": "2026-08-31T14:02:00Z",

  "source": {
    "agent": "claude-code",
    "session_id": "00000000-0000-4000-8000-000000000000", // routes answers home
    "cwd": "/Users/you/dev/search-api",
    "repo": "search-api",
    "branch": "eval-tooling",
    "label": "verifier triage", // what the inbox rail shows
  },

  "defaults": { "response": {/* a response spec applied to every card */} },
  "summary": {/* header stats — see below */},
  "cards": [/* ... */],
}
```

`defaults.response` is the important ergonomic win: a 200-card triage where every card
has the same three buttons declares those buttons **once**. A card may still override.

### `source` earns its keep with several sessions running

It's no longer decorative footer text. With three Claude sessions pushing batches into
one inbox:

- `session_id` is how `guide wait` knows which batch is _its own_, and how a per-card
  question gets routed back to the right session.
- `repo` and `label` are what the inbox rail groups and labels by — without them, "17
  verifier complaints" and "4 API doc questions" blur into an undifferentiated pile.
- `cwd` lets the skill resolve relative file paths mentioned in a card.

`id` is a **ULID**, not a slug: two sessions pushing in the same millisecond can't
collide, and ids sort by creation time for free.

---

## Card

```jsonc
{
  "id": "1",
  "title": "Give me a chart of users who are partners vs not partners",
  "tags": ["numeric_faithfulness", "run 78"],
  "blocks": [/* what you read */],
  "response": {/* what you do — omit to inherit defaults.response */},
  "meta": { "run": 78, "check": "numeric_faithfulness" }, // opaque passthrough
}
```

---

## Blocks — what you read

Every block takes an optional `label` (the small uppercase heading) and optional
`collapsed: true`, which renders it inside a `<details>`. That's how you hide 60 rows
of data behind one line and keep cards scannable.

| `type`     | Fields                                           | Renders as                                           |
| ---------- | ------------------------------------------------ | ---------------------------------------------------- |
| `text`     | `text`, `format`: `plain` \| `pre` \| `markdown` | Paragraph, monospace block, or rendered markdown     |
| `callout`  | `text`, `footnote`, `tone`                       | Left-bordered highlight — the "why this matters" box |
| `code`     | `code`, `language`                               | Syntax-highlighted block                             |
| `table`    | `columns[]`, `rows[]`, `note`, `truncated`       | Scrollable table; a row is an object or an array     |
| `keyvalue` | `pairs[]` of `{key, value}`                       | Two-column list; the order of the pairs is preserved |
| `diff`     | `diff` (unified diff text)                       | Colored +/- diff                                     |
| `json`     | `value`                                          | Collapsible JSON tree                                |
| `image`    | `src` (data URI), `alt`, `caption`               | An image                                             |
| `columns`  | `columns[]`, each `{ label, blocks[] }`          | Side-by-side panes                                   |

`tone` is one of `info` · `warn` · `bad` · `good` · `mute`.

`columns` nests other blocks, which is what makes "answer A vs answer B side by side"
work without a special block type for it.

---

## Response — what you do

```jsonc
{
  "prompt": "Your verdict",
  "fields": [
    {
      "id": "verdict",
      "type": "choice",
      "required": true,
      "options": [
        {
          "value": "false_alarm",
          "label": "✓ False alarm — answer was fine",
          "tone": "good",
          "key": "1",
        },
        {
          "value": "good_catch",
          "label": "✗ Good catch — answer was wrong",
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
}
```

Field types for v0.1 — the three shapes you said you actually want, plus the two
primitives they lean on:

| `type`        | Extra fields                             | Notes                                                      |
| ------------- | ---------------------------------------- | ---------------------------------------------------------- |
| `choice`      | `options[]`                              | Single-select button row. `key` binds a keyboard shortcut. |
| `text`        | `multiline`, `placeholder`, `max_length` | The comment box                                            |
| `rating`      | `min`, `max`, `labels`                   | 1–5 / Likert                                               |
| `compare`     | `options[]` referencing pane labels      | A/B pick — pairs with a `columns` block                    |
| `multichoice` | `options[]`                              | Checkboxes                                                 |
| `boolean`     | `true_label`, `false_label`              |                                                            |

**Dropped from v0.1:** `rank` (drag to reorder). Not worth building without a real use.

A card counts as **answered** when every `required: true` field has a value. That's the
only progress logic in the system.

### A/B compare

`compare` is a `choice` that knows it's picking between the panes of a `columns` block,
so the UI can highlight the winning pane and put the buttons under the right columns:

```jsonc
{
  "type": "columns",
  "columns": [
    {
      "label": "A",
      "blocks": [{ "type": "text", "format": "pre", "text": "..." }],
    },
    {
      "label": "B",
      "blocks": [{ "type": "text", "format": "pre", "text": "..." }],
    },
  ],
}
```

```jsonc
{
  "id": "winner",
  "type": "compare",
  "required": true,
  "options": [
    { "value": "A", "label": "A is better" },
    { "value": "B", "label": "B is better" },
    { "value": "tie", "label": "Tie" },
  ],
}
```

---

## Summary — header stats

Optional. Declares the counters that made the triage page readable at a glance, without
the renderer knowing what any of the values mean:

```jsonc
{
  "progress": true,
  "counters": [
    { "label": "false alarms", "field": "verdict", "equals": "false_alarm" },
    { "label": "good catches", "field": "verdict", "equals": "good_catch" },
  ],
  "rates": [
    {
      "label": "false-alarm rate",
      "field": "verdict",
      "numerator": ["false_alarm"],
      "denominator": ["false_alarm", "good_catch"],
    },
  ],
}
```

---

## Answers

Written to disk continuously by the daemon — there's no Save button. Lives beside the
batch at `~/.guide/batches/<id>/answers.json`.

```jsonc
{
  "guide_version": "0.1.0", // format these answers are written in
  "batch_version": "0.1.0", // what the batch declared
  "viewer_version": "0.1.0", // what actually rendered it
  "degraded": false, // true if any block or field fell back
  "degraded_cards": [], // which ones, so Claude can discount them

  "batch_id": "01JQ8FQ2X7K3M9VB4H0TZC5RWD",
  "session_id": "00000000-0000-4000-8000-000000000000", // whose question this was
  "started_at": "2026-08-31T14:10:00Z",
  "updated_at": "2026-08-31T15:02:41Z",
  "complete": true, // flipped by the Done button; what `guide wait` waits on
  "stats": { "total": 17, "answered": 17 },

  "answers": [
    {
      "card_id": "1",
      "title": "Give me a chart of users who are partners vs not partners", // echoed
      "meta": { "run": 78, "check": "numeric_faithfulness" }, // echoed verbatim
      "values": { "verdict": "false_alarm", "comment": "31% is 37/118, fine." },
      "answered_at": "2026-08-31T14:12:03Z",
    },
  ],
}
```

`title` and `meta` are echoed so the answers file is readable **and** actionable on its
own — Claude shouldn't need the original batch in context to act on the results. A
deliberate redundancy, and worth the bytes.

`session_id` is what makes several concurrent sessions work: each one's `guide wait`
watches only its own file, and never wakes on someone else's answers.

The three version fields let Claude tell whether the human answered while looking at a
degraded render. See [versioning.md](versioning.md).

---

## Versioning

`guide_version` is full `major.minor.patch`, and it's the first key in the document.
Major mismatch is a hard error; minor-ahead renders with a visible per-card warning;
patch is always silent. The full contract, including how a degraded render is recorded
in the answers file so Claude knows the human saw less than the whole picture, is in
[versioning.md](versioning.md).

---

## Worked example

[`../examples/verifier-triage.batch.json`](../examples/verifier-triage.batch.json) is
the real triage page re-expressed in this format, **with synthetic data substituted** —
the original contains client data.
