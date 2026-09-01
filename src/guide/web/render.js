/* GUIde — the renderer.
 *
 * The whole thesis of docs/architecture.md, in one file:
 *
 *     render(batch)  -> a page of cards
 *     collect(page)  -> answers
 *
 * Two rules hold this in shape.
 *
 * The renderer never learns your domain. It knows block types and field types;
 * anything domain-specific rides in `meta`, which it passes through untouched.
 *
 * The renderer never learns your transport either. Nothing in this file fetches,
 * saves, or reaches for global state. It is given a batch and the values already
 * answered, and it hands back DOM plus a callback for changes. That is what lets
 * the same code drive the daemon page and the file:// fallback.
 *
 * Classic script, not an ES module, on purpose: browsers refuse module imports
 * over file://, and opening a single batch straight off disk with no process
 * running is a documented feature. See docs/decisions/0007-no-build-step.md.
 */

(function (namespace) {
  "use strict";

  /* Bumped in lockstep with FORMAT_VERSION in src/guide/__init__.py.
     tests/test_web_assets.py fails the build if the two drift apart. */
  const VIEWER_VERSION = "0.1.0";

  const KNOWN_BLOCKS = new Set([
    "text",
    "callout",
    "code",
    "table",
    "keyvalue",
    "diff",
    "json",
    "image",
    "columns",
  ]);

  const KNOWN_FIELDS = new Set([
    "choice",
    "text",
    "rating",
    "compare",
    "multichoice",
    "boolean",
  ]);

  /* Field types a keystroke can answer, in the order the keyboard tries them. */
  const KEYABLE_FIELDS = [
    "choice",
    "compare",
    "multichoice",
    "boolean",
    "rating",
  ];

  /* ── DOM helpers ───────────────────────────────────────────────────────── */

  /* Everything is built as nodes and set as text. The single exception is the
     `markdown` block, which goes through md() below. */
  function el(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value == null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "html") node.innerHTML = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    }
    append(node, kids);
    return node;
  }

  function append(node, kids) {
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
  }

  /* replaceChildren() stringifies a falsy child into the text "false", unlike
     el(), which skips it. Everything that fills a container goes through here so
     a `condition && el(...)` that came out false disappears instead. */
  function fill(node, ...kids) {
    node.replaceChildren(...kids.flat().filter(Boolean));
    return node;
  }

  const esc = (text) =>
    String(text).replace(
      /[&<>"']/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character],
    );

  /* A deliberately small markdown subset: bold, italic, inline code, headings,
     unordered lists and pipe tables.

     This is the one place in GUIde where agent-authored text becomes markup, so
     it is safe by construction rather than by sanitiser. Every fragment is
     escaped *first*, and the transforms that follow can only emit tags from a
     fixed list — there is no path by which a character in the source becomes a
     tag, an attribute, or a URL. Links are absent for exactly that reason: an
     href is an attribute, and an attribute is a place to put javascript:.
     The daemon's Content-Security-Policy is the second, independent net.
     See docs/decisions/0006-markdown-by-construction.md. */
  function md(source) {
    const inline = (text) =>
      esc(text)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");

    let out = "";
    let inList = false;
    let inTable = false;

    const closeList = () => {
      if (inList) out += "</ul>";
      inList = false;
    };
    const closeTable = () => {
      if (inTable) out += "</tbody></table></div>";
      inTable = false;
    };

    for (const line of String(source).split("\n")) {
      if (/^\s*\|.*\|\s*$/.test(line)) {
        const cells = line
          .trim()
          .slice(1, -1)
          .split("|")
          .map((cell) => cell.trim());
        if (cells.every((cell) => /^-{2,}$/.test(cell))) continue; // separator row
        if (inTable) {
          out +=
            "<tr>" +
            cells.map((c) => `<td>${inline(c)}</td>`).join("") +
            "</tr>";
        } else {
          closeList();
          out +=
            '<div class="tablewrap"><table><thead><tr>' +
            cells.map((c) => `<th>${inline(c)}</th>`).join("") +
            "</tr></thead><tbody>";
          inTable = true;
        }
        continue;
      }
      closeTable();

      if (/^\s*[-*]\s+/.test(line)) {
        if (!inList) out += "<ul>";
        inList = true;
        out += `<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`;
        continue;
      }
      closeList();

      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      if (heading) {
        const level = heading[1].length + 2;
        out += `<h${level}>${inline(heading[2])}</h${level}>`;
        continue;
      }
      if (line.trim() !== "") out += `<p>${inline(line)}</p>`;
    }
    closeList();
    closeTable();
    return out;
  }

  /* ── The version gate ──────────────────────────────────────────────────── */

  /* Mirrors src/guide/versioning.py exactly. The duplication is deliberate — a
     batch opened over file:// has no daemon to ask — and both implementations
     are checked against tests/fixtures/version_compat.json. */
  function versionCheck(batch, viewer) {
    const declared = parseVersion(batch.guide_version);
    const supported = parseVersion(viewer || VIEWER_VERSION);
    /* Anything that is not exactly major.minor.patch is refused rather than
       guessed at. Python raises on the same input; over file:// there is no
       daemon to have raised first, which is the entire reason this check is
       written twice. */
    if (!declared || !supported) return { gate: "hard", why: "malformed" };

    const [batchMajor, batchMinor] = declared;
    const [viewerMajor, viewerMinor] = supported;

    if (batchMajor !== viewerMajor) return { gate: "hard", why: "major" };
    if (batchMajor === 0 && batchMinor !== viewerMinor)
      return { gate: "hard", why: "pre-1.0 minor" };
    if (batchMinor > viewerMinor) return { gate: "warn", why: "minor ahead" };
    return { gate: "ok", why: "compatible" };
  }

  /* Returns [major, minor, patch], or null if the string is not exactly that.
     Mirrors the pattern in src/guide/versioning.py. */
  function parseVersion(text) {
    const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(String(text));
    return match ? match.slice(1).map(Number) : null;
  }

  /* ── Blocks — what you read ────────────────────────────────────────────── */

  function renderBlock(block) {
    if (!KNOWN_BLOCKS.has(block.type)) {
      return wrapBlock(
        block,
        fallback(
          `Unsupported block type \`${block.type}\` — this viewer is on ${VIEWER_VERSION}.`,
          block,
        ),
      );
    }
    return wrapBlock(block, BLOCKS[block.type](block));
  }

  const BLOCKS = {
    text: (block) => {
      if (block.format === "pre")
        return el("pre", { class: "pre" }, block.text);
      if (block.format === "markdown")
        return el("div", { html: md(block.text) });
      return el("p", {}, block.text);
    },

    callout: (block) =>
      el(
        "div",
        { class: `callout ${block.tone || "info"}` },
        el("div", {}, block.text),
        block.footnote && el("div", { class: "fn" }, block.footnote),
      ),

    code: (block) =>
      el(
        "pre",
        { class: "pre codeblock" },
        block.language && el("span", { class: "lang" }, block.language),
        block.code,
      ),

    table: (block) => {
      const rows = Array.isArray(block.rows) ? block.rows : [];
      const columns = block.columns || Object.keys(rows[0] || {});
      return el(
        "div",
        {},
        el(
          "div",
          { class: "tablewrap" },
          el(
            "table",
            {},
            el(
              "thead",
              {},
              el(
                "tr",
                {},
                columns.map((c) => el("th", {}, c)),
              ),
            ),
            el(
              "tbody",
              {},
              rows.map((row) =>
                el(
                  "tr",
                  {},
                  columns.map((column, index) =>
                    el(
                      "td",
                      {},
                      cell(Array.isArray(row) ? row[index] : row[column]),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
        (block.note || block.truncated) &&
          el("div", { class: "tnote" }, block.note || "truncated"),
      );
    },

    keyvalue: (block) =>
      el(
        "dl",
        { class: "kv" },
        (block.pairs || []).flatMap((pair) => [
          el("dt", {}, pair.key),
          el("dd", {}, cell(pair.value)),
        ]),
      ),

    diff: (block) =>
      el(
        "pre",
        { class: "pre diff" },
        String(block.diff || "")
          .split("\n")
          .map((line) => el("span", { class: diffClass(line) }, line + "\n")),
      ),

    json: (block) =>
      el("pre", { class: "pre" }, JSON.stringify(block.value, null, 2)),

    /* The format says data URIs or nothing: a batch is self-contained, and a
       remote image would both leak that the batch was opened and fail offline.
       The daemon's CSP blocks remote sources anyway; refusing here is what makes
       the failure legible instead of a blank box.

       The subtype is an explicit allowlist rather than the broader `image/`
       prefix. `data:image/svg+xml` matching that prefix is harmless today — an
       SVG used as `<img src>` cannot run script — but that is a property of how
       it is used here, not of the format, and this is the one gate a future
       change to how images are rendered would otherwise have to remember to
       add back. Narrowing it now costs nothing a legitimate batch needs. */
    image: (block) => {
      if (
        !/^data:image\/(png|jpeg|gif|webp|avif)[;,]/i.test(
          String(block.src || ""),
        )
      ) {
        return fallback(
          "This image is not a data URI in a supported format (png, jpeg, gif, " +
            "webp, avif). Batches are self-contained, so remote images are not " +
            "loaded.",
          block,
        );
      }
      return el(
        "figure",
        { class: "figure" },
        el("img", { src: block.src, alt: block.alt || "" }),
        block.caption && el("figcaption", { class: "tnote" }, block.caption),
      );
    },

    columns: (block) =>
      el(
        "div",
        { class: "cols" },
        (block.columns || []).map((pane) =>
          el(
            "div",
            { class: "pane", "data-pane": pane.label },
            el("div", { class: "plabel" }, pane.label),
            (pane.blocks || []).map(renderBlock),
          ),
        ),
      ),
  };

  function cell(value) {
    if (value === null || value === undefined)
      return el("span", { class: "null" }, "null");
    if (value === "") return el("span", { class: "null" }, "(empty)");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function diffClass(line) {
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    if (line.startsWith("@@")) return "hun";
    return "";
  }

  /* Degrading loudly: the raw JSON stays available, collapsed, so a judgment can
     still be made — it just has to be made knowingly. */
  function fallback(message, raw) {
    return el(
      "div",
      { class: "fallback" },
      el("div", { class: "msg" }, message),
      el(
        "details",
        {},
        el("summary", {}, "show raw JSON"),
        el("pre", { class: "pre" }, JSON.stringify(raw, null, 2)),
      ),
    );
  }

  function wrapBlock(block, body) {
    if (block.collapsed) {
      return el(
        "div",
        { class: "block" },
        el(
          "details",
          { class: "blk" },
          el("summary", {}, block.label || "details"),
          el("div", { class: "body" }, body),
        ),
      );
    }
    return el(
      "div",
      { class: "block" },
      block.label && el("div", { class: "blabel" }, block.label),
      body,
    );
  }

  /* ── Fields — what you do ──────────────────────────────────────────────── */

  function renderField(field, values, onChange) {
    if (!KNOWN_FIELDS.has(field.type)) {
      /* An unsupported *required* field blocks its card outright — cardStatus()
         is what enforces that. Here it just has to say so, on the card. */
      return el(
        "div",
        { class: "field" },
        fallback(
          `Unsupported field type \`${field.type}\` — this viewer is on ${VIEWER_VERSION}.` +
            (field.required
              ? " This field is required, so the card cannot be answered."
              : ""),
          field,
        ),
      );
    }

    const set = (value) => onChange(field.id, value);
    const control = FIELDS[field.type](field, values[field.id], set);

    return el(
      "div",
      { class: "field" },
      field.label && el("div", { class: "flabel" }, field.label),
      control,
    );
  }

  const FIELDS = {
    choice: (field, value, set) => optionRow(field, value, set, false),
    compare: (field, value, set) => optionRow(field, value, set, false),
    multichoice: (field, value, set) => optionRow(field, value, set, true),

    boolean: (field, value, set) =>
      el(
        "div",
        { class: "opts" },
        booleanOptions(field).map((option) =>
          el(
            "button",
            {
              type: "button",
              class: `opt ${option.tone} ${value === option.value ? "on" : ""}`,
              onclick: () =>
                set(value === option.value ? undefined : option.value),
            },
            option.label,
            el("kbd", {}, option.key),
          ),
        ),
      ),

    rating: (field, value, set) =>
      el(
        "div",
        { class: "rating" },
        field.labels?.[0] && el("span", { class: "rlab" }, field.labels[0]),
        ratingScale(field).map((number) =>
          el(
            "button",
            {
              type: "button",
              class: `opt ${value === number ? "on" : ""}`,
              onclick: () => set(value === number ? undefined : number),
            },
            String(number),
          ),
        ),
        field.labels?.length > 1 &&
          el("span", { class: "rlab" }, field.labels[field.labels.length - 1]),
      ),

    /* Continuous save: every keystroke goes to the daemon, which is why there is
       no Save button anywhere in this UI. */
    text: (field, value, set) => {
      const node = el(field.multiline ? "textarea" : "input", {
        class: "textfield",
        rows: field.multiline ? 2 : null,
        type: field.multiline ? null : "text",
        placeholder: field.placeholder || "",
        maxlength: field.max_length || null,
      });
      node.value = value || "";
      node.addEventListener("input", () => set(node.value || undefined));
      return node;
    },
  };

  function optionRow(field, value, set, multiple) {
    const chosen = multiple ? new Set(value || []) : null;
    return el(
      "div",
      { class: "opts" },
      (field.options || []).map((option) => {
        const on = multiple ? chosen.has(option.value) : value === option.value;
        return el(
          "button",
          {
            type: "button",
            class: `opt ${option.tone || ""} ${on ? "on" : ""}`,
            onclick: () => set(toggle(field, value, option.value, multiple)),
          },
          option.label,
          option.key && el("kbd", {}, option.key),
        );
      }),
    );
  }

  /* Clicking the chosen option again clears it. Un-answering has to be possible:
     the alternative is a card you cannot take back, in a tool whose entire job is
     recording considered judgments. */
  function toggle(field, current, value, multiple) {
    if (!multiple) return current === value ? undefined : value;
    const next = new Set(current || []);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next.size ? [...next] : undefined;
  }

  const booleanOptions = (field) => [
    { value: true, label: field.true_label || "Yes", tone: "good", key: "y" },
    { value: false, label: field.false_label || "No", tone: "bad", key: "n" },
  ];

  function ratingScale(field) {
    const min = field.min ?? 1;
    const max = field.max ?? 5;
    return Array.from(
      { length: Math.max(0, max - min + 1) },
      (_, i) => min + i,
    );
  }

  /* ── Cards ─────────────────────────────────────────────────────────────── */

  const responseOf = (card, batch) => card.response || batch.defaults?.response;
  const fieldsOf = (card, batch) => responseOf(card, batch)?.fields || [];

  /* A card is answered when every required field has a value. That is the only
     progress logic in the system, and src/guide/batch.py says the same thing for
     the daemon's copy of the count. An unsupported required field can never
     satisfy it, which is the point. */
  function cardStatus(card, batch, values) {
    let blocked = false;
    let answered = true;
    for (const field of fieldsOf(card, batch)) {
      if (!field.required) continue;
      if (!KNOWN_FIELDS.has(field.type)) {
        blocked = true;
        answered = false;
        continue;
      }
      if (!hasValue((values || {})[field.id])) answered = false;
    }
    return { answered, blocked };
  }

  function hasValue(value) {
    if (value === undefined || value === null || value === "") return false;
    return !(Array.isArray(value) && value.length === 0);
  }

  /* Renders one card.
   *
   *   options.card     the card
   *   options.index    its position, for "card 4 of 17"
   *   options.batch    the batch it belongs to
   *   options.values   what has been answered so far, keyed by field id
   *   options.focused  whether the keyboard is acting on this card
   *   options.onChange (fieldId, value) => void
   *
   * Returns the DOM node. Whether the card degraded is deliberately NOT
   * returned: `isDegraded()` answers that without rendering, so the flag the
   * daemon is told about comes from one implementation whether the card is on
   * screen or is being collected by the file:// fallback.
   */
  function renderCard(options) {
    const { card, index, batch, values, focused, onChange, onFocus } = options;
    const response = responseOf(card, batch);
    const fields = fieldsOf(card, batch);
    const status = cardStatus(card, batch, values);

    const node = el(
      "article",
      {
        class: [
          "card",
          status.answered ? "answered" : "",
          status.blocked ? "blocked" : "",
          focused ? "focus" : "",
        ]
          .filter(Boolean)
          .join(" "),
        id: `card-${card.id}`,
        tabindex: "0",
        onclick: () => onFocus && onFocus(card.id),
      },
      el(
        "div",
        { class: "card-top" },
        el("h2", {}, card.title || `Card ${card.id}`),
        el(
          "span",
          { class: "card-n" },
          `card ${index + 1} of ${batch.cards.length}`,
        ),
      ),
      card.tags?.length &&
        el(
          "div",
          { class: "tags" },
          card.tags.map((tag) => el("span", { class: "tag" }, tag)),
        ),
      (card.blocks || []).map(renderBlock),
      response &&
        el(
          "div",
          { class: "resp" },
          response.prompt &&
            el(
              "div",
              { class: "rprompt" },
              response.prompt,
              fields.some((field) => field.required) &&
                el("span", { class: "req" }, " *"),
            ),
          fields.map((field) => renderField(field, values || {}, onChange)),
        ),
    );

    highlightWinningPane(node, fields, values);
    return node;
  }

  /* `compare` is a choice that knows it is picking between the panes of a
     `columns` block, so the pick is shown where the evidence is. */
  function highlightWinningPane(node, fields, values) {
    const comparison = fields.find((field) => field.type === "compare");
    if (!comparison) return;
    const pick = (values || {})[comparison.id];
    for (const pane of node.querySelectorAll(".pane")) {
      pane.classList.toggle("win", Boolean(pick) && pane.dataset.pane === pick);
    }
  }

  /* ── Progress ──────────────────────────────────────────────────────────── */

  function tally(batch, answers) {
    let answered = 0;
    let blocked = 0;
    for (const card of batch.cards) {
      const status = cardStatus(card, batch, answers[card.id]);
      if (status.answered) answered += 1;
      if (status.blocked) blocked += 1;
    }
    return { answered, blocked, total: batch.cards.length };
  }

  /* The header counters, declared by the batch and computed without the renderer
     knowing what any of the values mean. */
  function summarize(batch, answers) {
    const rows = Object.values(answers || {});
    const counters = (batch.summary?.counters || []).map((spec) => ({
      label: spec.label,
      tone: spec.tone,
      value: String(
        rows.filter((row) => row[spec.field] === spec.equals).length,
      ),
    }));
    const rates = (batch.summary?.rates || []).map((spec) => {
      const numerator = rows.filter((r) =>
        spec.numerator.includes(r[spec.field]),
      ).length;
      const denominator = rows.filter((r) =>
        spec.denominator.includes(r[spec.field]),
      ).length;
      return {
        label: spec.label,
        value: denominator
          ? Math.round((numerator / denominator) * 100) + "%"
          : "—",
      };
    });
    return { counters, rates };
  }

  /* ── The answers file ──────────────────────────────────────────────────── */

  /* Only used by the file:// fallback and the Copy JSON button. When a daemon is
     present it builds the real file — the browser must not be the authority on
     what an answers file looks like, or two implementations start to drift. */
  function buildAnswers(batch, answers, options) {
    const settings = options || {};
    const degradedCards = batch.cards
      .filter((card) => isDegraded(card, batch))
      .map((card) => card.id);
    const counts = tally(batch, answers);

    return {
      guide_version: VIEWER_VERSION,
      batch_version: batch.guide_version,
      viewer_version: VIEWER_VERSION,
      degraded: degradedCards.length > 0,
      degraded_cards: degradedCards,
      batch_id: batch.id,
      session_id: batch.source?.session_id,
      started_at: settings.startedAt,
      updated_at: new Date().toISOString(),
      complete: Boolean(settings.complete),
      stats: { total: counts.total, answered: counts.answered },
      answers: batch.cards
        .filter((card) => Object.keys(answers[card.id] || {}).length)
        .map((card) => ({
          card_id: card.id,
          title: card.title,
          meta: card.meta,
          values: answers[card.id],
          degraded: isDegraded(card, batch),
        })),
    };
  }

  function isDegraded(card, batch) {
    const unknownField = fieldsOf(card, batch).some(
      (f) => !KNOWN_FIELDS.has(f.type),
    );
    return unknownField || (card.blocks || []).some(blockDegrades);
  }

  /* Recurses through `columns` panes. A block this viewer cannot draw is no less
     invisible for being nested, and a shallow check would report exactly that
     case — the format's own answer to "show A next to B" — as a clean render. */
  function blockDegrades(block) {
    if (!KNOWN_BLOCKS.has(block.type)) return true;
    if (block.type !== "columns") return false;
    return (block.columns || []).some((pane) =>
      (pane.blocks || []).some(blockDegrades),
    );
  }

  /* ── Exports ───────────────────────────────────────────────────────────── */

  namespace.render = {
    VIEWER_VERSION,
    KNOWN_BLOCKS,
    KNOWN_FIELDS,
    KEYABLE_FIELDS,
    el,
    fill,
    esc,
    md,
    versionCheck,
    renderCard,
    cardStatus,
    fieldsOf,
    responseOf,
    tally,
    summarize,
    buildAnswers,
    isDegraded,
    hasValue,
    ratingScale,
    booleanOptions,
  };
})((window.GUIde = window.GUIde || {}));
