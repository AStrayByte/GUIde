/* GUIde — preview mock: sample batches.
 *
 * ALL DATA HERE IS SYNTHETIC AND EXTREMELY SILLY ON PURPOSE. Loaded as a script
 * (not fetched) so the mock opens over file:// with no server, exactly like the
 * real single-file path.
 *
 * Between them these five batches exercise every block type, every field type,
 * the loud-degrade fallback, and the hard version gate.
 */

window.VIEWER_VERSION = "0.1.0";

window.BATCHES = [
  /* ───────────────────────────────────────────────────────── 1. the flagship */
  {
    guide_version: "0.1.0",
    id: "01JQ8FQ2X7K3M9VB4H0TZC5RWD",
    title: "Power-scaling triage",
    subtitle: "The lore checker filed 8 complaints. Was it right?",
    instructions:
      "A bot checks every power-scaling claim against on-screen feats. For each complaint: did the answer actually hold up (the bot cried wolf), or is it a genuine lore violation? Progress saves continuously — there is no Save button.",
    created_at: "2026-08-31T14:02:00Z",
    source: {
      agent: "claude-code",
      session_id: "00000000-0000-4000-8000-000000000000",
      cwd: "/Users/you/dev/search-api",
      repo: "search-api",
      branch: "eval-tooling",
      label: "power-scaling triage",
    },
    defaults: {
      response: {
        prompt: "Your ruling",
        fields: [
          {
            id: "verdict",
            type: "choice",
            required: true,
            options: [
              {
                value: "false_alarm",
                label: "✓ Bot cried wolf — answer was fine",
                tone: "good",
                key: "1",
              },
              {
                value: "good_catch",
                label: "✗ Real violation — answer was wrong",
                tone: "bad",
                key: "2",
              },
              {
                value: "unsure",
                label: "? Ask the fandom",
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
    summary: {
      progress: true,
      counters: [
        {
          label: "cried wolf",
          field: "verdict",
          equals: "false_alarm",
          tone: "good",
        },
        {
          label: "real violations",
          field: "verdict",
          equals: "good_catch",
          tone: "bad",
        },
        {
          label: "ask the fandom",
          field: "verdict",
          equals: "unsure",
          tone: "mute",
        },
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
        title: "Could Aang beat Superman in a fight?",
        tags: ["cross_franchise", "run 78"],
        meta: { run: 78, check: "cross_franchise" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every power-scaling claim must be traceable to an on-screen feat. A cross-franchise comparison needs at least one feat from each side, measured in comparable units. This fires when one side is doing vibes.",
            footnote:
              "claim 'Aang takes it' rests on 0 comparable feats · 'the Avatar State is basically a god' is not a unit",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Great question! Aang would **almost certainly win**. [1]\n\nHe has access to all four elements, the Avatar State, and — critically — **energybending**, which lets him remove someone's bending entirely. Superman's powers are basically bending if you squint, so Aang could just switch him off.\n\nAlso Aang can fly and Superman is weak to rocks.",
          },
          {
            type: "table",
            label: "The feats the agent actually had — 4 rows",
            collapsed: true,
            columns: ["character", "feat", "source", "comparable"],
            rows: [
              {
                character: "Aang",
                feat: "raised an island",
                source: "Book 3",
                comparable: true,
              },
              {
                character: "Aang",
                feat: "removed Ozai's bending",
                source: "Book 3",
                comparable: false,
              },
              {
                character: "Superman",
                feat: "moved a planet",
                source: "n/a — not in corpus",
                comparable: null,
              },
              {
                character: "Superman",
                feat: "weak to kryptonite",
                source: "n/a — not in corpus",
                comparable: null,
              },
            ],
            note: "'Superman is weak to rocks' is a load-bearing simplification",
          },
        ],
      },
      {
        id: "2",
        title: "Is Batman a metahuman?",
        tags: ["ability_ledger", "run 78"],
        meta: { run: 78, check: "ability_ledger" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Any ability attributed to a character must appear in that character's ability ledger. Invented abilities are how a wiki answer quietly becomes fan fiction.",
            footnote:
              "ability 'prep time' not found in ledger · nearest match: 'planning (non-superhuman)'",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "No — Batman has **no metahuman abilities**. [1] He relies entirely on training, technology, and **prep time**, which is technically a superpower if you think about it.",
          },
          {
            type: "table",
            label: "Ability ledger — 5 rows",
            collapsed: true,
            columns: ["ability", "metahuman", "first appearance"],
            rows: [
              {
                ability: "peak human conditioning",
                metahuman: false,
                "first appearance": "1939",
              },
              {
                ability: "detective skill",
                metahuman: false,
                "first appearance": "1939",
              },
              {
                ability: "planning (non-superhuman)",
                metahuman: false,
                "first appearance": "1940",
              },
              {
                ability: "budget",
                metahuman: null,
                "first appearance": "1939",
              },
              {
                ability: "prep time",
                metahuman: null,
                "first appearance": "not found",
              },
            ],
          },
        ],
      },
      {
        id: "3",
        title: "Who's faster, Quicksilver or the Flash?",
        tags: ["numeric_faithfulness", "run 91"],
        meta: { run: 91, check: "numeric_faithfulness" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every number in the answer must be traceable to the data rows — a value, a total, an average, or a difference of two of them. This fires when one isn't.",
            footnote:
              "stated '400% faster' has no recoverable base/final pair · rows give 1.2c and 3.1c, a 158% difference",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "The Flash, comfortably. He's roughly **400% faster** than Quicksilver [1], and he can also run so fast he goes back in time, which Quicksilver has only managed in a kitchen.",
          },
          {
            type: "table",
            label: "Top recorded speed — 2 rows",
            collapsed: true,
            columns: ["character", "top_speed_c", "franchise"],
            rows: [
              {
                character: "Quicksilver",
                top_speed_c: 1.2,
                franchise: "Marvel",
              },
              { character: "The Flash", top_speed_c: 3.1, franchise: "DC" },
            ],
            note: "3.1 / 1.2 = 2.58× · the answer said 5×",
          },
        ],
      },
      {
        id: "4",
        title: "Can Toph read the scroll?",
        tags: ["null_handling", "run 91"],
        meta: { run: 91, check: "null_handling" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Rows with null attribute values must be surfaced, not silently folded into a default. This fires when the answer assumes a value the data doesn't carry.",
            footnote: "toph.vision = null was read as 'normal'",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Yes — Toph reads the scroll aloud to the group and identifies the seal immediately. [1]",
          },
          {
            type: "table",
            label: "Character attributes — 3 rows",
            collapsed: true,
            columns: ["character", "vision", "seismic_sense"],
            rows: [
              { character: "Katara", vision: "normal", seismic_sense: false },
              { character: "Sokka", vision: "normal", seismic_sense: false },
              { character: "Toph", vision: null, seismic_sense: true },
            ],
            note: "null here means blind, not unknown. The schema has been arguing about this since Book 2.",
          },
        ],
      },
      {
        id: "5",
        title: "How many elements has Aang mastered?",
        tags: ["numeric_faithfulness", "run 104"],
        meta: { run: 104, check: "numeric_faithfulness" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every number in the answer must be traceable to the data rows.",
            footnote:
              "stated count 4 not reproducible from returned rows (mastered = true on 3)",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "By the end of Book 2, Aang has mastered **all four elements**. [1]",
          },
          {
            type: "table",
            label: "Bending progress at end of Book 2 — 4 rows",
            collapsed: true,
            columns: ["element", "mastered", "teacher"],
            rows: [
              { element: "air", mastered: true, teacher: "Monk Gyatso" },
              { element: "water", mastered: true, teacher: "Katara" },
              { element: "earth", mastered: true, teacher: "Toph" },
              { element: "fire", mastered: false, teacher: null },
            ],
            note: "mastered = true on 3 of 4 · fire has no teacher assigned yet",
          },
        ],
      },
      {
        id: "6",
        title: "Is this the same Groot?",
        tags: ["citation_coverage", "run 104"],
        meta: { run: 104, check: "citation_coverage" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: "Every factual sentence must carry a [n] citation pointing at a result set. Uncited claims are where the hallucinations hide.",
            footnote: "4 of 6 sentences carry no citation marker",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "Technically no. The original Groot died and the one we see afterwards grew from a cutting. [1]\n\nSo he's more of a son than a resurrection. Marvel has been fairly consistent about this. Most fans disagree. The Russo brothers have said different things in different interviews, which doesn't help.",
          },
          {
            type: "table",
            label: "Result set [1] — 3 rows",
            collapsed: true,
            columns: ["entity", "status", "continuity_note"],
            rows: [
              {
                entity: "Groot (original)",
                status: "deceased",
                continuity_note: "Vol. 1",
              },
              {
                entity: "Groot (sapling)",
                status: "active",
                continuity_note: "grown from cutting",
              },
              {
                entity: "Groot (teen)",
                status: "active",
                continuity_note: "same sapling, later",
              },
            ],
          },
        ],
      },
      {
        id: "7",
        title: "How many Robins have there been?",
        tags: ["unsupported_judgment", "run 118"],
        meta: { run: 118, check: "unsupported_judgment" },
        blocks: [
          {
            type: "callout",
            label: "Why this check exists",
            tone: "warn",
            text: 'An evaluative word ("main", "real", "proper") implies a threshold. If no threshold is in the data or in the question, the model invented one.',
            footnote: "'the real ones' applied without a canon filter in scope",
          },
          {
            type: "text",
            label: "The answer it complained about",
            format: "pre",
            text: "There have been **five** Robins, if you only count the real ones. [1] I'm not counting the ones from alternate continuities, or the one that was a duck.",
          },
          {
            type: "table",
            label: "Result set [1] — 5 rows",
            collapsed: true,
            columns: ["robin", "years", "continuity"],
            rows: [
              { robin: "Dick Grayson", years: "1940–1984", continuity: "main" },
              { robin: "Jason Todd", years: "1983–1988", continuity: "main" },
              { robin: "Tim Drake", years: "1989–2009", continuity: "main" },
              {
                robin: "Stephanie Brown",
                years: "2004–2005",
                continuity: "main",
              },
              { robin: "Damian Wayne", years: "2009–", continuity: "main" },
            ],
            truncated: true,
            note: "showing 5 of 11 rows · 6 rows filtered out by an undeclared continuity filter",
          },
        ],
      },
      {
        id: "8",
        title: "Summarise the Fire Nation's line of succession",
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
            text: "Here's the Fire Nation succession, most recent last:\n\n| Fire Lord | Reign | Notable for |\n| --- | --- | --- |\n| Sozin | 82 years | Started it |\n| Azulon | 51 years | Continued it |\n| Ozai | 6 years | Peak of it |\n| Zuko | ongoing | Apologising for it |\n\nZuko's reign is the only one that begins with a formal apology. [1]",
          },
          {
            type: "keyvalue",
            label: "Run context",
            collapsed: true,
            pairs: [
              { key: "run", value: "118" },
              { key: "model", value: "lore-agent v2.3" },
              { key: "latency", value: "4.1s" },
              { key: "result sets", value: "1" },
              { key: "honour", value: "restored" },
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
    title: "Canon drift",
    subtitle:
      "The summariser's output changed between v2.2 and v2.3 — intended or not?",
    instructions:
      "Each card is a lore summary whose wording changed after the prompt rewrite. Mark whether the new version is what you want, and tag what you think drove it.",
    created_at: "2026-08-31T14:40:00Z",
    source: {
      agent: "claude-code",
      session_id: "00000000-0000-4000-8000-000000000000",
      cwd: "/Users/you/dev/search-api",
      repo: "search-api",
      branch: "eval-tooling",
      label: "canon drift",
    },
    defaults: {
      response: {
        prompt: "Is the new version correct?",
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
              { value: "retcon", label: "Honestly? A retcon" },
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
        title: "Iroh's tea advice lost the tea",
        tags: ["case 07", "voice"],
        meta: { case: "07", suite: "voice" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ summary @@\n-Iroh advises Zuko to slow down, and offers him jasmine tea. [1]\n-The tea is doing a lot of narrative work here.\n+Iroh provides emotional support to Zuko. [1]",
          },
          {
            type: "keyvalue",
            label: "Case",
            pairs: [
              {
                key: "question",
                value: "What does Iroh tell Zuko in the tea shop?",
              },
              { key: "rows returned", value: "3" },
              { key: "first seen", value: "run 112" },
              { key: "tea mentioned", value: "no (was: yes)" },
            ],
          },
        ],
      },
      {
        id: "r2",
        title: "The snap now affects a different denominator",
        tags: ["case 12", "numbers"],
        meta: { case: "12", suite: "numbers" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ summary @@\n-Thanos eliminated **half of all living things** in the universe. [1]\n+Thanos eliminated **half of all people**. [1]",
          },
          {
            type: "callout",
            tone: "bad",
            text: "This one is not a formatting nit. 'All living things' and 'all people' differ by roughly every plant, and the fandom will absolutely notice.",
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
            diff: "@@ summary @@\n-Zuko joins the team in Book 3. [1] Katara forgives him last. [1]\n+Zuko joins the team in Book 3. Katara forgives him last.\n+\n+[1]",
          },
        ],
      },
      {
        id: "r4",
        title: "Unnamed past Avatar now labelled 'Avatar Yangchen'",
        tags: ["case 23", "null handling"],
        meta: { case: "23", suite: "nulls" },
        blocks: [
          {
            type: "diff",
            label: "v2.2 → v2.3",
            diff: "@@ summary @@\n-| (unnamed air nomad avatar) | ~350 BG |\n+| Avatar Yangchen | ~350 BG |",
          },
          {
            type: "callout",
            tone: "good",
            text: "This looks like a deliberate improvement from the prompt rewrite — confirming it so it stops surfacing as a diff every run.",
          },
        ],
      },
      {
        id: "r5",
        title: "Answers to 'who would win' grew ~40% longer",
        tags: ["case 31", "verbosity"],
        meta: { case: "31", suite: "verbosity" },
        blocks: [
          {
            type: "table",
            label: "Token counts across 8 versus-question cases",
            columns: ["case", "matchup", "v2.2", "v2.3", "delta"],
            rows: [
              {
                case: "31a",
                matchup: "Thor vs Superman",
                "v2.2": 128,
                "v2.3": 181,
                delta: "+41%",
              },
              {
                case: "31b",
                matchup: "Azula vs Zuko",
                "v2.2": 96,
                "v2.3": 142,
                delta: "+48%",
              },
              {
                case: "31c",
                matchup: "Hulk vs Doomsday",
                "v2.2": 155,
                "v2.3": 199,
                delta: "+28%",
              },
              {
                case: "31d",
                matchup: "Appa vs Falkor",
                "v2.2": 110,
                "v2.3": 168,
                delta: "+53%",
              },
            ],
            truncated: true,
            note: "showing 4 of 8 rows · the Appa one got genuinely heated",
          },
        ],
      },
    ],
  },

  /* ─────────────────────────────────────────── 3. another repo, another shape */
  {
    guide_version: "0.1.0",
    id: "01JQ8FZK9M6R2TXH8B3EQY7NVP",
    title: "Bending API doc gaps",
    subtitle: "Which of these undocumented endpoints actually matter?",
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
        title: "POST /v1/benders/:id/bloodbend",
        tags: ["no description", "3 callers", "ethically fraught"],
        meta: { path: "/v1/benders/:id/bloodbend", callers: 3 },
        blocks: [
          {
            type: "code",
            label: "Handler",
            language: "typescript",
            code: "router.post('/v1/benders/:id/bloodbend', requireFullMoon, async (req, res) => {\n  const bender = await store.get(req.params.id)\n  if (!bender) return res.status(404).end()\n  if (bender.element !== 'water') return res.status(403).json({ error: 'wrong element' })\n  await bender.assertControl(req.body.target)\n  res.json({ ok: true, regrets: 1 })\n})",
          },
          {
            type: "text",
            format: "markdown",
            text: "Gated behind `requireFullMoon`, which is the only middleware in the codebase that calls an **astronomy API**. Undocumented, three callers, and nobody can remember writing it.",
          },
        ],
      },
      {
        id: "d2",
        title: "GET /v1/avatar/state",
        tags: ["no description", "0 callers"],
        meta: { path: "/v1/avatar/state", callers: 0 },
        blocks: [
          {
            type: "code",
            label: "Handler",
            language: "typescript",
            code: "router.get('/v1/avatar/state', (_req, res) =>\n  res.json({ active: false, glowing: false, pastLives: 9999, uptime: process.uptime() }))",
          },
          {
            type: "callout",
            tone: "mute",
            text: "Nothing in the repo calls this. It may exist only for a smoke test that was deleted. `pastLives` is hardcoded, which feels like it should be somebody's problem.",
          },
        ],
      },
      {
        id: "d3",
        title: "DELETE /v1/nations/:id",
        tags: ["no description", "1 caller", "irreversible"],
        meta: { path: "/v1/nations/:id", callers: 1 },
        blocks: [
          {
            type: "text",
            format: "markdown",
            text: "Backs `guide clean`. Deletes the whole nation outright — **no archive path**, which is the behaviour open question 5 is still arguing about. Has been called exactly once, in 100 AG.",
          },
          {
            type: "json",
            label: "Response shape",
            collapsed: true,
            value: {
              deleted: true,
              id: "air-nomads",
              survivors: 1,
              freed_bytes: 48211,
              reversible: false,
            },
          },
        ],
      },
      {
        id: "d4",
        title: "GET /v1/spirits?since=",
        tags: ["partially documented", "6 callers"],
        meta: { path: "/v1/spirits", callers: 6 },
        blocks: [
          {
            type: "text",
            format: "markdown",
            text: "The endpoint is documented; the `since` parameter is not. It takes an **ISO-8601 timestamp** and is what the page's poll loop uses to notice a new spirit without refetching the entire Spirit World.",
          },
          {
            type: "code",
            label: "Example",
            language: "bash",
            code: "curl '127.0.0.1:7777/v1/spirits?since=2026-08-31T15:00:00Z'",
          },
        ],
      },
    ],
  },

  /* ───────────────────────────── 4. exercises the loud-degrade fallback path */
  {
    guide_version: "0.1.0",
    id: "01JQ8G4D3V8W5YKN1C7FPS2MRB",
    title: "Catchphrase A/B",
    subtitle: "Two phrasings, identical scene. Which one ships?",
    instructions:
      "Pick a winner and say how confident you are. Two cards here use content this viewer doesn't know how to draw — that's deliberate, so you can see how it degrades.",
    created_at: "2026-08-31T15:20:00Z",
    source: {
      agent: "claude-code",
      session_id: "22222222-2222-4222-8222-222222222222",
      cwd: "/Users/you/dev/report-gen",
      repo: "report-gen",
      branch: "prompt-tuning",
      label: "catchphrase A/B",
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
        title: "Which version of Iroh's advice lands better?",
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
            text: "Two prompt variants produced these lines from the same scene. Pick the one you'd rather ship.",
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
                    text: "Failure is a teacher. Drink your tea. [1]",
                  },
                ],
              },
              {
                label: "B",
                blocks: [
                  {
                    type: "text",
                    format: "pre",
                    text: "It is important to draw wisdom from many different places. If you take it from only one place, it becomes rigid and stale. Also, your tea is getting cold. [1]",
                  },
                ],
              },
            ],
          },
          {
            type: "table",
            label: "Source scene — 2 rows",
            collapsed: true,
            columns: ["scene.id", "scene.location", "tea.temp_c"],
            rows: [
              {
                "scene.id": "S3E12",
                "scene.location": "Ba Sing Se tea shop",
                "tea.temp_c": 71,
              },
              {
                "scene.id": "S3E12",
                "scene.location": "Ba Sing Se tea shop",
                "tea.temp_c": 43,
              },
            ],
            note: "the second row is 20 minutes later, which is arguably the whole point",
          },
        ],
      },
      {
        id: "p2",
        title: "Which villain monologue is clearer?",
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
                    text: "I am inevitable.",
                  },
                ],
              },
              {
                label: "B",
                blocks: [
                  {
                    type: "text",
                    format: "pre",
                    text: "Given current population growth against finite resources, and having modelled this across 14,000,605 outcomes, I have concluded that a 50% reduction — applied uniformly and at random — is the only sustainable intervention. I am, in this specific and load-bearing sense, inevitable.",
                  },
                ],
              },
            ],
          },
          {
            /* Unknown block type — the viewer must degrade loudly, per versioning.md */
            type: "timeline",
            label: "Dramatic pause length across the run",
            events: [
              { at: "0.0s", what: "gauntlet raised" },
              { at: "2.4s", what: "meaningful stare" },
              { at: "6.1s", what: "snap" },
            ],
          },
        ],
      },
      {
        id: "p3",
        title: "Rank these four catchphrases",
        tags: ["prompt_ab", "run 106", "blocked"],
        meta: { run: 106, check: "prompt_ab" },
        blocks: [
          {
            type: "callout",
            tone: "warn",
            text: "This card asks for a response type this viewer can't draw. Per the versioning contract, an unsupported REQUIRED field blocks the card — it can never be marked answered, which is much better than being silently skipped.",
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
                {
                  value: "a",
                  label: "I'm the Avatar, you gotta deal with it!",
                },
                { value: "b", label: "I am Groot." },
                { value: "c", label: "It's me, Zuko. Hello." },
                { value: "d", label: "That's my secret — I'm always angry." },
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
    title: "Multiverse schema drift",
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
    title: "Sidekick naming review",
    repo: "search-api",
    cards: 12,
    when: "yesterday",
  },
  {
    id: "done-2",
    title: "Redemption arc tagging",
    repo: "report-gen",
    cards: 6,
    when: "yesterday",
  },
  {
    id: "done-3",
    title: "Cabbage merchant incidents",
    repo: "web-client",
    cards: 9,
    when: "2 days ago",
  },
];

/* Arrives 12s in, to show that a new batch never steals focus mid-card. */
window.INCOMING = {
  guide_version: "0.1.0",
  id: "01JQ8GJ0Y4A7C2FRT6M9WD5XHN",
  title: "Lore lookup misses",
  subtitle: "Questions where the right wiki page wasn't in the top 10",
  instructions:
    "Was the missed page genuinely relevant, or is the question just ambiguous?",
  created_at: "2026-08-31T15:58:00Z",
  source: {
    agent: "claude-code",
    session_id: "33333333-3333-4333-8333-333333333333",
    cwd: "/Users/you/dev/search-api",
    repo: "search-api",
    branch: "recall-work",
    label: "lore lookup misses",
  },
  defaults: {
    response: {
      prompt: "Was the missed page actually relevant?",
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
              label: "~ Question is ambiguous",
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
      title: '"who is the strongest bender"',
      tags: ["rank 24", "recall@10 miss"],
      meta: { query_id: "q-441", true_rank: 24 },
      blocks: [
        {
          type: "keyvalue",
          pairs: [
            {
              key: "expected page",
              value: "Avatar State (combat applications)",
            },
            { key: "actual rank", value: "24" },
            { key: "top hit", value: "List of cabbage-related incidents" },
          ],
        },
      ],
    },
    {
      id: "m2",
      title: '"why is he like that"',
      tags: ["rank 17", "recall@10 miss", "ambiguous"],
      meta: { query_id: "q-447", true_rank: 17 },
      blocks: [
        {
          type: "keyvalue",
          pairs: [
            { key: "expected page", value: "Zuko (character arc)" },
            { key: "actual rank", value: "17" },
            { key: "top hit", value: "Ozai (parenting)" },
            { key: "note", value: "arguably the top hit is correct" },
          ],
        },
      ],
    },
  ],
};
