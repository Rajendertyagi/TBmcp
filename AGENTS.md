# AGENTS.md — Onboarding for AI Coding Agents

> **Read this first.** This is the primary onboarding document for any AI coding
> agent working on TBMCP. It tells you what the project is, how it is laid out,
> how to run it, the rules that govern changes, and — most importantly — the
> things you **MUST NOT change casually**.
>
> The docs in [`docs/`](docs/README.md) hold the detailed references; this file
> gives you the map and the rules. When in doubt, check the docs.

---

## 1. What TBMCP is

**TBMCP** (Python package name `tbmcp`) is a personal Indian stock-market
application with **two consumers** that share one data layer:

1. **An AI assistant** — talks to an **MCP server** exposing **42 tools**
   (raw market data + fundamentals/news/Greeks + derived F&O analytics + strategy pricers) over stdio.
2. **A human** — uses a **web dashboard** (Falcon backend + static HTML/JS SPA)
   served on `http://127.0.0.1:8888`.

Both read live data from the **Upstox** broker through a single provider
abstraction, so the AI view and the human view never disagree.

Full product description: [`docs/product.md`](docs/product.md).

---

## 2. Development workflow

**Every new feature follows a fixed 7-step sequence** — understand → identify
ownership → decide modularity → implement → test → document → report. Step 1
means inspect before coding; Step 3 has a hard stop: if a feature needs major
restructuring, **STOP and report it before proceeding**. Step 7 closes with a
fixed report shape (files created/modified/removed, tests, architecture impact,
docs, remaining issues).

Full step-by-step reference (with repo-specific pointers):
[`docs/development/workflow.md`](docs/development/workflow.md).
Convention: [ADR-006](docs/decisions/adr-006-development-workflow.md).

---

## 3. Repository structure

```
TBMCP/                       # git repo root = the app
├── AGENTS.md                # you are here
├── main.py                  # entry point: `mcp`, `ui`, `both` subcommands
├── config.py                # settings + portable .env/.token paths
├── constants.py             # every magic value (URLs, lot sizes, colours, defaults)
├── models.py                # typed data models (OptionChain, Candle, FuturesChain, ...)
├── providers/               # DataProvider abstraction (swap brokers here)
│   ├── __init__.py          #   create_provider() factory
│   ├── base.py              #   30-method DataProvider protocol
│   └── upstox.py            #   UpstoxClient: the Upstox v2/v3 REST adapter —
│       ├── upstox_parsing.py      #     split into focused mixins by domain:
│       ├── upstox_connect.py      #     raw-response parsing + debug dumps
│       ├── upstox_resolution.py   #     auth + token lifecycle + rate-limited transport
│       ├── upstox_market_data.py  #     symbol → instrument-key / lot-size resolution
│       └── upstox_fundamentals.py #     chains, quotes, futures, depth, margin, market info
│                                #     fundamentals / news / option Greeks
├── analytics/               # derived F&O analytics — pure functions over models
│   ├── option_chain.py      #   chain analytics (compute_*) + buildup tagging
│   └── strategies.py        #   strategy pricers (price_strategy)
├── mcp/                     # AI-facing MCP server (server.py + tool modules)
│   ├── market_data.py       #   19 raw market-data tools (get_*)
│   ├── fundamentals.py      #   7 fundamentals/news/Greeks tools
│   └── options.py           #   16 derived/strategy tools (compute_*, price_*)
├── api/                     # human-facing Falcon web dashboard
│   ├── app.py               #   WSGI assembly + helpers
│   ├── render.py            #   pure HTML rendering for the chain table
│   └── routes/              #   one Resource class per HTTP endpoint, split by
│       ├── market.py        #     responsibility (re-exported via __init__.py):
│       ├── fundamentals.py  #     market data (ticker/quote/chain/expiries/history/vix)
│       ├── auth.py          #     fundamentals / news / option Greeks
│       ├── tools.py         #     settings + OAuth login flow
│       └── __init__.py      #     "test all" batch (Tools page)
├── services/
│   └── tools_runner.py      # runs every tool once ("Test All" batch)
├── frontend/                # static HTML/JS single-page app
├── tests/                   # test harness
├── zeromcp/                 # the forked ZeroMCP engine (self-contained project)
├── docs/                    # detailed documentation
└── pyproject.toml           # app package metadata (name="tbmcp")
```

---

## 4. Where the actual application lives

The application is at the **repository root**. `main.py`, `config.py`,
`constants.py`, `models.py`, and the `providers/`, `analytics/`, `mcp/`,
`api/`, `services/`, `frontend/`, `tests/` packages **are the app**. All recent
commits land here.

The root `pyproject.toml` (name `tbmcp`, version `0.1.0`) is the app's project
file. Dependencies: `falcon`, `waitress`, `requests`.

---

## 5. Where ZeroMCP lives

The AI server runs on a **forked ZeroMCP engine** — a zero-dependency MCP server
framework we control. It lives self-contained at [`zeromcp/`](zeromcp/):

- It keeps a **minimal `pyproject.toml`** (name/version/requirements only) and
  the engine source under `src/`. Everything else from upstream was trimmed when
  it was vendored — no `uv.lock`, no `examples/`, no `README.md`/`LICENSE`, no
  nested `.github` CI (the app's tests cover the engine, and GitHub only runs
  root-level workflows anyway).
- It is **not pip-installed**. `mcp/server.py` adds `zeromcp/src` to `sys.path`
  at import time:

  ```python
  _SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zeromcp", "src")
  if _SRC_DIR not in sys.path:
      sys.path.insert(0, _SRC_DIR)
  ```

- The importable package is `zeromcp` (under `zeromcp/src/`).

Do not edit `zeromcp/` casually — treat it as an upstream fork you sync, not app
code. (See §17.)

---

## 6. How to run the application

Requires **Python >= 3.11** and **uv**. Full setup: [`docs/development/local.md`](docs/development/local.md).

```bash
uv sync            # creates .venv, installs falcon/waitress/requests
```

| Command | What it runs |
|---|---|
| `python main.py` | **both** MCP server + web UI (default) |
| `python main.py both` | both, explicitly |
| `python main.py mcp` | MCP server (stdio) only — for AI clients |
| `python main.py ui` | Falcon web dashboard only — for humans |
| `python main.py ui --debug` | dashboard with DEBUG logs |

The dashboard listens on `http://127.0.0.1:8888` by default.

**Credentials:** an Upstox `UPSTOX_API_KEY` / `UPSTOX_API_SECRET` /
`UPSTOX_REDIRECT_URI` in a local `.env` next to the app (or via the dashboard's
gear-icon settings page). Logs go to **stderr** so they never corrupt the MCP
server's stdout JSON-RPC stream. `--reload` is accepted but ignored by Falcon.

---

## 7. Frontend architecture

The dashboard is a **vanilla JavaScript SPA** — no React/Vue/Angular, no build
step. It is served as static files by Falcon.

```
frontend/
├── index.html            # single application shell
├── style.css             # all styling + bundled font @font-face rules
├── vendor/               # lightweight-charts (local, classic script)
└── js/
    ├── app.js            # bootstrap only: registers pages, wires top bar, ticker
    ├── router.js         # client-side routing / nav tabs
    ├── api.js            # the ONLY module that calls fetch()
    ├── state.js          # tiny app state (currentRoute)
    ├── pages/            # one module per page (home, market, vix, charts, tools, upstox)
    ├── components/       # reusable UI (ticker, chart, controls, error)
    └── utils/            # helpers (dom, format, config)
```

Key rules:

- `app.js` stays **small** — bootstrap/orchestration only. Never dump page logic
  into it.
- Pages register via `registerRoute(key, label, factory, opts)` in `app.js`;
  the router lazily mounts each page on first visit.
- All backend calls go through `api.js`; pages never call `fetch()` directly.
- The whole frontend must remain plain static files (freezes into the Nuitka
  `.exe`).

Guide: [`docs/frontend/guide.md`](docs/frontend/guide.md).

---

## 8. Backend architecture

Layers (top to bottom):

```
DataProvider  (providers/)  — one broker adapter behind a stable protocol
     ↓
Typed Models  (models.py)   — OptionChain, Candle, FuturesChain, ...
     ↓
Analytics     (analytics/)  — pure functions, no network, broker-agnostic
     ↓
 ┌──────────────┬──────────────┐
 MCP (mcp/)    Falcon (api/)  → frontend/
```

Key patterns:

- **`DataProvider` is a hard boundary** — a new broker fits behind
  `providers/base.py` without touching MCP tools or frontend pages.
- **Analytics are broker-agnostic** — shared logic lives once in `analytics/`,
  called by both the MCP tools and the Falcon routes. Never duplicate a
  calculation across layers.
- **Client is lazy/rebuildable** (`api/app.py`) — `get_client()` builds on first
  use; `rebuild_client()` recreates after credential changes, so settings edits
  take effect without a restart.
- **Error handling** — the API wraps client calls in `_safe()`, returning
  `{"error": ...}` JSON instead of raising. MCP tools return `json.dumps(...)`
  strings.

Architecture: [`docs/architecture.md`](docs/architecture.md).

---

## 9. MCP architecture

The MCP server is **modular by tool category** with exactly **one shared
`McpServer`** instance:

```
mcp/
├── server.py         # assembly only: builds McpServer, injects client, registers TOOLS
├── market_data.py    # 19 raw market-data tools (get_*)
├── fundamentals.py   # 7 fundamentals/news/Greeks tools
└── options.py        # 16 derived/strategy tools (compute_*, price_*)
```

Rules:

1. **One shared instance.** Tool modules expose a `TOOLS` list of plain async
   functions; `server.py` registers them:
   `for _fn in fundamentals.TOOLS + market_data.TOOLS + options.TOOLS: mcp.tool()(_fn)`.
2. **Stable tool names.** The registered name is the function's `__name__`.
   Moving a tool between modules must **never** rename it.
3. **Split on category size.** New category modules (`technical.py`,
   `fundamentals.py`, `screening.py`, `portfolio.py`) are created only when a
   category grows — not to match a tree.
4. **Client injection stays internal.** `server.py` sets `module._client = client`.

All 42 tools (names + args): [`docs/mcp/tools.md`](docs/mcp/tools.md).

---

## 10. Provider architecture

- `providers/base.py` defines the **`DataProvider` protocol** (30 methods) —
  the contract every data source must implement.
- `providers/upstox.py` is the **`UpstoxClient`** adapter (the only provider),
  assembled from focused mixins by domain (`upstox_connect`, `upstox_resolution`,
  `upstox_market_data`, `upstox_fundamentals`) plus shared `upstox_parsing`
  helpers — the public surface (`UpstoxClient`, all protocol methods) is unchanged.
- `providers/__init__.py` exports `create_provider(settings)` — the **single
  switch point**, driven by `TBMCP_PROVIDER` (default `upstox`).

Adding a broker = new module in `providers/` + a factory entry. Do **not** call
the broker directly from tools, routes, or pages.

---

## 11. Naming conventions

**File Responsibility Rule** — every important file has a clear reason to
change; name files for their responsibility, not their position.

Bad: `helpers.py`, `misc.py`, `stuff.py`, `common.py`, `new.py`, `extra.py`,
`utils2.py`. Good: `option_chain.py`, `technical_analysis.py`, `market_data.py`,
`fundamentals.py`, `screening.py`, `upstox.py`, `portfolio.py`.

Test before naming: **"Why would someone edit this file?"** — one honest answer
means a good name; several unrelated answers mean split it. Signals:

1. One verb per file.
2. The name survives a rename test (`upstox.py` stays correct if the broker is
   swapped; `misc.py` is wrong no matter what).
3. No siblings by qualification — `utils2.py` / `extra.py` / `helpers_final.py`
   are symptoms of a file outgrowing its name; split the file, don't suffix the
   name.

ADR: [`docs/decisions/adr-004-file-responsibility.md`](docs/decisions/adr-004-file-responsibility.md).

---

## 12. Modularization rules

- **Never use an existing file as a dumping ground.** Before adding code, ask
  which responsibility it belongs to, whether that module exists, whether it is
  already too large, and whether it should be its own module. If it's a separate
  responsibility, **create a new module**.
- **No giant files** — prefer 20 focused modules over 5 giant modules. Split a
  file when it holds many unrelated responsibilities; line count alone is not
  the deciding factor (ADR-007).
- **MCP Modularization** (see §9): one module per tool category, one shared
  `McpServer`, stable tool names.
- **Don't create empty folders** — folder structure follows content.

ADRs: [`docs/decisions/adr-004`](docs/decisions/adr-004-file-responsibility.md),
[`adr-005`](docs/decisions/adr-005-mcp-modularization.md),
[`adr-007`](docs/decisions/adr-007-no-giant-files.md).

---

## 13. Testing rules

See [`docs/testing/README.md`](docs/testing/README.md).

Three suites:

- **Unit** (`tests/unit/`) — pure logic (config, models, analytics, strategy
  pricers). Offline, runs in CI.
- **Integration** (`tests/integration/`) — the layers above the broker, driven
  by an in-memory `FakeProvider` (`tests/integration/conftest.py`): provider
  factory, the **42-tool MCP inventory contract**, every Falcon route (happy +
  error paths), and the `run_all_tools()` batch. Offline, runs in CI.
- **Live** (`tests/live/`) — opt-in against the real Upstox API, gated by
  `pytest.mark.live` and `TBMCP_RUN_LIVE=1`. Never runs in CI.

Rules:

- A bare `python -m pytest` runs only unit + integration (set by
  `pyproject.toml` `testpaths`), so CI never touches the broker.
- **The 42 MCP tool names are a stable contract** — `tests/integration/
  test_mcp_server.py` asserts the exact inventory. After any MCP refactor, run
  it (or `python -c "import mcp.server as s; print(sorted(s.mcp.tools.methods))"`).
- CI (`.github/workflows/ci.yml`) runs: compileall syntax check, `main.py --help`
  smoke, and the offline pytest suites on every push/PR.
- `tests/tool_test.py` remains as a live one-off batch harness
  (`python tests/tool_test.py NIFTY`) requiring valid credentials.
- The batch logic lives in the production module `services/tools_runner.py`
  (the app must never depend on `tests/` to start).

---

## 14. Packaging rules

See [`docs/packaging/nuitka.md`](docs/packaging/nuitka.md).

- **Manual, release-only Nuitka onefile build** — you run it by hand on a
  Windows machine; CI never builds automatically (it only validates: syntax
  check, CLI smoke, offline tests):
  `python -m nuitka --onefile --include-package=zeromcp --include-data-dir=frontend=frontend --include-package=falcon,waitress,requests main.py`
- Produces a standalone `TBMcp.exe`; config/token live next to the exe
  (portable folder).
- Keep include flags in sync with `pyproject.toml` dependencies.
- `main.py` calls `multiprocessing.freeze_support()` for `both` mode under the
  frozen binary — don't remove it. Note: `--reload` is available for dev but
  not passed through to the child process in `both` mode (set explicitly when
  running `python main.py ui --reload`).

---

## 15. Security rules

- **Never commit credentials.** `.env` and `.upstox-token.json` are gitignored;
  a single `git add -A` would otherwise commit a working broker token. When
  staging, confirm neither file appears (`git status` must not list them).
- The dashboard binds `127.0.0.1` by default. If run on `0.0.0.0`, the entire
  credential surface (`/api/settings` GET returns the API key; POST writes
  credentials; `/upstox/callback` exchanges tokens) is exposed — do not do this
  casually.
- Frontend `innerHTML` with API/error strings is a latent XSS pattern — escape
  error text before insertion.
- Logs go to stderr (never stdout) so they can't corrupt the MCP JSON-RPC
  stream.

---

## 16. Important architectural decisions

Recorded as ADRs in [`docs/decisions/`](docs/decisions/README.md):

1. **ADR-001 — ZeroMCP engine** is the single MCP server (official-SDK `tools.py`
   retired). Engine vendored at `zeromcp/`, not pip-installed.
2. **ADR-002 — Falcon + static HTML/JS** dashboard instead of
   NiceGUI/PyWebIO/Flet (chosen for the cleanest Nuitka freeze).
3. **ADR-003 — DataProvider abstraction** — all broker access behind the
   `providers/base.py` protocol.
4. **ADR-004 — File Responsibility rule** (§11).
5. **ADR-005 — MCP Modularization** (§9).
6. **ADR-006 — Development Workflow** (§2).
7. **ADR-007 — No giant files** (§12).

History: [`docs/background.md`](docs/background.md).

---

## 17. Things AI agents MUST NOT change casually

These are load-bearing. Change only with an explicit, deliberate decision:

1. **MCP tool names** — the 42 registered names are a stable contract for
   existing AI clients. Internal refactoring must never rename a tool.
2. **The `DataProvider` abstraction** — do not bypass `providers/base.py` to call
   Upstox directly "because it's easier." A broker swap must require no tool/UI
   renames.
3. **The single shared `McpServer`** — do not create per-module server instances;
   `mcp/server.py` owns the one instance and registers every module's `TOOLS`.
4. **No frontend framework** — do not introduce React/Vue/Angular/Next.js
   without explicit approval; the frontend must stay static and build-free.
5. **`zeromcp/` (the fork)** — treat as an upstream sync target, not app code.
   Do not refactor or restyle it as part of app work.
6. **Shared analytics in `analytics/`** — do not duplicate a calculation into an
   MCP tool, a Falcon route, or frontend JS; implement it once and call it.
7. **The portable config layout** (`config.py`) — everything lives next to the
   app (repo root, or next to the `.exe` when frozen) with no dependency on the
   user's home directory. Do not add home-dir dependencies.
8. **Commit hygiene** — never stage `.env` / `.upstox-token.json`. Keep tool
   names verified after any move (`s.mcp.tools.methods`).

---

## Quick doc index

| Need | Go to |
|---|---|
| Product | [`docs/product.md`](docs/product.md) |
| Architecture & rules | [`docs/architecture.md`](docs/architecture.md) |
| Feature workflow | [`docs/development/workflow.md`](docs/development/workflow.md) |
| HTTP endpoints | [`docs/api/endpoints.md`](docs/api/endpoints.md) |
| MCP tools (42) | [`docs/mcp/tools.md`](docs/mcp/tools.md) |
| Frontend | [`docs/frontend/guide.md`](docs/frontend/guide.md) |
| Local setup/run | [`docs/development/local.md`](docs/development/local.md) |
| Testing | [`docs/testing/README.md`](docs/testing/README.md) |
| Nuitka packaging | [`docs/packaging/nuitka.md`](docs/packaging/nuitka.md) |
| Decisions (ADRs) | [`docs/decisions/README.md`](docs/decisions/README.md) |
| History | [`docs/background.md`](docs/background.md) |
