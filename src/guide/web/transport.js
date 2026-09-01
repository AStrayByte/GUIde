/* GUIde — where answers go.
 *
 * Two implementations of one interface, so app.js never asks which world it is
 * in:
 *
 *   inbox()                        -> [summary]
 *   batch(id)                      -> batch document
 *   answers(id)                    -> answers document
 *   saveCard(id, cardId, payload)  -> void      (payload: {values, degraded})
 *   setComplete(id, complete, degradedCards) -> void
 *   subscribe(handler)             -> unsubscribe
 *
 * DaemonTransport is the product: the daemon owns the answers file, so it is
 * the authority on stats, echoed titles and timestamps.
 *
 * LocalTransport is the documented degenerate case — one batch, opened straight
 * off disk over file://, with localStorage standing in for the answers file. It
 * exists because a batch may contain client data and you may not want a process
 * running at all. It is a real fallback, not a mock: same renderer, same
 * contract, same continuous saving.
 */

(function (namespace) {
  "use strict";

  const API = namespace.ui.API;

  /* ── Daemon ────────────────────────────────────────────────────────────── */

  class DaemonTransport {
    constructor(origin) {
      this.kind = "daemon";
      this.origin = origin || "";
      this.stream = null;
    }

    async inbox() {
      return this.#json("GET", "/batches");
    }

    async batch(id) {
      return this.#json("GET", `/batches/${encodeURIComponent(id)}`);
    }

    async answers(id) {
      return this.#json("GET", `/batches/${encodeURIComponent(id)}/answers`);
    }

    async saveCard(id, cardId, payload) {
      await this.#json(
        "PUT",
        `/batches/${encodeURIComponent(id)}/answers/${encodeURIComponent(cardId)}`,
        {
          values: payload.values || {},
          degraded: Boolean(payload.degraded),
          viewer_version: namespace.render.VIEWER_VERSION,
        },
      );
    }

    async setComplete(id, complete, degradedCards) {
      await this.#json("POST", `/batches/${encodeURIComponent(id)}/complete`, {
        complete: Boolean(complete),
        degraded_cards: degradedCards || [],
      });
    }

    /* EventSource reconnects on its own, so "the daemon restarted" costs nothing
       here. Every event is a hint to refresh rather than a delta to apply, which
       is what makes a missed one harmless. */
    subscribe(handler) {
      this.stream = new EventSource(`${this.origin}${API}/events`);
      for (const kind of [
        "batch.added",
        "batch.answered",
        "batch.completed",
        "batch.removed",
      ]) {
        this.stream.addEventListener(kind, (event) => {
          handler(kind, safeParse(event.data));
        });
      }
      return () => this.stream && this.stream.close();
    }

    async #json(method, path, body) {
      const response = await fetch(`${this.origin}${API}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) throw new Error(await describe(response));
      return response.status === 204 ? null : response.json();
    }
  }

  /* ── file:// ───────────────────────────────────────────────────────────── */

  /* Holds exactly one batch — whichever the user opened — and keeps its answers
     in localStorage under the batch id. Same continuous-save contract as the
     daemon: every change persists immediately, and there is no Save button. */
  class LocalTransport {
    constructor(batch) {
      this.kind = "file";
      this.batchDocument = batch;
      this.key = `guide.answers.${batch.id || "adhoc"}`;
      this.state = readStorage(this.key) || { cards: {}, complete: false };
      this.listeners = new Set();
    }

    async inbox() {
      const counts = namespace.render.tally(
        this.batchDocument,
        this.state.cards,
      );
      return [
        {
          id: this.batchDocument.id,
          title: this.batchDocument.title,
          label: this.batchDocument.source?.label,
          repo: this.batchDocument.source?.repo,
          guide_version: this.batchDocument.guide_version,
          cards: counts.total,
          answered: counts.answered,
          complete: this.state.complete,
        },
      ];
    }

    async batch() {
      return this.batchDocument;
    }

    async answers() {
      return namespace.render.buildAnswers(
        this.batchDocument,
        this.state.cards,
        {
          complete: this.state.complete,
          startedAt: this.state.startedAt,
        },
      );
    }

    async saveCard(_id, cardId, payload) {
      if (payload.values && Object.keys(payload.values).length) {
        this.state.cards[cardId] = payload.values;
      } else {
        delete this.state.cards[cardId];
      }
      this.state.startedAt = this.state.startedAt || new Date().toISOString();
      this.#persist();
    }

    async setComplete(_id, complete, degradedCards) {
      this.state.complete = Boolean(complete);
      this.state.degradedCards = degradedCards || [];
      this.#persist();
    }

    subscribe(handler) {
      this.listeners.add(handler);
      return () => this.listeners.delete(handler);
    }

    #persist() {
      writeStorage(this.key, this.state);
      for (const listener of this.listeners) listener("batch.answered", {});
    }
  }

  /* ── Helpers ───────────────────────────────────────────────────────────── */

  async function describe(response) {
    try {
      const body = await response.json();
      if (typeof body.detail === "string") return body.detail;
    } catch {
      /* fall through to the status line */
    }
    return `${response.status} ${response.statusText}`;
  }

  function safeParse(text) {
    try {
      return JSON.parse(text);
    } catch {
      return {};
    }
  }

  /* Storage can throw outright in a private window, so every touch is guarded
     and a failure degrades to "answers only last as long as the page". */
  function readStorage(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || "null");
    } catch {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* no persistence available; the in-memory copy still works */
    }
  }

  namespace.DaemonTransport = DaemonTransport;
  namespace.LocalTransport = LocalTransport;
})((window.GUIde = window.GUIde || {}));
