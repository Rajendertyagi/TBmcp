# TBmcp — Session Tracking / Progress Log

> Working notes so a future session can pick up exactly where we left off.
> Workspace root: `D:\Temp\TBmcp` (git repo). The app lives at the repo root, and the forked AI engine lives self-contained at `zeromcp/`.

## Session context

The long-running goal has been rebuilding TBmcp (an Upstox-backed trading-data MCP
server + web dashboard) in phases. Earlier phases (already done):

1. **zeromcp fork** — the AI engine lives self-contained at `zeromcp/` (not pip-installed; the
   MCP server adds `zeromcp/src` to `sys.path` at import time).
2. **tools.py → mcp_server.py** — migrated off the official `mcp` SDK onto the
   forked zeromcp engine.
3. **NiceGUI ui.py → Falcon dashboard** (`dashboard.py` + `frontend/` static app).
4. **DataProvider abstraction** — `client.py` (UpstoxClient) behind a `DataProvider`
   protocol so a broker swap needs no tool/UI renames.

## Phase 4 (just completed): flat modules → packages

`rtmcp` was a flat set of modules; this phase split them into packages so each
layer (provider / analytics / API / MCP / services) is independently importable
and testable. **Nothing is committed yet.**

### File map

| New location | Came from | Notes |
|---|---|---|
| `analytics/options.py` | `analytics.py` + `buildup.py` | merged; `BUILDUP_COLORS`/`NEUTRAL_BUILDUP` import added |
| `analytics/__init__.py` | — | re-exports 13 public names (`compute_*`, `price_strategy`, `classify_buildup`, `buildup_color`) |
| `providers/base.py` | `providers.py` (Protocol) | 21-method `DataProvider` contract, incl. `exchange_code_for_token` |
| `providers/upstox.py` | `client.py` (1060 lines) | `from buildup import classify_buildup` → `from analytics import classify_buildup` |
| `providers/__init__.py` | `providers.py` (`create_provider`) | factory + re-exports `DataProvider`, `UpstoxClient` |
| `api/render.py` | `render.py` | `buildup_color` import now from `analytics` |
| `api/app.py` | `dashboard.py` | helpers `get_client`/`rebuild_client`/`_json`/`_safe`, `IndexResource`, `create_app`, `build_app` |
| `api/routes/__init__.py` | `dashboard.py` | 12 resources: Ticker, Quote, Chain, Expiries, History, Vix, TestAll, Settings, LoginUrl, Login, Callback, LoginStatus |
| `mcp/server.py` | `mcp_server.py` | assembly: builds `client`, `mcp`, binds tools |
| `mcp/market_data.py` | `mcp_server.py` | 19 raw tools (`get_*`) |
| `mcp/options.py` | `mcp_server.py` | 16 derived/strategy tools (`compute_*`, `price_*`) |
| `services/tools_runner.py` | `tools_runner.py` | unchanged logic |
| `main.py` | — | imports → `from mcp.server import mcp`, `from api.app import build_app` |
| `tests/tool_test.py` | — | import → `from services.tools_runner import run_all_tools` |

Deleted flat files: `client.py`, `providers.py`, `analytics.py`, `buildup.py`,
`render.py`, `mcp_server.py`, `dashboard.py`, `tools_runner.py`.

### Key design points

- **MCP tool binding:** submodules define plain async functions + a `TOOLS` list;
  `mcp/server.py` does `mcp.tool()(fn)` for each. Tool name = `fn.__name__`, so the
  AI-facing names are unchanged (35 tools: 19 raw + 10 compute + 6 price).
- **Circular import (API):** `api/routes/__init__.py` imports helpers from `..app`;
  `api/app.py` imports `.routes` at the **bottom** of the file to break the cycle.
- **`_client` injection:** `mcp/market_data.py` and `mcp/options.py` keep a module
  `_client = None`; `mcp/server.py` sets `market_data._client = client` after
  building the provider. Avoids importing the server from the tool modules.
- **`zeromcp` sys.path:** `mcp/server.py` resolves `zeromcp/src` as
  `os.path.join(os.path.dirname(__file__), "..", "zeromcp", "src")` (the engine is a
  self-contained project at the repo root with a src-layout).
- **Dashboard `STATIC_DIR`:** `api/app.py` uses `os.path.join(_HERE, "..", "frontend")`.

### Bug fixed during the move

The old `mcp_server.py` had `async def compute_pcr(...)` bodies calling
`compute_pcr(chain)` — i.e. the **tool calling itself**, not the analytics
function. Every `compute_*`/derived tool would have raised at runtime.
Fixed by aliasing the analytics imports in `mcp/options.py`
(`compute_pcr as _compute_pcr`, …) and rewriting the call sites.

## Important tooling caveat

The Read tool in this environment **corrupts large file contents** (fabricated
imports, phantom lines, mangled code). The real files were completely different
from what the Read tool displayed (e.g. dashboard.py). Therefore:

- **Python is the source of truth** for anything file-content related. Read via
  `pathlib`, transform/verify with Python/AST.
- The migration itself was done programmatically (not hand-copied).
  Scripts kept at:
  - `C:\Users\RTPC\AppData\Local\Temp\opencode\migrate.py` (runs the move)
  - `C:\Users\RTPC\AppData\Local\Temp\opencode\verify.py` (post-move checks)

## Verification performed (all green)

- `compileall` over the repo root (excluding `.venv`, `__pycache__`, `frontend`, `zeromcp`).
- All packages import: `analytics`, `providers`, `api.app`, `mcp.server`, `services.tools_runner`.
- `mcp.server.mcp.tools.methods` has exactly **35** tools with the original names.
- Shadowing fix confirmed via `inspect.getsource` (`_compute_pcr(chain)`,
  `_client.get_option_chain`).
- Falcon app: `create_app()` + `falcon.testing.TestClient` — `GET /`,
  `/api/settings`, `/static/index.html`, `/api/login-url` all return 200.
- `python main.py --help` works; repo-wide scan shows **0 stale imports**
  of the old flat modules.

## Pending / follow-ups (not done)

- [ ] Commit the Phase 4/5 changes (repo currently has many `D`/`M`/`??` entries;
      also `.upstox-token.json` is untracked — do **not** commit secrets).
- [x] Repo restructure: `rtmcp-py` renamed to `rtmcp`, then the app was flattened to
      the repo root; the engine is now a self-contained project at `zeromcp/`
      (own pyproject/README/tests/examples/CI).
- [x] Phase 5 — File Responsibility Rule: recorded as a project convention in
      `docs/CONVENTIONS.md`; codebase audited and already compliant (no renames needed).
- [x] Phase 6 — MCP Modularization: recorded as Rule 2 in `docs/CONVENTIONS.md`.
      Current `mcp/` already complies (`server.py` assembly-only, `market_data.py`
      19 tools, `options.py` 16 tools, one shared `McpServer`). Future category
      modules (`technical`, `fundamentals`, `screening`, `portfolio`) to be created
      only when those categories grow; tool names must stay stable.
- [ ] `PLAN_*.md` (now in `docs/`) still reference old flat module names (`mcp_server`,
      `dashboard.py`, `tools_runner`, `client`) and the old `rtmcp-py/` path — update or leave.
- [ ] `tests/unit`, `tests/integration`, `tests/live` dirs exist but appear empty;
      decide whether to add package-path-aware tests.
- [ ] Optionally verify a real `python main.py mcp` stdio round-trip (needs a live
      client + token) and a real `python main.py ui` browser session.
- [ ] Repo-root `tests/*_test.py` were deleted in an earlier phase — confirm
      intentionally or restore.
