# ADR-007 — No Giant Files

- **Status:** accepted
- **Date:** 2026-08-13

## Context

As the application grows, files can silently balloon to thousands of lines —
`app.js` → 3,000, `mcp_server.py` → 2,000, `dashboard.py` → 2,000,
`analytics.py` → 2,000 — "just because the application grew". A file that large
is hard to navigate, review, and change, and size usually means several
responsibilities have piled up in one place.

Line count alone is not the deciding factor: a 3,000-line stylesheet or a
1,000-line single-class adapter can be one honest responsibility. But a file
holding **many unrelated responsibilities** must be split.

## Decision

**Do not make giant files. This rule is mandatory.**

- Prefer **20 focused modules** over **5 giant modules**.
- Line count is a smell, not the rule: split when a file contains many
  unrelated responsibilities (the File Responsibility test, ADR-004 — "why
  would someone edit this file?" with several unrelated answers means split).
- A module should still represent a **meaningful responsibility** — do not
  shatter files into fragments (ADR-004: split by responsibility, not
  granularity). Do not create empty or near-empty modules to look tidy
  (architecture.md Rule 5).
- When a file stops being navigable, split it **before** it becomes a giant,
  not after.

Audit findings (2026-08-13, updated 2026-08-14):

- **No source file violates the rule today.** The two flagged split candidates
  were split by responsibility:
  - `providers/upstox.py` (was 1068 lines) is now an ~40-line assembler plus
    focused mixins by domain: `upstox_connect` (auth/transport),
    `upstox_resolution` (key/lot-size), `upstox_market_data` (chains/quotes/...),
    `upstox_fundamentals`, and shared `upstox_parsing` helpers. `UpstoxClient`
    and every protocol method keep their names.
  - `api/routes/__init__.py` (was ~272 lines, all 15 resources) is now a
    re-export shim plus `market.py`, `fundamentals.py`, `auth.py`, `tools.py`.
- Largest remaining: `frontend/style.css` (1485 lines — one responsibility: all
  styling, no build step; CSS exception) and `providers/upstox_market_data.py`
  (~470 lines — one responsibility: the market-data slice of the Upstox adapter;
  size is a smell to watch, not a violation).
- Watch list for future splits: `providers/upstox_market_data.py` — split its
  market-information block (PCR/max-pain/OI/FII/DII/status) if it keeps growing;
  `mcp/market_data.py` — 19 tools, split when a category grows.

## Alternatives considered

- **Hard line-count limits (e.g. "never exceed 1,000 lines")** — rejected:
  line count alone is explicitly not the deciding factor; a hard cap would force
  artificial splits of single-responsibility files.
- **No rule** — rejected: files grow incrementally and every addition looks
  reasonable at the time.

## Consequences

- Codebase stays navigable as the application grows.
- New functionality gets a natural home in a focused module instead of being
  appended to an ever-growing file.
- Reviews can flag "this file is getting large" as a first-class concern, with
  the split decision guided by responsibility (ADR-004), not just line count.
- The named anti-examples (`app.js`, `mcp_server.py`, `dashboard.py`,
  `analytics.py`) are all already split or small in this repo; the rule keeps
  them that way as the tool set grows.
