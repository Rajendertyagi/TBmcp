# Development Workflow

The "how to apply" reference for the development-workflow convention
([ADR-006](../decisions/adr-006-development-workflow.md)). **Every new feature
follows these seven steps, in order.** It applies to any AI coding agent and to
manual human development alike.

---

## Step 1 — Understand

Inspect before coding. At a minimum, read:

- [`AGENTS.md`](../../AGENTS.md) — the onboarding map + the load-bearing rules.
- [`docs/architecture.md`](../architecture.md) — the permanent engineering
  contract: layers, boundaries, Rules.
- The reference for the areas the feature touches:
  - HTTP endpoints → [`docs/api/endpoints.md`](../api/endpoints.md)
  - MCP tools → [`docs/mcp/tools.md`](../mcp/tools.md)
  - Browser frontend → [`docs/frontend/guide.md`](../frontend/guide.md)
  - Tests → [`docs/testing/README.md`](../testing/README.md)
- The relevant source files, existing services, and existing tests — not just
  the docs.

Do not immediately start coding.

## Step 2 — Identify ownership

Determine and write down:

| Item | Answer |
|---|---|
| Feature | _what is being added or changed_ |
| Existing modules involved | _providers/, analytics/, mcp/, api/, frontend/, services/, tests/_ |
| New modules required | _only if the responsibility has no home (see Step 3)_ |
| Existing files that should NOT be modified | _see AGENTS.md §17 "MUST NOT change casually"_ |
| Dependencies | _new packages, config, credentials, external services_ |

## Step 3 — Decide modularity

Decide **before implementing** which of these applies:

1. **An existing module is appropriate** → add to it.
2. **A new module is needed** → create it (name it for its responsibility per
   ADR-004; give it a real job, not a "helpers" grab-bag).
3. **An existing module should be split first** → split it, then implement.

If the feature would require **major restructuring**, **STOP and report it**
before proceeding — do not silently rearrange the codebase as part of a feature.

## Step 4 — Implement

- Make the **smallest clean change** consistent with `docs/architecture.md`.
- Respect the hard boundaries: `DataProvider` in `providers/base.py` (ADR-003),
  shared analytics once in `analytics/` (never duplicated into tools/routes/JS),
  MCP tools in their category module with stable names (ADR-005).
- Never use an existing file as a dumping ground (ADR-004).

## Step 5 — Test

- Add or extend tests per [`docs/testing/README.md`](../testing/README.md):
  unit + integration run offline; live tests are gated behind `TBMCP_RUN_LIVE=1`
  and never run in CI.
- Regression-test the affected functionality:
  `uv run python -m pytest -q`
- After any MCP change, verify the 42-tool inventory is unchanged:
  `python -c "import mcp.server as s; print(sorted(s.mcp.tools.methods))"`

## Step 6 — Documentation

Update the relevant documentation whenever the architecture, HTTP API, MCP
tools, frontend pages, configuration, or behavior changed:

| Changed | Update |
|---|---|
| Repo layout / layers / rules | `docs/architecture.md` |
| HTTP endpoints | `docs/api/endpoints.md` |
| MCP tools | `docs/mcp/tools.md` (names + args) |
| Frontend pages/JS | `docs/frontend/guide.md` |
| Config / env vars | `docs/development/local.md` |
| Tests / verification | `docs/testing/README.md` |
| Behavior or decisions worth remembering | `docs/background.md`, `docs/decisions/` |
| Agent-facing onboarding | `AGENTS.md` |

## Step 7 — Report

Report (in the final message and/or PR description):

- **Files created:** ...
- **Files modified:** ...
- **Files removed:** ...
- **Tests performed:** ...
- **Architecture impact:** ...
- **Documentation updated:** ...
- **Remaining issues:** ...
