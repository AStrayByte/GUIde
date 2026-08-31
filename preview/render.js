/* GUIde — preview mock: the renderer.
 *
 * The whole thesis of docs/architecture.md in ~500 lines:
 *
 *     render(batch)  -> a page of cards
 *     collect(page)  -> answers
 *
 * The renderer never learns the domain. It knows block types and field types;
 * anything domain-specific rides in `meta` and is echoed back untouched.
 */

const VIEWER = window.VIEWER_VERSION;

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

/* ── State ─────────────────────────────────────────────────────────────────── */

const state = {
  batches: window.BATCHES.slice(),
  done: window.DONE_BATCHES.slice(),
  activeId: window.BATCHES[0].id,
  answers: load(), // { [batchId]: { [cardId]: { [fieldId]: value } } }
  completed: {}, // { [batchId]: true }
  focus: null, // card id the keyboard acts on
  arrived: {}, // batches that landed this session, for the rail dot
};

function load() {
  try {
    return JSON.parse(localStorage.getItem("guide.preview") || "{}");
  } catch {
    return {};
  }
}
function save() {
  /* The real daemon writes answers.json here. In the mock, localStorage stands in —
     same contract: every change persists immediately, no Save button. */
  try {
    localStorage.setItem("guide.preview", JSON.stringify(state.answers));
  } catch {}
}

const active = () => state.batches.find((b) => b.id === state.activeId);
const answersFor = (bid) => (state.answers[bid] ||= {});

/* ── Tiny DOM helper ───────────────────────────────────────────────────────── */

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

const esc = (s) =>
  String(s).replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );

/* Deliberately minimal markdown — bold, code, headings, lists, pipe tables. */
function md(src) {
  const lines = String(src).split("\n");
  let out = "",
    inList = false,
    inTable = false;
  const inline = (s) =>
    esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");

  const closeList = () => {
    if (inList) {
      out += "</ul>";
      inList = false;
    }
  };
  const closeTable = () => {
    if (inTable) {
      out += "</tbody></table></div>";
      inTable = false;
    }
  };

  for (const line of lines) {
    if (/^\s*\|.*\|\s*$/.test(line)) {
      const cells = line
        .trim()
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      if (cells.every((c) => /^-{2,}$/.test(c))) continue; // separator row
      if (!inTable) {
        closeList();
        out +=
          '<div class="tablewrap"><table><thead><tr>' +
          cells.map((c) => `<th>${inline(c)}</th>`).join("") +
          "</tr></thead><tbody>";
        inTable = true;
      } else {
        out +=
          "<tr>" + cells.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>";
      }
      continue;
    }
    closeTable();
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        out += "<ul>";
        inList = true;
      }
      out += `<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`;
      continue;
    }
    closeList();
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      out += `<h${h[1].length + 2}>${inline(h[2])}</h${h[1].length + 2}>`;
      continue;
    }
    if (line.trim() === "") continue;
    out += `<p>${inline(line)}</p>`;
  }
  closeList();
  closeTable();
  return out;
}

/* ── Version gate ──────────────────────────────────────────────────────────── */

const parseV = (v) => String(v).split(".").map(Number);

/* Pre-1.0, minor acts as major — see docs/versioning.md. */
function versionCheck(batch) {
  const [bMaj, bMin] = parseV(batch.guide_version);
  const [vMaj, vMin] = parseV(VIEWER);
  if (bMaj !== vMaj) return { gate: "hard", why: "major" };
  if (bMaj === 0 && bMin !== vMin)
    return { gate: "hard", why: "pre-1.0 minor" };
  if (bMin > vMin) return { gate: "warn" };
  return { gate: "ok" };
}

/* ── Blocks ────────────────────────────────────────────────────────────────── */

function renderBlock(b, ctx) {
  if (!KNOWN_BLOCKS.has(b.type)) {
    ctx.degraded.push(`block \`${b.type}\``);
    return wrap(
      b,
      el(
        "div",
        { class: "fallback" },
        el(
          "div",
          { class: "msg" },
          `Unsupported block type \`${b.type}\` — this viewer is on ${VIEWER}.`,
        ),
        el(
          "details",
          {},
          el("summary", {}, "show raw JSON"),
          el("pre", { class: "pre" }, JSON.stringify(b, null, 2)),
        ),
      ),
    );
  }

  let body;
  switch (b.type) {
    case "text":
      body =
        b.format === "pre"
          ? el("pre", { class: "pre" }, b.text)
          : b.format === "markdown"
            ? el("div", { html: md(b.text) })
            : el("p", {}, b.text);
      break;

    case "callout":
      body = el(
        "div",
        { class: `callout ${b.tone || "info"}` },
        el("div", {}, b.text),
        b.footnote && el("div", { class: "fn" }, b.footnote),
      );
      break;

    case "code":
      body = el(
        "pre",
        { class: "pre codeblock" },
        b.language && el("span", { class: "lang" }, b.language),
        b.code,
      );
      break;

    case "table": {
      const cols = b.columns || Object.keys(b.rows?.[0] || {});
      body = el(
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
                cols.map((c) => el("th", {}, c)),
              ),
            ),
            el(
              "tbody",
              {},
              (b.rows || []).map((r) =>
                el(
                  "tr",
                  {},
                  cols.map((c) => {
                    const v = Array.isArray(r) ? r[cols.indexOf(c)] : r[c];
                    return el(
                      "td",
                      {},
                      v === null || v === undefined
                        ? el("span", { class: "null" }, "null")
                        : v === ""
                          ? el("span", { class: "null" }, "(empty)")
                          : String(v),
                    );
                  }),
                ),
              ),
            ),
          ),
        ),
        (b.note || b.truncated) &&
          el("div", { class: "tnote" }, b.note || "truncated"),
      );
      break;
    }

    case "keyvalue":
      body = el(
        "dl",
        { class: "kv" },
        (b.pairs || []).flatMap((p) => [
          el("dt", {}, p.key),
          el("dd", {}, String(p.value)),
        ]),
      );
      break;

    case "diff":
      body = el(
        "pre",
        { class: "pre diff" },
        String(b.diff)
          .split("\n")
          .map((l) =>
            el(
              "span",
              {
                class: l.startsWith("+")
                  ? "add"
                  : l.startsWith("-")
                    ? "del"
                    : l.startsWith("@@")
                      ? "hun"
                      : "",
              },
              l + "\n",
            ),
          ),
      );
      break;

    case "json":
      body = el("pre", { class: "pre" }, JSON.stringify(b.value, null, 2));
      break;

    case "image":
      body = el(
        "figure",
        { style: "margin:0" },
        el("img", { src: b.src, alt: b.alt || "" }),
        b.caption && el("figcaption", { class: "tnote" }, b.caption),
      );
      break;

    case "columns":
      body = el(
        "div",
        { class: "cols" },
        (b.columns || []).map((c) =>
          el(
            "div",
            { class: "pane", "data-pane": c.label },
            el("div", { class: "plabel" }, c.label),
            (c.blocks || []).map((sub) => renderBlock(sub, ctx)),
          ),
        ),
      );
      break;
  }
  return wrap(b, body);
}

function wrap(b, body) {
  if (b.collapsed) {
    return el(
      "div",
      { class: "block" },
      el(
        "details",
        { class: "blk" },
        el("summary", {}, b.label || "details"),
        el("div", { class: "body" }, body),
      ),
    );
  }
  return el(
    "div",
    { class: "block" },
    b.label && el("div", { class: "blabel" }, b.label),
    body,
  );
}

/* ── Fields ────────────────────────────────────────────────────────────────── */

function renderField(f, card, batch, ctx, rerender) {
  const vals = (answersFor(batch.id)[card.id] ||= {});

  if (!KNOWN_FIELDS.has(f.type)) {
    ctx.degraded.push(`field \`${f.type}\``);
    if (f.required) ctx.blocked = true;
    return el(
      "div",
      { class: "field" },
      el(
        "div",
        { class: "fallback" },
        el(
          "div",
          { class: "msg" },
          `Unsupported field type \`${f.type}\` — this viewer is on ${VIEWER}.` +
            (f.required
              ? " This field is required, so the card cannot be answered."
              : ""),
        ),
        el(
          "details",
          {},
          el("summary", {}, "show raw JSON"),
          el("pre", { class: "pre" }, JSON.stringify(f, null, 2)),
        ),
      ),
    );
  }

  const set = (v) => {
    vals[f.id] = v;
    save();
    rerender();
  };

  const optionRow = (multi) =>
    el(
      "div",
      { class: "opts" },
      (f.options || []).map((o) => {
        const on = multi
          ? (vals[f.id] || []).includes(o.value)
          : vals[f.id] === o.value;
        return el(
          "button",
          {
            class: `opt ${o.tone || ""} ${on ? "on" : ""}`,
            onclick: () => {
              if (!multi)
                return set(vals[f.id] === o.value ? undefined : o.value);
              const cur = new Set(vals[f.id] || []);
              cur.has(o.value) ? cur.delete(o.value) : cur.add(o.value);
              set([...cur]);
            },
          },
          o.label,
          o.key && el("kbd", {}, o.key),
        );
      }),
    );

  let control;
  switch (f.type) {
    case "choice":
    case "compare":
      control = optionRow(false);
      break;

    case "multichoice":
      control = optionRow(true);
      break;

    case "boolean":
      control = el(
        "div",
        { class: "opts" },
        [
          { v: true, l: f.true_label || "Yes", tone: "good", key: "y" },
          { v: false, l: f.false_label || "No", tone: "bad", key: "n" },
        ].map((o) =>
          el(
            "button",
            {
              class: `opt ${o.tone} ${vals[f.id] === o.v ? "on" : ""}`,
              onclick: () => set(vals[f.id] === o.v ? undefined : o.v),
            },
            o.l,
            el("kbd", {}, o.key),
          ),
        ),
      );
      break;

    case "rating": {
      const min = f.min ?? 1,
        max = f.max ?? 5;
      const nums = [];
      for (let i = min; i <= max; i++) nums.push(i);
      control = el(
        "div",
        { class: "rating" },
        f.labels?.[0] && el("span", { class: "rlab" }, f.labels[0]),
        nums.map((n) =>
          el(
            "button",
            {
              class: `opt ${vals[f.id] === n ? "on" : ""}`,
              onclick: () => set(vals[f.id] === n ? undefined : n),
            },
            String(n),
          ),
        ),
        f.labels?.[f.labels.length - 1] &&
          el("span", { class: "rlab" }, f.labels[f.labels.length - 1]),
      );
      break;
    }

    case "text": {
      const tag = f.multiline ? "textarea" : "input";
      const node = el(tag, {
        rows: f.multiline ? 2 : null,
        type: f.multiline ? null : "text",
        placeholder: f.placeholder || "",
        maxlength: f.max_length || null,
      });
      node.value = vals[f.id] || "";
      /* Continuous save — no Save button, exactly as the daemon behaves. */
      node.addEventListener("input", () => {
        vals[f.id] = node.value || undefined;
        save();
        paintProgress();
        paintRail();
      });
      control = node;
      break;
    }
  }

  return el(
    "div",
    { class: "field" },
    f.type !== "text" && f.prompt && el("div", { class: "rprompt" }, f.prompt),
    control,
  );
}

/* ── Cards ─────────────────────────────────────────────────────────────────── */

const responseFor = (card, batch) => card.response || batch.defaults?.response;

function fieldsOf(card, batch) {
  return responseFor(card, batch)?.fields || [];
}

/* A card is answered when every required field has a value — the only progress
   logic in the system. An unsupported required field can never satisfy this. */
function cardStatus(card, batch) {
  const vals = state.answers[batch.id]?.[card.id] || {};
  let blocked = false,
    answered = true;
  for (const f of fieldsOf(card, batch)) {
    if (!f.required) continue;
    if (!KNOWN_FIELDS.has(f.type)) {
      blocked = true;
      answered = false;
      continue;
    }
    const v = vals[f.id];
    if (
      v === undefined ||
      v === null ||
      v === "" ||
      (Array.isArray(v) && v.length === 0)
    )
      answered = false;
  }
  return { answered, blocked };
}

function renderCard(card, i, batch) {
  const ctx = { degraded: [], blocked: false };
  const rerender = () => repaintCard(card, i, batch);
  const resp = responseFor(card, batch);
  const status = cardStatus(card, batch);

  const node = el(
    "article",
    {
      class: `card ${status.answered ? "answered" : ""} ${status.blocked ? "blocked" : ""} ${state.focus === card.id ? "focus" : ""}`,
      id: `card-${card.id}`,
      tabindex: "0",
      onclick: () => {
        if (state.focus !== card.id) {
          state.focus = card.id;
          paintCards();
        }
      },
    },
    el(
      "div",
      { class: "card-top" },
      el("h2", {}, card.title || `Card ${card.id}`),
      el("span", { class: "card-n" }, `card ${i + 1} of ${batch.cards.length}`),
    ),
    card.tags?.length &&
      el(
        "div",
        { class: "tags" },
        card.tags.map((t) => el("span", { class: "tag" }, t)),
      ),
    (card.blocks || []).map((b) => renderBlock(b, ctx)),
    resp &&
      el(
        "div",
        { class: "resp" },
        resp.prompt &&
          el(
            "div",
            { class: "rprompt" },
            resp.prompt,
            fieldsOf(card, batch).some((f) => f.required) &&
              el("span", { class: "req" }, " *"),
          ),
        fieldsOf(card, batch).map((f) =>
          renderField(f, card, batch, ctx, rerender),
        ),
      ),
  );

  if (ctx.degraded.length) {
    node.dataset.degraded = ctx.degraded.join(", ");
  }
  /* Highlight the winning pane when a compare field has a pick. */
  const cmp = fieldsOf(card, batch).find((f) => f.type === "compare");
  if (cmp) {
    const pick = state.answers[batch.id]?.[card.id]?.[cmp.id];
    node
      .querySelectorAll(".pane")
      .forEach((p) =>
        p.classList.toggle("win", !!pick && p.dataset.pane === pick),
      );
  }
  return node;
}

function repaintCard(card, i, batch) {
  const old = document.getElementById(`card-${card.id}`);
  if (!old) return paintAll();
  old.replaceWith(renderCard(card, i, batch));
  paintProgress();
  paintRail();
}

/* ── Progress / summary ────────────────────────────────────────────────────── */

function tally(batch) {
  let answered = 0,
    blocked = 0;
  for (const c of batch.cards) {
    const s = cardStatus(c, batch);
    if (s.answered) answered++;
    if (s.blocked) blocked++;
  }
  return { answered, blocked, total: batch.cards.length };
}

function paintProgress() {
  const batch = active();
  if (!batch) return;
  const host = document.getElementById("stats");
  if (!host) return;
  const t = tally(batch);
  const vals = Object.values(state.answers[batch.id] || {});
  const count = (spec) =>
    vals.filter((v) => v[spec.field] === spec.equals).length;

  host.replaceChildren(
    el(
      "div",
      { class: "stat" },
      el("span", { class: "v" }, `${t.answered}/${t.total}`),
      el("span", { class: "k" }, "answered"),
    ),
    ...(batch.summary?.counters || []).map((c) =>
      el(
        "div",
        { class: `stat ${c.tone || ""}` },
        el("span", { class: "v" }, String(count(c))),
        el("span", { class: "k" }, c.label),
      ),
    ),
    ...(batch.summary?.rates || []).map((r) => {
      const num = vals.filter((v) => r.numerator.includes(v[r.field])).length;
      const den = vals.filter((v) => r.denominator.includes(v[r.field])).length;
      return el(
        "div",
        { class: "stat" },
        el(
          "span",
          { class: "v" },
          den ? Math.round((num / den) * 100) + "%" : "—",
        ),
        el("span", { class: "k" }, r.label),
      );
    }),
    ...(t.blocked
      ? [
          el(
            "div",
            { class: "stat bad" },
            el("span", { class: "v" }, String(t.blocked)),
            el("span", { class: "k" }, "blocked"),
          ),
        ]
      : []),
  );

  const bar = document.querySelector("#bar i");
  if (bar) bar.style.width = (t.total ? (t.answered / t.total) * 100 : 0) + "%";

  const done = document.getElementById("doneBtn");
  if (done) {
    const complete = t.answered === t.total - t.blocked && t.total > 0;
    done.disabled = !complete || !!state.completed[batch.id];
    done.textContent = state.completed[batch.id]
      ? "Marked done"
      : "Done — release to Claude";
    const st = document.getElementById("footStatus");
    if (st) {
      st.textContent = state.completed[batch.id]
        ? `complete: true · written to ~/.guide/batches/${batch.id.slice(0, 8)}…/answers.json`
        : t.blocked
          ? `${t.answered}/${t.total - t.blocked} answerable · ${t.blocked} blocked by unsupported fields · saved continuously`
          : `${t.answered}/${t.total} answered · saved continuously — no Save button`;
    }
  }
}

/* ── Rail ──────────────────────────────────────────────────────────────────── */

function paintRail() {
  const host = document.getElementById("rail-body");
  const waiting = state.batches.filter((b) => !state.completed[b.id]);
  const doneList = [
    ...state.batches
      .filter((b) => state.completed[b.id])
      .map((b) => ({
        id: b.id,
        title: b.title,
        repo: b.source?.repo,
        cards: b.cards.length,
        when: "just now",
      })),
    ...state.done,
  ];

  host.replaceChildren(
    el(
      "div",
      { class: "rail-head" },
      "Waiting",
      el("span", { class: "count" }, String(waiting.length)),
    ),
    ...waiting.map((b) => {
      const t = tally(b);
      const gate = versionCheck(b);
      return el(
        "button",
        {
          class: `batch-item ${b.id === state.activeId ? "active" : ""}`,
          onclick: () => select(b.id),
        },
        el(
          "span",
          { class: "t" },
          el("span", {
            class: `dot ${state.arrived[b.id] ? "new" : t.answered ? "" : "off"}`,
          }),
          b.title,
        ),
        el(
          "span",
          { class: "s" },
          `${b.source?.repo || "?"} · ${b.cards.length} card${b.cards.length === 1 ? "" : "s"}` +
            (gate.gate === "hard"
              ? " · unreadable"
              : t.answered
                ? ` · ${t.answered} done`
                : ""),
        ),
      );
    }),
    el(
      "div",
      { class: "rail-head" },
      "Done",
      el("span", { class: "count" }, String(doneList.length)),
    ),
    ...doneList.map((d) =>
      el(
        "button",
        {
          class: `batch-item done ${d.id === state.activeId ? "active" : ""}`,
          onclick: () =>
            state.batches.some((b) => b.id === d.id) && select(d.id),
        },
        el("span", { class: "t" }, el("span", { class: "dot off" }), d.title),
        el("span", { class: "s" }, `${d.repo} · ${d.cards} cards · ${d.when}`),
      ),
    ),
  );
}

/* ── Main pane ─────────────────────────────────────────────────────────────── */

function paintCards() {
  const batch = active();
  const host = document.getElementById("cards");
  host.replaceChildren(...batch.cards.map((c, i) => renderCard(c, i, batch)));
  paintProgress();
}

function paintAll() {
  const batch = active();
  const wrap = document.getElementById("wrap");
  const gate = versionCheck(batch);

  if (gate.gate === "hard") {
    wrap.replaceChildren(
      el(
        "div",
        { class: "gate" },
        el("div", { class: "big" }, "⨯"),
        el("h2", {}, "This batch can't be rendered safely"),
        el(
          "p",
          {},
          `It declares GUIde `,
          el("code", {}, batch.guide_version),
          ` and this viewer is `,
          el("code", {}, VIEWER),
          `.`,
        ),
        el(
          "p",
          {},
          gate.why === "pre-1.0 minor"
            ? "Pre-1.0, a minor bump is allowed to break the format — so this is treated as a major mismatch and refused outright."
            : "A major mismatch is a hard error.",
        ),
        el(
          "p",
          {},
          "Refusing to render beats rendering it wrong: a silently degraded review means someone judges on evidence they can't see, and an agent acts on that judgment.",
        ),
        el(
          "p",
          { style: "margin-top:14px" },
          el("code", {}, "npx guide@latest upgrade"),
        ),
      ),
    );
    paintRail();
    return;
  }

  wrap.replaceChildren(
    gate.gate === "warn" &&
      el(
        "div",
        { class: "banner" },
        el(
          "b",
          {},
          `This batch uses GUIde ${batch.guide_version}; this viewer is ${VIEWER}.`,
        ),
        el(
          "span",
          { class: "d" },
          "Some content may fall back. Every place it does says so, on the card where it happened.",
        ),
      ),
    el(
      "div",
      { class: "bhead" },
      el(
        "div",
        { class: "crumbs" },
        el("b", {}, batch.source?.repo || "—"),
        " / ",
        batch.source?.branch || "—",
        "  ·  ",
        batch.id.slice(0, 10),
        "…",
        "  ·  guide_version ",
        batch.guide_version,
      ),
      el("h1", {}, batch.title),
      batch.subtitle && el("div", { class: "sub" }, batch.subtitle),
      batch.instructions && el("div", { class: "instr" }, batch.instructions),
      el("div", { class: "stats", id: "stats" }),
      el("div", { class: "bar", id: "bar" }, el("i", {})),
    ),
    el("div", { id: "cards" }),
    el(
      "div",
      { class: "footer" },
      el("span", { class: "status", id: "footStatus" }),
      el(
        "span",
        { style: "display:flex;gap:8px" },
        el("button", { class: "btn", onclick: showAnswers }, "Copy JSON"),
        el(
          "button",
          {
            class: "btn primary",
            id: "doneBtn",
            onclick: () => {
              state.completed[batch.id] = true;
              paintRail();
              paintProgress();
            },
          },
          "Done",
        ),
      ),
    ),
  );

  paintCards();
  paintRail();
}

function select(id) {
  state.activeId = id;
  state.focus = null;
  delete state.arrived[id];
  paintAll();
  window.scrollTo({ top: 0 });
}

/* ── The answers file ──────────────────────────────────────────────────────── */

function buildAnswers(batch) {
  const degradedCards = [];
  for (const c of batch.cards) {
    const unknownBlock = (c.blocks || []).some(
      (b) => !KNOWN_BLOCKS.has(b.type),
    );
    const unknownField = fieldsOf(c, batch).some(
      (f) => !KNOWN_FIELDS.has(f.type),
    );
    if (unknownBlock || unknownField) degradedCards.push(c.id);
  }
  const t = tally(batch);
  const stored = state.answers[batch.id] || {};

  return {
    guide_version: VIEWER,
    batch_version: batch.guide_version,
    viewer_version: VIEWER,
    degraded: degradedCards.length > 0,
    degraded_cards: degradedCards,
    batch_id: batch.id,
    session_id: batch.source?.session_id,
    started_at: batch.created_at,
    updated_at: new Date().toISOString(),
    complete: !!state.completed[batch.id],
    stats: { total: t.total, answered: t.answered },
    answers: batch.cards
      .filter((c) => Object.keys(stored[c.id] || {}).length)
      .map((c) => ({
        card_id: c.id,
        title: c.title,
        meta: c.meta,
        values: stored[c.id],
        answered_at: new Date().toISOString(),
      })),
  };
}

function showAnswers() {
  const batch = active();
  const text = JSON.stringify(buildAnswers(batch), null, 2);
  const modal = el(
    "div",
    {
      class: "modal",
      onclick: (e) => {
        if (e.target === modal) modal.remove();
      },
    },
    el(
      "div",
      { class: "sheet" },
      el(
        "header",
        {},
        el("b", {}, `~/.guide/batches/${batch.id.slice(0, 12)}…/answers.json`),
        el(
          "span",
          { style: "display:flex;gap:8px" },
          el(
            "button",
            {
              class: "btn",
              onclick: (e) => {
                navigator.clipboard?.writeText(text);
                e.target.textContent = "Copied";
              },
            },
            "Copy",
          ),
          el(
            "button",
            { class: "btn", onclick: () => modal.remove() },
            "Close",
          ),
        ),
      ),
      el("div", { class: "scroll" }, el("pre", { class: "pre" }, text)),
    ),
  );
  document.body.append(modal);
}

/* ── Keyboard ──────────────────────────────────────────────────────────────── */

function firstChoiceField(card, batch) {
  return fieldsOf(card, batch).find((f) =>
    ["choice", "compare", "multichoice", "boolean", "rating"].includes(f.type),
  );
}

document.addEventListener("keydown", (e) => {
  if (/^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
  const batch = active();
  if (!batch || versionCheck(batch).gate === "hard") return;

  const idx = batch.cards.findIndex((c) => c.id === state.focus);

  if (e.key === "j" || e.key === "ArrowDown") {
    e.preventDefault();
    const next =
      batch.cards[Math.min(batch.cards.length - 1, idx + 1)] || batch.cards[0];
    state.focus = next.id;
    paintCards();
    document
      .getElementById(`card-${next.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (e.key === "k" || e.key === "ArrowUp") {
    e.preventDefault();
    const prev = batch.cards[Math.max(0, idx - 1)] || batch.cards[0];
    state.focus = prev.id;
    paintCards();
    document
      .getElementById(`card-${prev.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  if (idx < 0) return;
  const card = batch.cards[idx];
  const f = firstChoiceField(card, batch);
  if (!f) return;
  const vals = (answersFor(batch.id)[card.id] ||= {});

  if (f.type === "rating") {
    const n = Number(e.key);
    if (!Number.isNaN(n) && n >= (f.min ?? 1) && n <= (f.max ?? 5)) {
      vals[f.id] = n;
      save();
      repaintCard(card, idx, batch);
      advance(batch, idx);
    }
    return;
  }
  if (f.type === "boolean") {
    if (e.key === "y") vals[f.id] = true;
    else if (e.key === "n") vals[f.id] = false;
    else return;
    save();
    repaintCard(card, idx, batch);
    advance(batch, idx);
    return;
  }
  const opt = (f.options || []).find((o) => o.key === e.key);
  if (!opt) return;
  if (f.type === "multichoice") {
    const cur = new Set(vals[f.id] || []);
    cur.has(opt.value) ? cur.delete(opt.value) : cur.add(opt.value);
    vals[f.id] = [...cur];
  } else {
    vals[f.id] = opt.value;
  }
  save();
  repaintCard(card, idx, batch);
  if (f.type !== "multichoice") advance(batch, idx);
});

function advance(batch, idx) {
  const next = batch.cards[idx + 1];
  if (!next) return;
  state.focus = next.id;
  paintCards();
  document
    .getElementById(`card-${next.id}`)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ── Theme ─────────────────────────────────────────────────────────────────── */

function toggleTheme() {
  const root = document.documentElement;
  const next = root.dataset.theme === "light" ? "dark" : "light";
  root.dataset.theme = next;
  try {
    localStorage.setItem("guide.theme", next);
  } catch {}
  document.getElementById("themeBtn").textContent =
    next === "light" ? "dark" : "light";
}

/* ── A batch arriving mid-review ───────────────────────────────────────────── */

function arrive() {
  const b = window.INCOMING;
  if (state.batches.some((x) => x.id === b.id)) return;
  state.batches.push(b);
  state.arrived[b.id] = true;
  paintRail();

  /* Quiet toast. It never steals focus and never navigates you away —
     interrupting someone at card 11 of 17 is how you get bad answers. */
  const toast = el(
    "div",
    { class: "toast" },
    el("div", {}, `New batch: ${b.title}`),
    el(
      "span",
      { class: "s" },
      `${b.source.repo} · ${b.cards.length} cards · just now`,
    ),
    el(
      "button",
      {
        onclick: () => {
          toast.remove();
          select(b.id);
        },
      },
      "Open it",
    ),
  );
  document.body.append(toast);
  setTimeout(() => toast.remove(), 9000);
}

/* ── Boot ──────────────────────────────────────────────────────────────────── */

try {
  const saved = localStorage.getItem("guide.theme");
  if (saved) document.documentElement.dataset.theme = saved;
} catch {}

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("themeBtn").addEventListener("click", toggleTheme);
  document.getElementById("themeBtn").textContent =
    document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.getElementById("resetBtn").addEventListener("click", () => {
    state.answers = {};
    state.completed = {};
    save();
    paintAll();
  });
  paintAll();
  setTimeout(arrive, 12000);
});
