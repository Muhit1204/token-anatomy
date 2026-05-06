# Token Anatomy — Project Context & Development Tracker

> Last updated: 2026-05-06 (Session 9)
> Author: Md Muntasir Hossain (Munta)
> Status: Active development — v0.1 shipped to GitHub, roadmap ongoing

---

## 1. What This Project Is

**Token Anatomy** is a local, pure-Python analytics dashboard for Claude Code. It reads JSONL session files from `~/.claude/projects/` and renders a rich interactive dashboard in the browser — zero external dependencies, zero npm, zero pip installs.

Designed as a standalone open-source tool. Live at: https://github.com/Muhit1204/token-anatomy

---

## 2. Core Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Language | Pure Python 3.8+ stdlib only | No extra installs on any machine |
| Web server | `http.server` + `socketserver` | Built-in, zero deps |
| Frontend | Vanilla HTML/JS in `template.html` | Package structure, editable with real tooling |
| Charts | Chart.js 4.4.0 via CDN | No install, one `<script>` tag |
| Data source | `~/.claude/projects/**/*.jsonl` | Claude Code native format |
| Distribution | `python run.py` | Matches normal Python habit |
| Port | 3456 | Standard local dev port |
| Auto-open | `webbrowser.open()` on background thread | Convenience |
| Auto-refresh | `setInterval` every 60 seconds | Live updates without page reload |
| Package layout | `token_anatomy/` package | Maintainable, editable HTML separate from Python |
| Template serving | Read file per-request (not cached at startup) | Hot-reload on edit, no restart needed |

---

## 3. Project Structure

```
d:\Professional\Token Anatomy\
├── run.py                        ← entry point: python run.py
├── TOKEN_ANATOMY_CONTEXT.md      ← this file
├── README.md                     ← public docs
├── LICENSE                       ← MIT
├── .gitignore
├── token-anatomy-demo.png        ← dashboard screenshot (used in README)
└── token_anatomy/
    ├── __init__.py               ← empty (makes it a package)
    ├── __main__.py               ← python -m token_anatomy support
    ├── config.py                 ← env vars + rate constants
    ├── parser.py                 ← compute_cost() + parse_data()
    ├── server.py                 ← HTTP Handler + main()
    └── template.html             ← full dashboard HTML/CSS/JS
```

**Entry point:** `python run.py` from project root.
**Alternative:** `python -m token_anatomy` from project root.

**Import graph (no circular deps):**
```
config.py  ←  no internal imports
    ↑
    ├── parser.py   (imports CLAUDE_DIR, RATES)
    └── server.py   (imports CLAUDE_DIR, PORT, RATES + parse_data from parser)
                     ↑
              __main__.py / run.py  (imports main from server)
```

---

## 4. How the Data Pipeline Works

### Source files
Claude Code writes one JSONL file per session:
```
~/.claude/
  projects/
    <url-encoded-project-path>/
      <session-uuid>.jsonl
```

**Note:** Only Claude Code (CLI) sessions are available. Claude.ai desktop app chats are server-side only — no local JSONL files exist for them.

### JSONL line schema (relevant fields)

| Field | Where | Notes |
|---|---|---|
| `type` | top-level | `"assistant"` \| `"user"` \| `"summary"` |
| `timestamp` | top-level | ISO 8601 string |
| `message.model` | assistant turns | e.g. `"claude-sonnet-4-6-20250514"` |
| `message.usage.input_tokens` | assistant turns | integer |
| `message.usage.output_tokens` | assistant turns | integer |
| `message.usage.cache_read_input_tokens` | assistant turns | integer |
| `message.usage.cache_creation_input_tokens` | assistant turns | integer |
| `message.content[].type == "tool_use"` | assistant turns | tool call blocks |
| `message.content[].name` | tool_use blocks | tool name string |

Token usage counted only on `type == "assistant"` turns to avoid double-counting.

### Cost formula
```python
cost = (input_tokens       * RATE_INPUT       / 1_000_000)
     + (output_tokens      * RATE_OUTPUT      / 1_000_000)
     + (cache_read_tokens  * RATE_CACHE_READ  / 1_000_000)
     + (cache_write_tokens * RATE_CACHE_WRITE / 1_000_000)
```

### Default rates (Anthropic API — Claude Sonnet)
| Token type | USD per 1M |
|---|---|
| Input | $3.00 |
| Output | $15.00 |
| Cache read | $0.30 |
| Cache write | $3.75 |

All rates overridable via environment variables.

### Project label extraction
Directory names are URL-encoded full paths. Token Anatomy URL-decodes and takes the last path segment as display label.

---

## 5. API Endpoints

| Route | Method | Response |
|---|---|---|
| `/` | GET | Full dashboard HTML (read from `template.html` per-request) |
| `/api/stats` | GET | JSON payload with all aggregated data |

### `/api/stats` response shape
```json
{
  "total":          { "input": int, "output": int, "cache_read": int, "cache_write": int, "messages": int, "sessions": int },
  "today":          { ...same + "cost": float },
  "daily":          { "YYYY-MM-DD": { ...fields, "cost": float, "sessions": int } },
  "tools":          [ ["tool_name", count], ... ],
  "models":         { "claude-sonnet-4-6": int, ... },
  "projects":       [ ["project_label", { ...fields, "cost": float }], ... ],
  "sessions":       [ { session object }, ... ],
  "hourly":         [ int × 24 ],
  "cache_hit_rate": float,
  "cache_savings":  float,
  "total_cost":     float,
  "rates":          { "input": float, "output": float, "cache_read": float, "cache_write": float },
  "claude_dir":     string,
  "generated_at":   string
}
```

### Session object shape
```json
{
  "id":           "first 12 chars of filename stem",
  "project":      "human-readable label",
  "project_full": "raw url-encoded directory name",
  "messages":     int,
  "input":        int,
  "output":       int,
  "cache_read":   int,
  "cache_write":  int,
  "tools":        { "tool_name": count },
  "first_ts":     "ISO timestamp or null",
  "last_ts":      "ISO timestamp or null",
  "model":        "model string or null",
  "cost":         float
}
```

---

## 6. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CLAUDE_DIR` | `~/.claude` | Path to Claude data directory |
| `PORT` | `3456` | Server port |
| `RATE_INPUT` | `3.0` | Input token price (USD/1M) |
| `RATE_OUTPUT` | `15.0` | Output token price (USD/1M) |
| `RATE_CACHE_READ` | `0.30` | Cache read price (USD/1M) |
| `RATE_CACHE_WRITE` | `3.75` | Cache write price (USD/1M) |

For Bedrock cross-region inference (ap-southeast-2):
```bash
RATE_INPUT=5.0 RATE_OUTPUT=25.0 RATE_CACHE_READ=0.5 RATE_CACHE_WRITE=6.25 python run.py
```

---

## 7. Current Features

### Stat cards
- **Today's Snapshot:** sessions, messages, input tokens, output tokens, today's cost
- **All-Time Totals:** sessions, messages, total cost, cache hit rate %, cache savings, input/output tokens, cache reads
- **Hover tooltips:** every card has a plain-English definition on hover (`data-tip` attribute + CSS `::after`)

### Insights & Advisor panel
7 insight cards, each with severity (good/warn/bad/info), plain-English explanation, and actionable tip.
Positioned **below charts** (after Tool Call Frequency section).

| # | Insight | Signal | Severity |
|---|---------|--------|----------|
| 1 | Cache Hit Rate | `cache_hit_rate` | <10% bad, <40% warn, <70% info, ≥70% good |
| 2 | Model Selection | opus%/haiku% of sessions | >20% opus → warn; <5% haiku (≥10 sessions) → info |
| 3 | Session Cost Outliers | max_cost / median_cost | >5× → warn |
| 4 | Output/Input Ratio | output / (input + cache_read) | >50% → warn |
| 5 | Cache Write vs Read | cache_write==0 → bad; cache_read < cache_write×2 → warn |
| 6 | Tool Concentration | top_tool / total_tool_calls | >60% → info |
| 7 | Session Frequency | peak hour + active days | always info |

Color coding: `--green` (good), `--accent` orange (warn), `--red` (bad), `--blue` (info).

### Retrospective section
Two-panel grid positioned after All-Time Totals, before charts.

**Topic Clusters** (`token_anatomy/retrospective.py::compute_topic_clusters`)
- Extracts user message text from JSONL (`_extract_user_text` in `parser.py`)
- Keyword-taxonomy scoring across 8 categories + "General / Other" fallback
- Each session assigned to highest-scoring cluster
- Renders as gradient proportional bars with top-6 keywords per cluster
- `full_text` truncated to 8000 chars before JSON serialization

**Working Styles** (`retrospective.py::compute_working_styles`)
- 5 behavioral dimensions from session metadata (no NLP):
  1. Deep Diver / Quick Querier / Balanced Conversationalist (avg messages/session)
  2. Hands-On Builder / Pure Conversationalist (tool usage rate)
  3. Night Owl / Early Bird / Core Hours Worker (hourly distribution)
  4. Context Architect / Fresh Starter (cache hit rate)
  5. Breadth Explorer / Domain Specialist (distinct active clusters, requires ≥5 sessions)
- Each style: icon, label, description, evidence string, score bar (0–100)

Data flow: `parser.py::parse_data()` → `sess["full_text"]` → `compute_retrospective(sessions, hourly)` → `d.retrospective` in `/api/stats` → `renderRetrospective()` in JS

### Dashboard layout order
1. **Usage Overview** — unified cards grid: Today's Snapshot (5 cards) + "All-Time Totals" sub-label + 8 total cards, all in one auto-fill grid
2. Cost & Activity Trends (charts row 1)
3. Usage Patterns (charts row 2)
4. **Retrospective** — full width (`.retro-grid` internal 2-col)
5. **Insights & Advisor + [Per-Project Breakdown / Tool Call Frequency]** — side-by-side 1fr/1fr (`.side-row-insights-projects`): Insights left; right column has Projects table then Tools bar chart stacked below it; collapses at ≤900px
7. Daily Breakdown table
8. Chat Cost Browser

**Nav pills:** Overview · Totals · Trends · Patterns · Retro · Tools · Insights · Projects · Daily · Chats  
- "Totals" links to `id="sec-totals"` on the `.section-sub-title` div injected by JS inside `#today-cards`

### Timezone & Currency Selectors
Both selectors live in the header (right side, before status/refresh). State persists via localStorage.

| Key | Default | Description |
|---|---|---|
| `ta_timezone` | `UTC` | IANA timezone string (e.g. `Asia/Dhaka`) |
| `ta_currency` | `USD` | 3-letter currency code |
| `ta_fx_rates` | — | Cached JSON of FX rates from open.er-api.com |
| `ta_fx_timestamp` | — | Unix ms timestamp of last FX fetch |

FX rates cached 1h. On API failure: silent fallback to `FX_FALLBACK` table in `template.html`.  
`toUTC(s)` normalizer appends `Z` to naive ISO timestamps before any `new Date()` call.  
`ZERO_DECIMAL` set: JPY, PKR, IDR, KRW, VND show 0 decimal places.  
Hourly heatmap rebuilt from `d.sessions` on each render using selected timezone (not server-side `d.hourly`).

### Charts (Chart.js 4.4.0 CDN)
| Chart | Type | Description |
|---|---|---|
| Daily Cost | Bar | Last 30 days, USD |
| Daily Token Volume | Stacked bar | Input / Output / Cache Read per day |
| Hourly Activity Heatmap | Bar | Sessions by hour (0–23), alpha-scaled |
| Model Usage | Doughnut | Session count per Claude model variant |
| Cache Performance | Doughnut | Cache reads vs writes vs fresh input |

### Tool Call Frequency
Proportional horizontal bars, top 10 tools across all sessions.

### Per-Project Breakdown table
Top 8 projects by cost. Columns: project, sessions, messages, input, output, cache read (%), cost.

### Daily Breakdown table
Last 60 days. All token types + cost per day.

### Chat Cost Browser
Full interactive browser over all sessions — no cap.
- Free-text search (project name or session ID)
- Project dropdown filter
- Model dropdown filter
- All filters compose together
- Sortable columns: Started, Project, Model, Messages, Input, Output, Cache R, Cost
- Pagination: 25 rows/page
- Per-chat cache rate % inline
- Color-coded model pills (red=opus, green=haiku, purple=other)

---

## 8. Development History

### Session 1 — 2026-05-01
- Built Token Anatomy from scratch: pure Python stdlib, single-file
- Full data parser, cost formula, all aggregations
- All chart panels, tables, auto-refresh, auto-open
- **Name chosen: Token Anatomy** (user suggestion — precise, memorable, unique)
- Chat Cost Browser added (search/filter/sort/paginate, all sessions, per-chat cache rate)
- Deferred: export CSV, AI assistant panel, forecasting, live watcher

### Session 2 — 2026-05-01
- **Refactored monolith → package structure**
  - Split into `config.py`, `parser.py`, `server.py`, `template.html`
  - `run.py` added as simple entry point
  - `python -m token_anatomy` also works via `__main__.py`
- **Insights & Advisor panel added** (7 categories, color-coded severity)
- Clarified: Claude desktop app chats not available (server-side only)

### Session 3 — 2026-05-02
- **Bug fix:** server was reading `template.html` once at import time — served stale HTML after edits. Fixed to read per-request (`TEMPLATE_PATH.read_bytes()`)
- **Hover tooltips** added to all stat cards (`data-tip` + CSS `::after` popover)
- **Layout reorder:** Insights & Advisor moved below charts (better landing page)
- **GitHub release:** repo created at https://github.com/Muhit1204/token-anatomy
  - MIT LICENSE, README with demo screenshot, .gitignore added
- **README:** quick-start (3 lines), Windows instructions, custom rates section, demo screenshot

### Session 4 — 2026-05-02
- **Retrospective feature implemented** (new `token_anatomy/retrospective.py`)
  - `parser.py`: added `_extract_user_text()`, collects `sess["full_text"]` (truncated 8000 chars), calls `compute_retrospective()` at end of `parse_data()`
  - `retrospective.py`: `compute_topic_clusters()` (8-category keyword taxonomy + General fallback) + `compute_working_styles()` (5 behavioral dimensions from metadata)
  - `template.html`: CSS + HTML panel (two-column grid after All-Time Totals) + `renderRetrospective()` JS function
  - `retrospective` key added to `/api/stats` response
- **Rule established:** always update `TOKEN_ANATOMY_CONTEXT.md` after every change

### Session 6 — 2026-05-02
- **Model-aware pricing** implemented
  - `config.py`: added `MODEL_RATES` dict (10 model families, Claude 3.x + 4.x) + `get_rates(model_str)` helper that strips date suffix and falls back to global `RATES` for unknown models
  - `parser.py`: `compute_cost()` gains `model=""` param, uses `get_rates()` per call; per-session cost now uses correct model rates; daily/project costs accumulated by summing session costs (not recomputing from aggregated tokens); `total["cost"]` accumulated inline
  - Opus sessions now correctly priced at $15/$75 per 1M (was $3/$15); Haiku at $0.80/$4.00
- **Test suite added** (`tests/test_pricing.py`, `tests/__init__.py`)
  - 17 tests covering `get_rates()` and `compute_cost()` — all passing
  - Run: `python -m pytest tests/ -v`

### Session 8 — 2026-05-03
- **Responsive layout + wide-screen fixes** (`template.html` only)
  - `main` max-width bumped 1400px → 1600px; padding now `clamp(20px, 4vw, 60px)` (scales with viewport)
  - Header converted to full-bleed `<header>` + inner `.header-inner` div (`max-width: 1600px; margin: 0 auto`) so logo/nav/status align with main content on wide screens
  - Insights & Advisor + Per-Project Breakdown wrapped in `.side-row-insights-projects` (1fr/1fr, collapses at ≤900px)
  - Added `.side-row-insights-projects` CSS rule; `.side-row-retro-tools` media query shares same block
  - Scroll-spy `rootMargin` changed from `-40% 0px -55%` → `-30% 0px -65%` so active nav pill fires when section reaches viewport center, not just top

### Session 7 — 2026-05-02
- **Dashboard layout: reduced scrolling** (`template.html` only)
  - Merged Today's Snapshot + All-Time Totals into single unified `.cards` grid ("Usage Overview")
    - `#total-cards` element removed; totals injected via JS `+=` into `#today-cards` after a `.section-sub-title` separator div (`id="sec-totals"` preserved on it for nav)
  - Retrospective + Tool Call Frequency placed side-by-side: 2fr/1fr via `.side-row-retro-tools` grid wrapper
    - Collapses to single column at ≤900px
  - Added CSS: `.side-row`, `.side-row-retro-tools`, `.section-sub-title` (with `grid-column: 1/-1` to span all auto-fill columns)
  - Nav "Snapshot" pill renamed to "Overview"
  - Scroll distance reduced ~30%

### Session 9 — 2026-05-06
- **Timezone selector** added to dashboard header
  - `<select id="tz-select">` populated from 35-zone IANA list at runtime; persists to `localStorage` key `ta_timezone`
  - `fmtDate()` rewritten: uses `Intl.DateTimeFormat` via `toLocaleString('en-GB', {timeZone})` instead of string slicing
  - `toUTC(s)` normalizer added: appends `Z` to timestamps that lack timezone info (guards against older JSONL entries)
  - "Today" stats card now derives `todayKey` from `d.daily` using selected timezone (`en-CA` locale gives `YYYY-MM-DD`)
  - Hourly heatmap rebucketed from `d.sessions` using selected timezone (was using server-side `d.hourly` array)
  - `generated_at` display converted to selected timezone
  - On change: saves to localStorage, re-renders without refetch
- **Currency selector** added to dashboard header
  - `<select id="currency-select">` with 12 currencies; persists to `localStorage` key `ta_currency`
  - `fmtCost()` rewritten: multiplies by live FX rate, uses correct symbol, applies `ZERO_DECIMAL` set (JPY/PKR → 0 decimals)
  - `getCachedFX()`: fetches `open.er-api.com/v6/latest/USD` on load; caches in localStorage for 1h; silently falls back to `FX_FALLBACK` on failure
  - `FX_FALLBACK` hardcoded rates: USD/EUR/GBP/JPY/CAD/AUD/INR/BDT/SGD/CHF/MYR/PKR (BDT=122.0 current as of 2026-05)
  - On change: saves to localStorage, re-renders without refetch
- **`loadData()` refactored** to `async/await` with `Promise.all([fetch('/api/stats'), getCachedFX()])` — parallel fetches; `lastData` caches last response for re-render on selector change
- **`parser.py`** line 258: `datetime.now(timezone.utc)` replaces `datetime.now()` — avoids `DeprecationWarning` on Python 3.12+, emits unambiguous UTC timestamp with `+00:00` suffix

### Session 5 — 2026-05-02
- **Dashboard navigation** added to `template.html` (no other files changed)
  - `header` made sticky (`position: sticky; top: 0; z-index: 50`)
  - `<nav id="jump-nav">` added inside header — 10 pills: Snapshot · Totals · Trends · Patterns · Retro · Tools · Insights · Projects · Daily · Chats
  - Nav pills hidden (`opacity: 0`) at page load — fade in once user scrolls past 40px
  - Nav pill font size 13px (up from 11px)
  - Scroll-spy via `IntersectionObserver` — active pill highlights orange as section enters viewport
  - `id="sec-*"` added to all 10 `.section-title` divs; `scroll-margin-top: 57px` offsets sticky header on jump
  - Pills horizontally scrollable on narrow viewports (`overflow-x: auto; scrollbar-width: none`)
- **Back-to-top button** — orange pill "↑ Back to top", centered fixed above footer, appears only when within 80px of page bottom. Button placed in DOM before `<script>` block (was after — caused `getElementById` null bug)
- **Retrospective section moved** — now after Usage Patterns (position 5), was position 3
- **README updated** — added Retrospective, navigation, and Daily Breakdown to feature table; corrected repo URL

---

## 9. Roadmap

### v0.2
- [ ] Export button — download filtered Chat Cost Browser view as CSV
- [ ] Cost forecasting — rolling-average extrapolation ("at this pace, monthly = $X")
- [ ] Write test suite (`tests/` directory)
  - Unit tests: `compute_cost()`, `parse_data()` with fixture JSONL files
  - Integration test: HTTP server returns valid JSON from `/api/stats`
  - Insight logic tests: each of 7 insight rules fires correctly

### v0.3
- [ ] Date range filter in Chat Cost Browser
- [ ] Duration per chat (last_ts − first_ts)
- [ ] Compact/dense layout toggle

### v0.4 — AI Assistant Panel
- [ ] "Ask your data" text input
- [ ] Calls Anthropic API with session stats as context
- [ ] Natural language answers ("Which project cost most last week?")
- [ ] API key input (stored in `.env`, never hardcoded)

### v1.0
- [ ] GitHub Actions: lint check on push
- [ ] One-liner install via curl

---

## 10. Known Limitations & Edge Cases

| Issue | Status | Notes |
|---|---|---|
| Sessions with no `timestamp` | Handled | `first_ts`/`last_ts` = None, displayed as `—` |
| Malformed JSONL lines | Handled | `try/except json.JSONDecodeError` per line |
| Unreadable files | Handled | Warning to stderr, file skipped |
| Project label collisions | Known gap | Two projects with same last path segment merge in table |
| Very large `~/.claude` dirs (1000+ sessions) | Untested | May slow parse; no streaming/caching yet |
| Windows path separators | Untested | `urllib.parse.unquote` should handle it |
| `model` field absent on older sessions | Handled | Displays as "unknown" with purple pill |
| Cache savings formula | Approximation | Compares actual cost vs hypothetical no-cache cost |
| Claude desktop app chats | Not supported | Server-side only — no local JSONL exists |
| Insights with < 3 sessions | Partially skipped | Session outlier insight requires ≥3 sessions |

---

## 11. Reference Links

| Resource | URL |
|---|---|
| Claude Code docs | https://docs.anthropic.com/claude-code |
| Anthropic API pricing | https://www.anthropic.com/pricing |
| Chart.js 4.4.0 CDN | https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js |
| Token Anatomy repo | https://github.com/Muhit1204/token-anatomy |
