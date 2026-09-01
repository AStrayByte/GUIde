# ADR 0006 — The markdown block is safe by construction, plus a CSP

**Status:** accepted
**Date:** 2026-08-31
**Closes:** the open call flagged by the tech-architecture plan

## Context

`docs/format.md` gives the `text` block a `format` of `plain`, `pre` or
`markdown`. The preview mock implemented `markdown` with a ~30-line function that
builds an HTML string and assigns it to `innerHTML`.

Batch content is written by an agent, from data an agent gathered. That makes
this the one place in GUIde where text nobody hand-checked becomes markup. The
backlog called it out and asked for an explicit ruling rather than a default:
sanitise it, or drop `markdown` and keep `plain`/`pre`.

## Decision

**Keep `markdown`, and make it safe by construction rather than by sanitiser.
Then add a Content-Security-Policy that assumes the first defence has a bug.**

### 1. Escape first, then transform

`md()` escapes `&`, `<`, `>`, `"` and `'` in every fragment _before_ any
transform runs. The transforms that follow emit tags only from a fixed list —
`strong`, `em`, `code`, `p`, `h3`–`h6`, `ul`, `li`, `div`, `table`, `thead`,
`tbody`, `tr`, `th`, `td` — and the invariant is precisely this:

> **No tag, and no attribute value, ever derives from the source text.**

Every tag name and every attribute in the output is a compile-time constant in
`md()` itself. The one attribute that appears at all is the `class="tablewrap"`
on the wrapper around a pipe table, and it is a literal in the source of the
function. There is therefore no path by which a character in a batch becomes a
tag, an attribute, or a URL. The property is structural, not a blocklist to keep
up to date.

**Links are absent, and that is the reason.** An `href` is an attribute, an
attribute is a place to put `javascript:`, and a link is the first thing a
sanitiser has to get right. A batch is self-contained (`docs/format.md`, design
rule 5), so a link would have nowhere useful to point anyway.

### 2. A Content-Security-Policy that assumes the above is wrong

Every response from the daemon carries:

```
default-src 'none'; script-src 'self'; style-src 'self';
img-src 'self' data:; connect-src 'self';
base-uri 'none'; form-action 'none'; frame-ancestors 'none'
```

No inline script, no remote anything, no form target, no framing. If `md()` ever
does emit a tag it should not have, the injected markup has nowhere to go.

The policy also enforces a rule the architecture doc already states as a
principle — _no outbound requests from the page: no CDN, no fonts, no analytics,
no telemetry._ It is now a header rather than a habit.

`style-src 'self'` has one visible consequence: **no inline `style="…"`
attributes anywhere in the page**, since the browser drops them. Everything the
preview mock did inline is a class now, and `tests/test_web_assets.py` fails the
build if one creeps back in.

### 3. `image` blocks are data URIs or nothing

`docs/format.md` already required it; the renderer now enforces it, refusing any
`src` that is not `data:image/…` with a visible fallback. The CSP blocks remote
images regardless — refusing in the renderer is what turns a blank box into a
legible explanation.

## Why not the alternatives

- **Drop `markdown`, keep `plain`/`pre`.** Genuinely tempting, and it was the
  safest answer. But a `callout` explaining why a check exists reads far better
  with a bold phrase and a bullet list, and that callout is what makes a card
  answerable by someone who did not build the checker. The subset earns its keep,
  and it is thirty lines with no dependency.
- **Ship DOMPurify.** A dependency, a build step to vendor it, and a CDN
  reference the CSP would have to allow — all to sanitise output we generate
  ourselves from a fixed grammar. Sanitisers are for HTML you did not author.

## Consequences

- The markdown subset stays deliberately small. Adding a construct means
  re-checking the invariant above, and anything that would derive an attribute
  _value_ from the source needs a new ADR.
- The renderer never calls `innerHTML` anywhere else. Everything else is
  `document.createElement` and `textContent`, which is why a linter warning on
  the single `html:` path in `el()` is the right place to look.
- The page cannot load a web font or a CDN script even if someone adds one. That
  is a feature: it is how "nothing leaves the machine" stops being a promise and
  becomes a mechanism.
