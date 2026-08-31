# Versioning

## The declaration

`guide_version` is the **first key** in every batch and every answers file, and it's
required. Same idea as `<?xml version="1.0"?>` — it's read and checked _before_ any
other parsing happens, so a document from the future fails cleanly instead of
half-rendering.

```jsonc
{
  "guide_version": "1.2.0",
  "id": "verifier-triage-2026-08-31",
  ...
}
```

Full `major.minor.patch`. No ranges, no `^`, no `latest`.

## Why this matters more here than usual

For most formats, a version mismatch means an ugly page. For this one it means
**someone makes a judgment call on evidence they can't fully see** — and then an agent
acts on that judgment. A silently degraded render is worse than a hard failure, because
nobody finds out.

That single fact drives every rule below.

## What increments what

|           | Change                                                                                                                                                          | Example                           |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| **patch** | No format change at all. Renderer bugfix, doc fix, perf.                                                                                                        | Fixed table column widths         |
| **minor** | Purely additive. New block type, new field type, new optional key.                                                                                              | Added the `diff` block            |
| **major** | Anything that could make an existing batch render _wrong_: removing or renaming a key, changing what an existing key means, changing how answers join to cards. | `rows` becomes an array of arrays |

The bar for a major bump is deliberately painful. Additive-only is almost always
achievable, and the whole fallback design (below) exists so it stays achievable.

**Pre-1.0:** while the format is `0.x.y`, **minor acts as major** — `0.2.0` may break
`0.1.0`. Standard semver convention, and it's where we are now (`0.1.0`).

## Compatibility rules

The viewer declares what it supports. Given a batch at version `B` and a viewer
supporting `V`:

| Condition                 | Behavior                                                                                                                            |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `B.major > V.major`       | **Hard error.** Refuse to render. _"This batch needs GUIde ≥ 2.0; this is 1.4.2. Update GUIde."_                                    |
| `B.major < V.major`       | **Hard error**, unless the viewer ships an explicit compat reader for that major. It'll read exactly one major back and no further. |
| `B.minor > V.minor`       | **Warn, and render.** Unknown blocks and fields fall back visibly.                                                                  |
| `B.minor < V.minor`       | Silent. Forward compatibility is the point of additive-only minors.                                                                 |
| patch differs, either way | Silent, always.                                                                                                                     |

## Degrading loudly

A minor-ahead batch renders, but **every place it degraded says so, where it happened**:

- A banner at the top: _"This batch uses GUIde 1.6; this viewer is 1.4. 3 cards contain
  content it can't fully display."_
- On each affected card, in place of the block it couldn't draw: _"Unsupported block
  type `timeline` — this viewer is on 1.4."_ plus the raw JSON, collapsed. You can
  still read it, you just don't get the nice rendering.
- An **unsupported required field blocks that card**. If a card asks for a `rank`
  response and the viewer can't draw one, that card cannot be marked answered. Better an
  obviously-stuck card than a silently skipped one.

A banner alone is not enough. Someone scrolling to card 12 needs to know _at card 12_
that they're judging on partial evidence.

## Answers record what produced them

The answers file carries both versions:

```jsonc
{
  "guide_version": "1.2.0",           // the format the answers are written in
  "batch_version": "1.6.0",           // what the batch declared
  "viewer_version": "1.4.2",          // what actually rendered it
  "degraded": true,                   // true if anything fell back
  "degraded_cards": ["12", "14"],     // where
  ...
}
```

So Claude can tell that a human answered card 12 without seeing all of it, and weigh
that answer accordingly — or ask again after an update. This is the payoff for the
whole scheme.

## Version negotiation on write

Claude should write the **oldest version that expresses what it needs**, not always the
newest. A batch of plain choice cards is `1.0.0` and every viewer ever built can read
it. Only reach for a newer minor when you actually use something from it.

The skill can check the installed viewer's version (`guide --format-version`) and target
that. Cheap, and it means the mismatch path is rare rather than routine.
