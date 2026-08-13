# TBMCP Repo Audit (hyaudit)

> Audit date: 2026-08-13
> Scope: full repository (`TBmcp` working tree at `D:\Temp\TBmcp`)
> Mode note: this is a read-only audit snapshot. Findings reference the state of the
> working tree at audit time (4 commits ahead of `origin/master`, with uncommitted
> changes and untracked files present).

---

## 1. What this repo actually is

It is **two projects in one tree**, which is the root cause of most of the confusion:

| Path | What it is | Package / version |
|------|------------|-------------------|
| `zeromcp/` | Vendored fork of `mrexodia/zeromcp` — the zero-dependency MCP engine (self-contained project at the repo root) | package `zeromcp` v0.0.0 |
| repo root (`TBMCP/`) | The actual application: an Upstox-backed market-data **MCP server** (`mcp/server.py`, ~35 tools) **plus** a **Falcon + vanilla-JS dashboard** (`api/app.py` + `frontend/`) | `tbmcp` v0.1.0 |

The engine's `README.md` (inside `zeromcp/`) documents only `zeromcp`. All recent commits land in the app at the repo root.
There are two `pyproject.toml` files and two `uv.lock` files (one per project).

---

## 2. Findings

### 🔴 Critical — fix before any commit/push

**C1. Live credential is not gitignored.**
`.upstox-token.json` (contains `access_token` + `refresh_token`, written by
`config.save_token`) is untracked and matched by **no** `.gitignore`. `git check-ignore`
returns "not ignored". A single `git add -A` would commit a working broker token.
The engine `.gitignore` (inside `zeromcp/`) also never mentions `.env` (only the root `.gitignore` does).

- Files: `.upstox-token.json`, `.gitignore`
- Fix: add `.upstox-token.json` (and a root `.env` rule) to ignore; confirm the file is
  never staged; consider rotating the exposed token.

**C2. CI is broken.**
`.github/workflows/ci.yml` runs `tests/jsonrpc_test.py`, `tests/mcp_test.py`,
`tests/server_test.py`, `tests/future_annotations_test.py` — **all four were deleted**
(uncommitted working change). Every push/PR fails. Additionally, `uv sync` at the repo
root only builds/tests the `zeromcp` library (in `zeromcp/`); the app (deps `falcon` /
`waitress` / `requests`) is never installed or tested by CI at all.

- File: `.github/workflows/ci.yml`
- Fix: restore the 4 library tests OR update CI to the real layout, and add a job that
  `uv sync`s the repo root and runs `tool_test.py` / type-checks the app.

### 🟠 High

**H1. Dirty repo + lost library tests.**
4 commits ahead of `origin/master`; uncommitted `main.py` change (adds `--debug` flags —
benign); the 4 deleted test files mean `zeromcp` now has **zero** coverage while
`pyproject.toml` still declares `testpaths = ["tests"]` (collects nothing). The app's
only test (`tests/tool_test.py`) is a manual CLI harness, not run by CI.

- Fix: commit/stash the `main.py` change; decide the fate of the deleted tests.

### 🟡 Medium

**M1. Stale `PLAN_*.md` (4 files).**
`PLAN_REPLACE_NICEGUI.md`, `PLAN_DUAL_SERVER.md`, `PLAN_SYMMETRICAL_CHAIN.md`,
`PLAN_FRAMEWORK_COMPARISON.md` describe a *NiceGUI → Flask* migration, but the code
already moved to **Falcon + vanilla JS**. They reference files that don't exist
(`ui.py`, `charts.py`, `tbmcp.css`). Misleading — remove or archive.

**M2. Stale `docs/`.**
`docs/overview.md` says the MCP server "exposes 3 tools" (it exposes ~30), references
`charts.py` / `tbmcp.css` (real files are `frontend/style.css`, no `charts.py`), and
says "Python 3.10+" while `pyproject.toml` requires `>=3.11`. `docs/README.md` mentions
NiceGUI then corrects to Falcon. Root `README.md` is `zeromcp`-only.

**M3. Dashboard has no auth and returns `api_key`.**
`SettingsResource.on_get` (dashboard.py:221) returns the API key in plaintext;
`/api/settings` POST writes credentials; `/upstox/callback` exchanges tokens. It binds
`127.0.0.1` by default (acceptable for a local tool), but if launched on `0.0.0.0` the
entire credential surface is exposed.

**M4. `CallbackResource` hardcodes the redirect URI.**
`dashboard.py:302` uses `DEFAULT_UPSTOX_REDIRECT_URI` instead of the configured
`redirect_uri`. If a custom redirect URI is set, one-click login silently breaks.

- Fix: read `load_settings().redirect_uri` (with the default as fallback).

### 🟢 Low

**L1. Latent XSS patterns.** Frontend uses `innerHTML` with API/error strings
(e.g. `tools.js`, `chart.js`). Low risk today (localhost + server-trusted data), but
error text should be escaped before insertion.

**L2. `get_full_quotes` dead branch.** `client.py:965` matches `val.get("symbol")`, but
Upstox returns `trading_symbol`, so that branch never fires — it works only via the
token/key match.

**L3. `json_load` defined at the bottom of `client.py`** and re-imports `json` — works at
runtime but is stylistically odd.

**L4. Naming/maintenance clarity.** `TBmcp` / `zeromcp` / `tbmcp` plus dual
`pyproject.toml` + `uv.lock` is confusing for a newcomer and makes the fork's
sync-with-upstream status unclear.

---

## 3. Recommended remediation plan (priority order)

1. **Security first (C1):** add `.upstox-token.json` (and a root `.env` rule) to
   `.gitignore`; verify the token file is never staged; rotate the leaked token.
2. **Fix CI (C2):** restore the 4 library tests or update `ci.yml` to the real layout;
   add a job that `uv sync`s the repo root and runs `tool_test.py` / type-checks the app.
3. **Clean the working tree (H1):** commit or stash the `main.py` change; decide the fate
   of the deleted tests.
4. **Remove/archive the 4 stale `PLAN_*.md` (M1)** and refresh `docs/` to match reality
   (~30 tools, Falcon, `frontend/style.css`, Python 3.11+).
5. **Harden the dashboard (M3/M4):** use the configured `redirect_uri` in the callback;
   optionally gate `/api/settings` and the callback behind localhost-only or a simple token.
6. **Escape error strings (L1)** before `innerHTML`, and fix the `get_full_quotes` symbol
   match (L2).

---

## 4. Open questions for the owner

- **Goal of the audit:** clean up / get CI green / secure the repo, or assess architecture
  soundness before building more features? Changes what gets prioritized.
- **Deleted test files:** intentional (you only care about `tbmcp`, drop the `zeromcp`
  library tests) or an accident? Determines whether step 2 restores or removes them from CI.
