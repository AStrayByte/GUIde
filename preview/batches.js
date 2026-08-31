/* GUIde — preview mock: sample batches.                                        */
/* ALL DATA HERE IS SYNTHETIC. Loaded as a script (not fetched) so the mock      */
/* opens over file:// with no server, exactly like the real single-file path.    */

window.VIEWER_VERSION = "0.1.0";

window.BATCHES = [
  /* ───────────────────────────────────────────────────────── 1. the flagship */
  {
    guide_version: "0.1.0",
    id: "01JQ8FQ2X7K3M9VB4H0TZC5RWD",
    title: "Verifier triage",
    subtitle: "Was the checker right to complain?",
    instructions:
      "For each complaint: was the answer actually fine (the checker cried wolf), or was it genuinely wrong (a real catch)? Progress saves continuously — there is no Save button.",
    created_at: "2026-08-31T14:02:00Z",
    source: {
      agent: "claude-code",
      session_id: "00000000-0000-4000-8000-000000000000",
      cwd: "/Users/you/dev/search-api",
      repo: "search-api",
      branch: "eval-tooling",
      label: "verifier triage",
    },
    defaults: {
      response: {
        prompt: "Your verdict",
        fields: [
          {
            id: "verdict",
            type: "choice",
            required: true,
            options: [
              {
                value: "false_alarm",
                label: "✓ False alarm — answer was fine",
                tone: "good",
                key: "1",
              },
              {
                value: "good_catch",
                label: "✗ Good catch — answer was wrong",
                tone: "bad",
                key: "2",
              },
              { value: "unsure", label: "? Not sure", tone: "mute", key: "3" },
            ],
          },
          {
            id: "comment",
            type: "text",
            multiline: true,
            placeholder: "Comments (optional)",
          },
        ],
      },
    },
    summary: {
      progress: true,
      counters: [
        {
          label: "false alarms",
          field: "verdict",
          equals: "false_alarm",
          tone: "good",
        },
        {
          label: "good catches",
          field: "verdict",
          equals: "good_catch",
          tone: "bad",
        },
        { label: "unsure", field: "verdict", equals: "unsure", tone: "mute" },
      ],
      rates: [
        {
          label: "false-alarm rate",
          field: "verdict",
          numerator: ["false_alarm"],
          denominator: ["false_alarm", "good_catch"],
        },
      ],
    },
    cards: [
      {
        id: "1",
        title: "Chart widget sales by region",
        tags: ["numeric_faithfulness", "run 78"],
        meta: { run: 78, check: "numeric_faithfulness" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every number in the answer must be traceable to the data rows — a value, a total, an average, or a difference of two of them. This fires when one isn't.",
            footnote:
              "stated percent 31% in answer has no recoverable base/final total pair to verify against",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Here's the breakdown of widget sales by region:\n\n- **North:** 37 units [1]\n- **South:** 68 units [1]\n- **Unassigned:** 13 units [1]\n\nOut of **118 total units**, North accounts for roughly **31%** of sales, with the majority (58%) in South and a small group (11%) unassigned. [1]",
          },
          {
            type: "table",
            label: "The data the agent actually had — 3 rows",
            collapsed: true,
            columns: ["sales.count", "sales.region"],
            rows: [
              { "sales.count": 68, "sales.region": "south" },
              { "sales.count": 37, "sales.region": "north" },
              { "sales.count": 13, "sales.region": null },
            ],
          },
        ],
      },
      {
        id: "2",
        title: "How did revenue trend last quarter?",
        tags: ["trend_guard", "run 91"],
        meta: { run: 91, check: "trend_guard" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: 'A directional claim ("up", "down", "growing") needs at least two comparable periods in the data. This fires when the answer asserts a trend from a single point.',
            footnote:
              "answer claims 'steady growth' but result set contains one period",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Revenue for Q3 came in at **$412,000** [1], continuing the steady growth we've seen through the year.",
          },
          {
            type: "table",
            label: "The data the agent actually had — 1 row",
            collapsed: true,
            columns: ["revenue.total", "revenue.quarter"],
            rows: [{ "revenue.total": 412000, "revenue.quarter": "2026-Q3" }],
          },
        ],
      },
      {
        id: "3",
        title: "List the top five accounts by open tickets",
        tags: ["citation_coverage", "run 78"],
        meta: { run: 78, check: "citation_coverage" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every factual sentence must carry a [n] citation pointing at a result set. Uncited claims are where hallucinations hide.",
            footnote: "3 of 7 sentences carry no citation marker",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "The five busiest accounts are Northwind (42 open), Contoso (38), Fabrikam (31), Tailspin (27) and Wingtip (22). [1]\n\nNorthwind's volume is unusual for an account of its size. It may be worth a check-in from the account team. Ticket volume tends to spike after a migration.",
          },
          {
            type: "table",
            label: "Result set [1] — 5 rows",
            collapsed: true,
            columns: ["account.name", "tickets.open", "account.seats"],
            rows: [
              {
                "account.name": "Northwind",
                "tickets.open": 42,
                "account.seats": 60,
              },
              {
                "account.name": "Contoso",
                "tickets.open": 38,
                "account.seats": 340,
              },
              {
                "account.name": "Fabrikam",
                "tickets.open": 31,
                "account.seats": 210,
              },
              {
                "account.name": "Tailspin",
                "tickets.open": 27,
                "account.seats": 95,
              },
              {
                "account.name": "Wingtip",
                "tickets.open": 22,
                "account.seats": 150,
              },
            ],
          },
        ],
      },
      {
        id: "4",
        title: "What's the average deal size this year?",
        tags: ["numeric_faithfulness", "run 91"],
        meta: { run: 91, check: "numeric_faithfulness" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every number in the answer must be traceable to the data rows.",
            footnote:
              "stated average 24,500 not reproducible from returned rows (computed 24,483.33)",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "The average deal size so far this year is about **$24,500** across 6 closed deals. [1]",
          },
          {
            type: "table",
            label: "Result set [1] — 6 rows",
            collapsed: true,
            columns: ["deal.id", "deal.amount", "deal.closed_at"],
            rows: [
              {
                "deal.id": "D-1041",
                "deal.amount": 18000,
                "deal.closed_at": "2026-02-11",
              },
              {
                "deal.id": "D-1055",
                "deal.amount": 31500,
                "deal.closed_at": "2026-03-02",
              },
              {
                "deal.id": "D-1067",
                "deal.amount": 22400,
                "deal.closed_at": "2026-04-19",
              },
              {
                "deal.id": "D-1088",
                "deal.amount": 27900,
                "deal.closed_at": "2026-05-30",
              },
              {
                "deal.id": "D-1102",
                "deal.amount": 19600,
                "deal.closed_at": "2026-06-22",
              },
              {
                "deal.id": "D-1119",
                "deal.amount": 27500,
                "deal.closed_at": "2026-07-08",
              },
            ],
            note: "mean = 24,483.33 · the answer rounded to 24,500",
          },
        ],
      },
      {
        id: "5",
        title: "Which regions are underperforming?",
        tags: ["unsupported_judgment", "run 104"],
        meta: { run: 104, check: "unsupported_judgment" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: 'An evaluative word ("underperforming", "poor", "healthy") implies a threshold. If no threshold is in the data or the question, the model invented one.',
            footnote:
              "'underperforming' applied without a target or benchmark in scope",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "**West** and **Central** are underperforming, at 12 and 15 units respectively against a company average of 29.5. [1]",
          },
          {
            type: "table",
            label: "Result set [1] — 4 rows",
            collapsed: true,
            columns: ["region", "units"],
            rows: [
              { region: "east", units: 54 },
              { region: "north", units: 37 },
              { region: "central", units: 15 },
              { region: "west", units: 12 },
            ],
          },
        ],
      },
      {
        id: "6",
        title: "Summarise this quarter's churn",
        tags: ["null_handling", "run 104"],
        meta: { run: 104, check: "null_handling" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Rows with null grouping keys must be surfaced, not silently folded into a bucket or dropped from a total.",
            footnote:
              "2 rows with churn.reason = null omitted from the narrative",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Nine accounts churned this quarter. The reasons were **price** (5) and **missing features** (4). [1]",
          },
          {
            type: "table",
            label: "Result set [1] — 4 rows",
            collapsed: true,
            columns: ["churn.reason", "churn.count"],
            rows: [
              { "churn.reason": "price", "churn.count": 5 },
              { "churn.reason": "missing_features", "churn.count": 4 },
              { "churn.reason": null, "churn.count": 2 },
              { "churn.reason": "", "churn.count": 0 },
            ],
            note: "11 accounts total, not 9",
          },
        ],
      },
      {
        id: "7",
        title: "Compare Q2 and Q3 headcount",
        tags: ["trend_guard", "run 118"],
        meta: { run: 118, check: "trend_guard" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "A directional claim needs at least two comparable periods in the data.",
            footnote: "two periods present — flagged on phrasing, not on data",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Headcount grew from **84** in Q2 to **91** in Q3 — an increase of 7 (8.3%). [1]",
          },
          {
            type: "table",
            label: "Result set [1] — 2 rows",
            collapsed: true,
            columns: ["headcount", "quarter"],
            rows: [
              { headcount: 84, quarter: "2026-Q2" },
              { headcount: 91, quarter: "2026-Q3" },
            ],
          },
        ],
      },
      {
        id: "8",
        title: "Show me pipeline by stage",
        tags: ["citation_coverage", "run 118"],
        meta: { run: 118, check: "citation_coverage" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every factual sentence must carry a [n] citation pointing at a result set.",
            footnote:
              "table rendered without a citation marker on the introducing sentence",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "markdown",
            text: "Here's the current pipeline by stage:\n\n| Stage | Deals | Value |\n| --- | --- | --- |\n| Discovery | 14 | $310k |\n| Proposal | 9 | $482k |\n| Negotiation | 4 | $265k |\n\nNegotiation is the thinnest stage right now. [1]",
          },
          {
            type: "keyvalue",
            label: "Run context",
            collapsed: true,
            pairs: [
              { key: "run", value: "118" },
              { key: "model", value: "answer-agent v2.3" },
              { key: "latency", value: "4.1s" },
              { key: "result sets", value: "1" },
            ],
          },
        ],
      },
    ],
  },

  /* ──────────────────────────────────────────── 2. a different response shape */
  {
    guide_version: "0.1.0",
    id: "01JQ8FT7B2N4P0WC5J1UAD6XKE",
    title: "Regression cases",
    subtitle: "Behaviour changed between v2.2 and v2.3 — intended or not?",
    instructions:
      "Each card is a case whose output changed after the prompt rewrite. Mark whether the new behaviour is what you want, and tag what drove it.",
    created_at: "2026-08-31T14:40:00Z",
    source: {
      agent: "claude-code",
      session_id: "00000000-0000-4000-8000-000000000000",
      cwd: "/Users/you/dev/search-api",
      repo: "search-api",
      branch: "eval-tooling",
      label: "regression cases",
    },
    defaults: {
      response: {
        prompt: "Is the new behaviour correct?",
        fields: [
          {
            id: "accept",
            type: "boolean",
            required: true,
            true_label: "✓ Intended",
            false_label: "✗ Regression",
          },
          {
            id: "cause",
            type: "multichoice",
            options: [
              { value: "prompt", label: "Prompt change" },
              { value: "schema", label: "Schema change" },
              { value: "model", label: "Model version" },
              { value: "flaky", label: "Non-deterministic" },
            ],
          },
          {
            id: "comment",
            type: "text",
            multiline: true,
            placeholder: "Notes (optional)",
          },
        ],
      },
    },
    summary: {
      progress: true,
      counters: [
        { label: "intended", field: "accept", equals: true, tone: "good" },
        { label: "regressions", field: "accept", equals: false, tone: "bad" },
      ],
    },
    cards: [
      {
        id: "r1",
        title: "Empty result set now returns a sentence, not a table",
        tags: ["case 07", "output shape"],
        meta: { case: "07", suite: "empty-results" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ answer @@\n-| Region | Units |\n-| --- | --- |\n-_(no rows)_\n+No sales records matched that filter. [1]",
          },
          {
            type: "keyvalue",
            label: "Case",
            pairs: [
              { key: "question", value: "Sales in Antarctica?" },
              { key: "rows returned", value: "0" },
              { key: "first seen", value: "run 112" },
            ],
          },
        ],
      },
      {
        id: "r2",
        title: "Currency symbol dropped from totals",
        tags: ["case 12", "formatting"],
        meta: { case: "12", suite: "formatting" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ answer @@\n-Total contract value: **$1,240,000** [1]\n+Total contract value: **1240000** [1]",
          },
          {
            type: "callout",
            tone: "bad",
            text: "Formatting regressions are cheap to miss and expensive in a customer-facing answer.",
          },
        ],
      },
      {
        id: "r3",
        title: "Citations moved from end-of-sentence to end-of-paragraph",
        tags: ["case 19", "citations"],
        meta: { case: "19", suite: "citations" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ answer @@\n-North sold 37 units. [1] South sold 68. [1]\n+North sold 37 units. South sold 68.\n+\n+[1]",
          },
        ],
      },
      {
        id: "r4",
        title: "Null grouping key now labelled 'Unassigned' instead of blank",
        tags: ["case 23", "null handling"],
        meta: { case: "23", suite: "nulls" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ answer @@\n-| (blank) | 13 |\n+| Unassigned | 13 |",
          },
          {
            type: "callout",
            tone: "good",
            text: "This one looks like a deliberate improvement from the prompt rewrite — confirming so it stops showing up as a diff.",
          },
        ],
      },
      {
        id: "r5",
        title: "Answer length grew ~40% on comparison questions",
        tags: ["case 31", "verbosity"],
        meta: { case: "31", suite: "verbosity" },
        blocks: [
          {
            type: "table",
            label: "Token counts across 8 comparison cases",
            columns: ["case", "v2.2", "v2.3", "delta"],
            rows: [
              { case: "31a", "v2.2": 128, "v2.3": 181, delta: "+41%" },
              { case: "31b", "v2.2": 96, "v2.3": 142, delta: "+48%" },
              { case: "31c", "v2.2": 155, "v2.3": 199, delta: "+28%" },
              { case: "31d", "v2.2": 110, "v2.3": 168, delta: "+53%" },
            ],
            truncated: true,
            note: "showing 4 of 8 rows",
          },
        ],
      },
    ],
  },

  /* ─────────────────────────────────────────── 3. another repo, another shape */
  {
    guide_version: "0.1.0",
    id: "01JQ8FZK9M6R2TXH8B3EQY7NVP",
    title: "API doc gaps",
    subtitle: "Which of these undocumented endpoints matter?",
    instructions:
      "The doc generator found endpoints with no description. Rate how badly each one needs writing up, and say who it's for.",
    created_at: "2026-08-31T15:05:00Z",
    source: {
      agent: "claude-code",
      session_id: "11111111-1111-4111-8111-111111111111",
      cwd: "/Users/you/dev/web-client",
      repo: "web-client",
      branch: "docs-sweep",
      label: "API doc gaps",
    },
    defaults: {
      response: {
        prompt: "How urgent?",
        fields: [
          {
            id: "priority",
            type: "rating",
            required: true,
            min: 1,
            max: 5,
            labels: ["skip", "", "", "", "must-have"],
          },
          {
            id: "audience",
            type: "choice",
            options: [
              { value: "external", label: "External devs", key: "e" },
              { value: "internal", label: "Internal only", key: "i" },
              {
                value: "deprecate",
                label: "Deprecate instead",
                tone: "bad",
                key: "d",
              },
            ],
          },
          {
            id: "comment",
            type: "text",
            multiline: true,
            placeholder: "What should it say?",
          },
        ],
      },
    },
    summary: { progress: true },
    cards: [
      {
        id: "d1",
        title: "POST /v1/batches/:id/reopen",
        tags: ["no description", "3 callers"],
        meta: { path: "/v1/batches/:id/reopen", callers: 3 },
        blocks: [
          {
            type: "code",
            label: "Handler",
            language: "typescript",
            code: "router.post('/v1/batches/:id/reopen', async (req, res) => {\n  const batch = await store.get(req.params.id)\n  if (!batch) return res.status(404).end()\n  batch.complete = false\n  await store.put(batch)\n  res.json({ ok: true })\n})",
          },
          {
            type: "text",
            format: "markdown",
            text: "Flips `complete` back to `false`. Undocumented, and it's the only way to undo a Done click. See **open question 10** — the docs currently say re-run rather than reopen.",
          },
        ],
      },
      {
        id: "d2",
        title: "GET /v1/daemon/health",
        tags: ["no description", "0 callers"],
        meta: { path: "/v1/daemon/health", callers: 0 },
        blocks: [
          {
            type: "code",
            label: "Handler",
            language: "typescript",
            code: "router.get('/v1/daemon/health', (_req, res) =>\n  res.json({ ok: true, uptime: process.uptime(), version: VERSION }))",
          },
          {
            type: "callout",
            tone: "mute",
            text: "Nothing in the repo calls this. It may exist only for a smoke test that was deleted.",
          },
        ],
      },
      {
        id: "d3",
        title: "DELETE /v1/batches/:id",
        tags: ["no description", "1 caller"],
        meta: { path: "/v1/batches/:id", callers: 1 },
        blocks: [
          {
            type: "text",
            format: "markdown",
            text: "Backs `guide clean`. Deletes the batch directory outright — **no archive path**, which is the behaviour open question 5 is still arguing about.",
          },
          {
            type: "json",
            label: "Response shape",
            collapsed: true,
            value: {
              deleted: true,
              id: "01JQ8FQ2X7K3M9VB4H0TZC5RWD",
              freed_bytes: 48211,
            },
          },
        ],
      },
      {
        id: "d4",
        title: "GET /v1/batches?since=",
        tags: ["partially documented", "6 callers"],
        meta: { path: "/v1/batches", callers: 6 },
        blocks: [
          {
            type: "text",
            format: "markdown",
            text: "The endpoint is documented; the `since` parameter is not. It takes an **ISO-8601 timestamp** and is what the page's poll loop uses to notice a new arrival without refetching the world.",
          },
          {
            type: "code",
            label: "Example",
            language: "bash",
            code: "curl '127.0.0.1:7777/v1/batches?since=2026-08-31T15:00:00Z'",
          },
        ],
      },
    ],
  },

  /* ───────────────────────────── 4. exercises the loud-degrade fallback path */
  {
    guide_version: "0.1.0",
    id: "01JQ8G4D3V8W5YKN1C7FPS2MRB",
    title: "Prompt A/B eval",
    subtitle: "Two phrasings, identical data. Which ships?",
    instructions:
      "Pick a winner and say how confident you are. Two cards here use content this viewer doesn't know how to draw — see how it degrades.",
    created_at: "2026-08-31T15:20:00Z",
    source: {
      agent: "claude-code",
      session_id: "22222222-2222-4222-8222-222222222222",
      cwd: "/Users/you/dev/report-gen",
      repo: "report-gen",
      branch: "prompt-tuning",
      label: "prompt A/B",
    },
    defaults: {
      response: {
        prompt: "Your pick",
        fields: [
          {
            id: "winner",
            type: "compare",
            required: true,
            options: [
              { value: "A", label: "A is better", key: "a" },
              { value: "B", label: "B is better", key: "b" },
              { value: "tie", label: "Tie", tone: "mute", key: "t" },
            ],
          },
          {
            id: "confidence",
            type: "rating",
            min: 1,
            max: 5,
            labels: ["coin flip", "", "", "", "certain"],
          },
          {
            id: "comment",
            type: "text",
            multiline: true,
            placeholder: "Why? (optional)",
          },
        ],
      },
    },
    summary: {
      progress: true,
      counters: [
        { label: "A wins", field: "winner", equals: "A" },
        { label: "B wins", field: "winner", equals: "B" },
        { label: "ties", field: "winner", equals: "tie", tone: "mute" },
      ],
    },
    cards: [
      {
        id: "p1",
        title: "Which phrasing of the revenue summary is better?",
        tags: ["prompt_ab", "run 104"],
        meta: {
          run: 104,
          check: "prompt_ab",
          variant_a: "terse-v3",
          variant_b: "narrative-v1",
        },
        blocks: [
          {
            type: "callout",
            tone: "info",
            label: "What you're deciding",
            text: "Two prompt variants produced these summaries from identical data. Pick the one you'd rather ship.",
          },
          {
            type: "columns",
            columns: [
              {
                label: "A",
                blocks: [
                  {
                    type: "text",
                    format: "pre",
                    text: "Q3 revenue: **$412,000**, up 8.4% on Q2's $380,000. [1]",
                  },
                ],
              },
              {
                label: "B",
                blocks: [
                  {
                    type: "text",
                    format: "pre",
                    text: "Revenue climbed to **$412,000** in Q3 — an 8.4% gain over the $380,000 posted in Q2, and the third consecutive quarter of growth. [1]",
                  },
                ],
              },
            ],
          },
          {
            type: "table",
            label: "Source data — 2 rows",
            collapsed: true,
            columns: ["revenue.total", "revenue.quarter"],
            rows: [
              { "revenue.total": 380000, "revenue.quarter": "2026-Q2" },
              { "revenue.total": 412000, "revenue.quarter": "2026-Q3" },
            ],
          },
        ],
      },
      {
        id: "p2",
        title: "Which error message is clearer?",
        tags: ["prompt_ab", "run 106"],
        meta: { run: 106, check: "prompt_ab" },
        blocks: [
          {
            type: "columns",
            columns: [
              {
                label: "A",
                blocks: [
                  {
                    type: "text",
                    format: "pre",
                    text: "No rows matched. Try widening the date range.",
                  },
                ],
              },
              {
                label: "B",
                blocks: [
                  {
                    type: "text",
                    format: "pre",
                    text: "That filter returned nothing between 2026-01-01 and 2026-03-31. The earliest record in this dataset is 2026-04-02.",
                  },
                ],
              },
            ],
          },
          {
            /* Unknown block type — the viewer must degrade loudly, per versioning.md */
            type: "timeline",
            label: "Response latency across the run",
            events: [
              { at: "0ms", what: "query parsed" },
              { at: "180ms", what: "rows fetched" },
              { at: "2.9s", what: "answer streamed" },
            ],
          },
        ],
      },
      {
        id: "p3",
        title: "Rank these four opening lines",
        tags: ["prompt_ab", "run 106", "blocked"],
        meta: { run: 106, check: "prompt_ab" },
        blocks: [
          {
            type: "callout",
            tone: "warn",
            text: "This card asks for a response type this viewer can't draw. Per the versioning contract, an unsupported REQUIRED field blocks the card — it can never be marked answered, which is better than being silently skipped.",
          },
        ],
        response: {
          prompt: "Order them best to worst",
          fields: [
            {
              /* Unknown field type, and required — must block the card */
              id: "order",
              type: "rank",
              required: true,
              options: [
                { value: "a", label: "Here's what I found." },
                { value: "b", label: "Short answer: revenue is up." },
                { value: "c", label: "Based on the data you have access to…" },
                { value: "d", label: "Revenue: $412,000 in Q3." },
              ],
            },
          ],
        },
      },
    ],
  },

  /* ─────────────────────────────────── 5. exercises the hard version gate */
  {
    guide_version: "0.9.0",
    id: "01JQ8GB6H1X9Z3QD4L2KTN8VJC",
    title: "Schema drift review",
    subtitle: "Written by a newer GUIde than this viewer",
    created_at: "2026-08-31T15:44:00Z",
    source: {
      agent: "claude-code",
      session_id: "22222222-2222-4222-8222-222222222222",
      cwd: "/Users/you/dev/report-gen",
      repo: "report-gen",
      branch: "prompt-tuning",
      label: "schema drift",
    },
    cards: [{ id: "x1", title: "unreadable", blocks: [] }],
  },
];

/* Batches already answered — they sit under Done in the rail. */
window.DONE_BATCHES = [
  {
    id: "done-1",
    title: "Peer-review findings",
    repo: "search-api",
    cards: 12,
    when: "yesterday",
  },
  {
    id: "done-2",
    title: "Tone calibration",
    repo: "report-gen",
    cards: 6,
    when: "yesterday",
  },
  {
    id: "done-3",
    title: "Null-handling sweep",
    repo: "web-client",
    cards: 9,
    when: "2 days ago",
  },
];

/* Arrives 12s in, to show that a new batch never steals focus mid-card. */
window.INCOMING = {
  guide_version: "0.1.0",
  id: "01JQ8GJ0Y4A7C2FRT6M9WD5XHN",
  title: "Retrieval misses",
  subtitle: "Queries where the right document wasn't in the top 10",
  instructions:
    "Was the document genuinely relevant, or is the query ambiguous?",
  created_at: "2026-08-31T15:58:00Z",
  source: {
    agent: "claude-code",
    session_id: "33333333-3333-4333-8333-333333333333",
    cwd: "/Users/you/dev/search-api",
    repo: "search-api",
    branch: "recall-work",
    label: "retrieval misses",
  },
  defaults: {
    response: {
      prompt: "Was the missed document actually relevant?",
      fields: [
        {
          id: "relevant",
          type: "choice",
          required: true,
          options: [
            {
              value: "yes",
              label: "✓ Relevant — a real miss",
              tone: "bad",
              key: "1",
            },
            { value: "no", label: "✗ Not relevant", tone: "good", key: "2" },
            {
              value: "ambig",
              label: "~ Query is ambiguous",
              tone: "mute",
              key: "3",
            },
          ],
        },
        {
          id: "comment",
          type: "text",
          multiline: true,
          placeholder: "Comments (optional)",
        },
      ],
    },
  },
  summary: { progress: true },
  cards: [
    {
      id: "m1",
      title: '"how do I reopen a finished batch"',
      tags: ["rank 24", "recall@10 miss"],
      meta: { query_id: "q-441", true_rank: 24 },
      blocks: [
        {
          type: "keyvalue",
          pairs: [
            {
              key: "expected doc",
              value: "docs/open-questions.md#10-reopening-answers",
            },
            { key: "actual rank", value: "24" },
            { key: "top hit", value: "docs/roadmap.md" },
          ],
        },
      ],
    },
    {
      id: "m2",
      title: '"port already in use"',
      tags: ["rank 17", "recall@10 miss"],
      meta: { query_id: "q-447", true_rank: 17 },
      blocks: [
        {
          type: "keyvalue",
          pairs: [
            {
              key: "expected doc",
              value: "docs/architecture.md#concurrency-honestly",
            },
            { key: "actual rank", value: "17" },
            {
              key: "top hit",
              value: "docs/decisions/0002-daemon-with-an-inbox.md",
            },
          ],
        },
      ],
    },
  ],
};
