/* GUIde — the page.
 *
 * Everything that is not rendering: which batch is open, what the rail shows,
 * where keystrokes go, and getting each change to the transport. render.js draws
 * a card; this file decides when.
 *
 * The one behavioural rule worth stating up front: a batch arriving while you
 * are mid-answer shows a quiet toast and appears in the rail. It never steals
 * focus and never navigates you away. Interrupting someone at card 11 of 17 is
 * how you get bad answers.
 */

(function (namespace) {
  "use strict";

  const { el, fill, renderCard, cardStatus, versionCheck, tally, summarize } =
    namespace.render;

  const SAVE_DEBOUNCE_MS = 120;
  const TOAST_MS = 9000;

  const state = {
    transport: null,
    summaries: [],
    activeId: null,
    batch: null,
    values: {}, // { [cardId]: { [fieldId]: value } }
    complete: false,
    focus: null,
    arrived: new Set(),
    pending: new Map(), // cardId -> timer, for debounced saves
    saving: new Map(), // cardId -> the write currently in flight for it
  };

  /* ── Boot ──────────────────────────────────────────────────────────────── */

  async function boot() {
    namespace.ui.wireThemeButton(document.getElementById("themeBtn"));

    if (location.protocol === "file:") {
      startFileMode();
      return;
    }

    state.transport = new namespace.DaemonTransport("");
    state.transport.subscribe(onServerEvent);
    document.getElementById("skillLink").hidden = false;
    await refreshInbox({
      select: new URLSearchParams(location.search).get("batch"),
    });
  }

  /* ── The inbox ─────────────────────────────────────────────────────────── */

  async function refreshInbox(options) {
    const settings = options || {};
    state.summaries = await state.transport.inbox();

    const wanted =
      settings.select ||
      state.activeId ||
      (state.summaries.find((one) => !one.complete) || state.summaries[0] || {})
        .id;

    paintRail();
    if (wanted && wanted !== state.activeId) await open(wanted);
    else if (!wanted) paintEmptyInbox();
  }

  async function open(id) {
    void flushPendingSaves();
    state.activeId = id;
    state.focus = null;
    state.arrived.delete(id);

    state.batch = await state.transport.batch(id);
    const answers = await state.transport.answers(id);
    state.values = Object.fromEntries(
      (answers.answers || []).map((record) => [record.card_id, record.values]),
    );
    state.complete = Boolean(answers.complete);

    paintRail();
    paintBatch();
    window.scrollTo({ top: 0 });
  }

  /* ── Change handling ───────────────────────────────────────────────────── */

  /* The daemon is told about every keystroke, but not on every keystroke: a
     short debounce per card collapses a burst of typing into one write while
     still guaranteeing the last value lands. Button clicks fall out of the same
     path — they are just a burst of one. */
  function onChange(cardId, fieldId, value) {
    const values = (state.values[cardId] ||= {});
    if (value === undefined) delete values[fieldId];
    else values[fieldId] = value;

    repaintCard(cardId);
    scheduleSave(cardId);
  }

  function scheduleSave(cardId) {
    clearTimeout(state.pending.get(cardId));
    state.pending.set(
      cardId,
      setTimeout(() => {
        state.pending.delete(cardId);
        save(cardId);
      }, SAVE_DEBOUNCE_MS),
    );
  }

  /* Fires every debounced save immediately and hands back their promises.
     `save()` reads the batch and the values synchronously before its first
     await, so the payloads are snapshotted here even if state moves on — which
     is what makes switching batches mid-keystroke safe. Callers that depend on
     the writes having *landed* must await what this returns. */
  function flushPendingSaves() {
    const inFlight = [];
    for (const [cardId, timer] of state.pending) {
      clearTimeout(timer);
      inFlight.push(save(cardId));
    }
    state.pending.clear();
    return Promise.all(inFlight);
  }

  /* Writes for one card are chained, so two of them cannot land out of order and
     leave the server holding the older value while the page shows the newer one.
     The payload is snapshotted here rather than read when the request goes out,
     which is what makes switching batches mid-keystroke safe: a queued write
     still carries the batch and the values it was queued for.

     Chained per card, so answering card 12 never waits on card 3. */
  function save(cardId) {
    const batch = state.batch;
    const card = batch.cards.find((one) => one.id === cardId);
    const payload = {
      values: { ...(state.values[cardId] || {}) },
      degraded: namespace.render.isDegraded(card, batch),
    };

    /* The status line belongs to whatever batch is on screen when the write
       settles — so a late failure from a batch you have already left does not
       shout on the one you are looking at now. */
    const report = (message) => {
      if (state.batch && state.batch.id === batch.id) setStatusLine(message);
    };

    const settled = (state.saving.get(cardId) || Promise.resolve())
      .then(() => state.transport.saveCard(batch.id, cardId, payload))
      .then(
        () => report(),
        (error) => report(`could not save: ${error.message}`),
      )
      .finally(() => {
        if (state.saving.get(cardId) === settled) state.saving.delete(cardId);
      });

    state.saving.set(cardId, settled);
    return settled;
  }

  /* Every card this viewer could not draw in full — including ones it blocked
     outright, which can never be answered and so can never report themselves
     through an answer record. This is the list the daemon cannot derive. */
  function degradedCardIds() {
    return state.batch.cards
      .filter((card) => namespace.render.isDegraded(card, state.batch))
      .map((card) => card.id);
  }

  /* ── Painting ──────────────────────────────────────────────────────────── */

  function paintRail() {
    const waiting = state.summaries.filter((one) => !one.complete);
    const done = state.summaries.filter((one) => one.complete);

    fill(
      document.getElementById("rail-body"),
      railHeading("Waiting", waiting.length),
      ...waiting.map(railItem),
      railHeading("Done", done.length),
      ...done.map(railItem),
    );
  }

  const railHeading = (text, count) =>
    el(
      "div",
      { class: "rail-head" },
      text,
      el("span", { class: "count" }, String(count)),
    );

  function railItem(summary) {
    const dot = state.arrived.has(summary.id)
      ? "new"
      : summary.answered
        ? ""
        : "off";
    const detail =
      `${summary.repo || "—"} · ${plural(summary.cards, "card")}` +
      (summary.answered ? ` · ${summary.answered} done` : "");

    return el(
      "button",
      {
        type: "button",
        class: [
          "batch-item",
          summary.id === state.activeId ? "active" : "",
          summary.complete ? "done" : "",
        ]
          .filter(Boolean)
          .join(" "),
        onclick: () => open(summary.id),
      },
      el(
        "span",
        { class: "t" },
        el("span", { class: `dot ${dot}` }),
        summary.title,
      ),
      el("span", { class: "s" }, detail),
    );
  }

  function paintEmptyInbox() {
    fill(
      document.getElementById("wrap"),
      el(
        "div",
        { class: "gate empty" },
        el("h2", {}, "Nothing waiting"),
        el("p", {}, "Push a batch and it will appear here."),
        el("p", {}, el("code", {}, "guide push ./questions.json")),
        el(
          "p",
          { class: "muted" },
          "No skill installed yet? ",
          el("a", { href: "/skill" }, "Install it for Claude"),
          ".",
        ),
      ),
    );
    paintRail();
  }

  function paintBatch() {
    const batch = state.batch;
    const wrap = document.getElementById("wrap");
    const gate = versionCheck(batch);

    if (gate.gate === "hard") {
      fill(wrap, versionGate(batch, gate));
      return;
    }

    fill(
      wrap,
      gate.gate === "warn" && versionBanner(batch),
      batchHeader(batch),
      el("div", { id: "cards" }),
      batchFooter(),
    );
    paintCards();
  }

  function batchHeader(batch) {
    return el(
      "div",
      { class: "bhead" },
      el(
        "div",
        { class: "crumbs" },
        el("b", {}, batch.source?.repo || "—"),
        " / ",
        batch.source?.branch || "—",
        "  ·  ",
        batch.id.slice(0, 10) + "…",
        "  ·  guide_version ",
        batch.guide_version,
      ),
      el("h1", {}, batch.title),
      batch.subtitle && el("div", { class: "sub" }, batch.subtitle),
      batch.instructions && el("div", { class: "instr" }, batch.instructions),
      el("div", { class: "stats", id: "stats" }),
      el("div", { class: "bar", id: "bar" }, el("i", {})),
    );
  }

  function batchFooter() {
    return el(
      "div",
      { class: "footer" },
      el("span", { class: "status", id: "footStatus" }),
      el(
        "span",
        { class: "row" },
        el(
          "button",
          { type: "button", class: "btn", onclick: showAnswers },
          "Copy JSON",
        ),
        el(
          "button",
          {
            type: "button",
            class: "btn primary",
            id: "doneBtn",
            onclick: markDone,
          },
          "Done",
        ),
      ),
    );
  }

  function paintCards() {
    const cards = state.batch.cards.map(buildCard);
    fill(document.getElementById("cards"), ...cards);
    paintProgress();
  }

  function buildCard(card, index) {
    return renderCard({
      card,
      index,
      batch: state.batch,
      values: state.values[card.id],
      focused: state.focus === card.id,
      onChange: (fieldId, value) => onChange(card.id, fieldId, value),
      onFocus: (id) => {
        if (state.focus === id) return;
        const previous = state.focus;
        state.focus = id;
        /* Repaint the two cards whose highlight changed, not all of them. A
           full repaint here would replace the very textarea the click was
           landing in, and take the caret with it. */
        repaintCard(previous);
        repaintCard(id);
      },
    });
  }

  function repaintCard(cardId) {
    if (cardId == null) return;
    const index = state.batch.cards.findIndex((one) => one.id === cardId);
    const existing = document.getElementById(`card-${cardId}`);
    if (index < 0 || !existing) return paintCards();

    const active = document.activeElement;
    const wasTyping = existing.contains(active) && isTextInput(active);
    if (wasTyping) {
      /* Never rebuild the node someone is typing into — it would take the caret
         with it. The counters still update. */
      paintProgress();
      return;
    }
    existing.replaceWith(buildCard(state.batch.cards[index], index));
    paintProgress();
  }

  function paintProgress() {
    const counts = tally(state.batch, state.values);
    const summary = summarize(state.batch, state.values);

    fill(
      document.getElementById("stats"),
      stat(`${counts.answered}/${counts.total}`, "answered"),
      ...summary.counters.map((one) => stat(one.value, one.label)),
      ...summary.rates.map((one) => stat(one.value, one.label)),
      counts.blocked ? stat(String(counts.blocked), "blocked", "bad") : null,
    );

    const bar = document.querySelector("#bar i");
    if (bar) {
      bar.style.width = counts.total
        ? (counts.answered / counts.total) * 100 + "%"
        : "0%";
    }

    const done = document.getElementById("doneBtn");
    if (done) {
      const answerable = counts.total - counts.blocked;
      done.disabled =
        state.complete || counts.answered < answerable || !counts.total;
      done.textContent = state.complete
        ? "Marked done"
        : "Done — release to Claude";
    }
    setStatusLine();
  }

  const stat = (value, label, tone) =>
    el(
      "div",
      { class: `stat ${tone || ""}` },
      el("span", { class: "v" }, value),
      el("span", { class: "k" }, label),
    );

  function setStatusLine(override) {
    const node = document.getElementById("footStatus");
    if (!node) return;
    if (override) {
      node.textContent = override;
      node.classList.add("bad");
      return;
    }
    node.classList.remove("bad");
    const counts = tally(state.batch, state.values);
    if (state.complete) {
      node.textContent = "complete: true · released to whichever session asked";
    } else if (counts.blocked) {
      node.textContent =
        `${counts.answered}/${counts.total - counts.blocked} answerable · ` +
        `${counts.blocked} blocked by unsupported fields · saved continuously`;
    } else {
      node.textContent = `${counts.answered}/${counts.total} answered · saved continuously — no Save button`;
    }
  }

  /* ── The version gate ──────────────────────────────────────────────────── */

  /* One sentence per reason the gate can slam shut. Exhaustive on purpose: a
     new `why` in render.js that fell through to the default would tell the
     reader the wrong thing about why their batch was refused, on the one screen
     whose whole argument is that refusing beats rendering it wrong. */
  const GATE_REASONS = {
    major: "A major mismatch is a hard error.",
    "pre-1.0 minor":
      "Pre-1.0, a minor bump is allowed to break the format — so this is treated as a major mismatch and refused outright.",
    malformed:
      "That version is not a major.minor.patch triple, so there is no way to tell what this batch expects.",
  };

  function versionGate(batch, gate) {
    return el(
      "div",
      { class: "gate" },
      el("div", { class: "big" }, "⨯"),
      el("h2", {}, "This batch can't be rendered safely"),
      el(
        "p",
        {},
        "It declares GUIde ",
        el("code", {}, batch.guide_version),
        " and this viewer is ",
        el("code", {}, namespace.render.VIEWER_VERSION),
        ".",
      ),
      el("p", {}, GATE_REASONS[gate.why] || GATE_REASONS.major),
      el(
        "p",
        {},
        "Refusing to render beats rendering it wrong: a silently degraded review means someone judges on evidence they can't see, and an agent acts on that judgment.",
      ),
      /* Upgrading helps when the batch is genuinely newer. It does nothing for a
         version string that was never valid, and saying so would send someone
         after the wrong fix. */
      el(
        "p",
        { class: "spaced" },
        gate.why === "malformed"
          ? "Fix guide_version in the batch, then push it again."
          : el("code", {}, "uv tool upgrade guide-cli"),
      ),
    );
  }

  const versionBanner = (batch) =>
    el(
      "div",
      { class: "banner" },
      el(
        "b",
        {},
        `This batch uses GUIde ${batch.guide_version}; this viewer is ${namespace.render.VIEWER_VERSION}.`,
      ),
      el(
        "span",
        { class: "d" },
        "Some content may fall back. Every place it does says so, on the card where it happened.",
      ),
    );

  /* ── Done, and the answers file ────────────────────────────────────────── */

  async function markDone() {
    /* Awaited, not fired and forgotten. `guide wait` returns the moment
       `complete` flips, so a comment still in flight when the flag lands is a
       comment Claude acts without. */
    await flushPendingSaves();
    await state.transport.setComplete(state.batch.id, true, degradedCardIds());
    state.complete = true;
    await refreshInbox();
    paintProgress();
  }

  async function showAnswers() {
    await flushPendingSaves();
    const answers = await state.transport.answers(state.batch.id);
    const text = JSON.stringify(answers, null, 2);

    const modal = el(
      "div",
      {
        class: "modal",
        onclick: (event) => {
          if (event.target === modal) modal.remove();
        },
      },
      el(
        "div",
        { class: "sheet" },
        el(
          "header",
          {},
          el("b", {}, `answers.json · ${state.batch.id.slice(0, 12)}…`),
          el(
            "span",
            { class: "row" },
            namespace.ui.copyButton(text),
            el(
              "button",
              { type: "button", class: "btn", onclick: () => modal.remove() },
              "Close",
            ),
          ),
        ),
        el("div", { class: "scroll" }, el("pre", { class: "pre" }, text)),
      ),
    );
    document.body.append(modal);
  }

  /* ── Live updates ──────────────────────────────────────────────────────── */

  /* Answers landing for the batch on screen are deliberately ignored: they are
     almost always this page's own writes echoing back, and reloading would take
     the caret out of whatever someone is typing. The rail still updates. */
  async function onServerEvent(kind, payload) {
    if (kind === "batch.added") {
      await refreshInbox();
      const summary = state.summaries.find((one) => one.id === payload.id);
      if (summary && summary.id !== state.activeId) announce(summary);
      return;
    }
    if (kind === "batch.removed" && payload.id === state.activeId) {
      state.activeId = null;
      await refreshInbox();
      return;
    }
    state.summaries = await state.transport.inbox();
    paintRail();
  }

  function announce(summary) {
    state.arrived.add(summary.id);
    paintRail();

    const toast = el(
      "div",
      { class: "toast" },
      el("div", {}, `New batch: ${summary.title}`),
      el(
        "span",
        { class: "s" },
        `${summary.repo || "—"} · ${plural(summary.cards, "card")} · just now`,
      ),
      el(
        "button",
        {
          type: "button",
          onclick: () => {
            toast.remove();
            open(summary.id);
          },
        },
        "Open it",
      ),
    );
    document.body.append(toast);
    setTimeout(() => toast.remove(), TOAST_MS);
  }

  /* ── Keyboard ──────────────────────────────────────────────────────────── */

  document.addEventListener("keydown", (event) => {
    if (!state.batch || isTextInput(event.target)) return;
    if (versionCheck(state.batch).gate === "hard") return;

    const cards = state.batch.cards;
    const index = cards.findIndex((card) => card.id === state.focus);

    if (event.key === "j" || event.key === "ArrowDown") {
      event.preventDefault();
      return focusCard(Math.min(cards.length - 1, index + 1));
    }
    if (event.key === "k" || event.key === "ArrowUp") {
      event.preventDefault();
      return focusCard(Math.max(0, index - 1));
    }
    if (index < 0) return;

    if (applyShortcut(cards[index], event.key)) {
      event.preventDefault();
      repaintCard(cards[index].id);
      scheduleSave(cards[index].id);
      if (shouldAdvance(cards[index])) focusCard(index + 1);
    }
  });

  /* Returns whether the key answered something, so the handler knows whether to
     swallow it. */
  function applyShortcut(card, key) {
    const field = keyableField(card);
    if (!field) return false;
    const values = (state.values[card.id] ||= {});

    if (field.type === "rating") {
      const number = Number(key);
      if (!namespace.render.ratingScale(field).includes(number)) return false;
      values[field.id] = values[field.id] === number ? undefined : number;
      return true;
    }
    if (field.type === "boolean") {
      const option = namespace.render
        .booleanOptions(field)
        .find((o) => o.key === key);
      if (!option) return false;
      values[field.id] =
        values[field.id] === option.value ? undefined : option.value;
      return true;
    }
    const option = (field.options || []).find((one) => one.key === key);
    if (!option) return false;

    if (field.type === "multichoice") {
      const chosen = new Set(values[field.id] || []);
      if (chosen.has(option.value)) chosen.delete(option.value);
      else chosen.add(option.value);
      values[field.id] = chosen.size ? [...chosen] : undefined;
    } else {
      values[field.id] =
        values[field.id] === option.value ? undefined : option.value;
    }
    return true;
  }

  /* Advance once the card is actually answered, and never on multichoice —
     you are still picking. */
  function shouldAdvance(card) {
    const field = keyableField(card);
    if (!field || field.type === "multichoice") return false;
    return cardStatus(card, state.batch, state.values[card.id]).answered;
  }

  function keyableField(card) {
    return namespace.render
      .fieldsOf(card, state.batch)
      .find((field) => namespace.render.KEYABLE_FIELDS.includes(field.type));
  }

  function focusCard(index) {
    const card = state.batch.cards[index];
    if (!card) return;
    state.focus = card.id;
    paintCards();
    document
      .getElementById(`card-${card.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const isTextInput = (node) =>
    Boolean(node) && /^(INPUT|TEXTAREA)$/.test(node.tagName || "");

  /* ── file:// mode ──────────────────────────────────────────────────────── */

  /* The degenerate case from ADR 0002, kept working rather than kept in a
     comment: one batch, no process, answers in localStorage. */
  function startFileMode() {
    document.getElementById("brandHost").textContent = "file://";
    const input = el("input", {
      type: "file",
      accept: "application/json,.json",
      class: "filepick",
      onchange: (event) => loadLocalFile(event.target.files[0]),
    });

    fill(
      document.getElementById("wrap"),
      el(
        "div",
        { class: "gate empty" },
        el("h2", {}, "Open a batch"),
        el(
          "p",
          {},
          "There is no daemon here, so pick a ",
          el("code", {}, "batch.json"),
          " and answer it straight off disk. Answers are kept in this browser and " +
            "copied out with the button at the bottom.",
        ),
        input,
        el(
          "p",
          { class: "muted" },
          "Run ",
          el("code", {}, "guide push"),
          " instead and the answers go back to Claude on their own.",
        ),
      ),
    );
    fill(document.getElementById("rail-body"), railHeading("No daemon", 0));
  }

  async function loadLocalFile(file) {
    if (!file) return;
    let batch;
    try {
      batch = JSON.parse(await file.text());
    } catch (error) {
      fill(
        document.getElementById("wrap"),
        el(
          "div",
          { class: "gate" },
          el("h2", {}, "That file is not valid JSON"),
          el("p", {}, error.message),
        ),
      );
      return;
    }
    batch.id = batch.id || file.name;
    state.transport = new namespace.LocalTransport(batch);
    state.transport.subscribe(() => paintRail());
    await refreshInbox({ select: batch.id });
  }

  const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;

  /* ── Go ────────────────────────────────────────────────────────────────── */

  namespace.ui.restoreTheme();

  window.addEventListener("DOMContentLoaded", () => {
    boot().catch((error) => {
      fill(
        document.getElementById("wrap"),
        el(
          "div",
          { class: "gate" },
          el("h2", {}, "Could not reach the daemon"),
          el("p", {}, error.message),
          el("p", {}, el("code", {}, "guide status")),
        ),
      );
    });
  });
})((window.GUIde = window.GUIde || {}));
