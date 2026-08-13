# TBMCP — Architecture

This document is the **permanent engineering contract** for this repository.
It describes how the code is organized, the important boundaries, and the rules
that govern changes. A new AI coding agent should read this first.

For *what the product is* see [product.md](product.md); for *why decisions were
made* see [background.md](background.md) and [decisions/](decisions/README.md).

---

## Repository layout

```
TBMCP/                       # git repo root = the app
├── main.py                  # entry point: `mcp`, `ui`, `both` subcommands
├── config.py                # settings + portable .env/.token paths
├── constants.py             # every magic value (URLs, lot sizes, colours, defaults)
├── models.py                # typed data models (OptionChain, Candle, FuturesChain, ...)
│
├── providers/               # DataProvider abstraction (swap brokers here)
│   ├── __init__.py          #   create_provider() factory + re-exports
│   ├── base.py              #   30-method DataProvider protocol
│   └── upstox.py            #   UpstoxClient assembler — composed of domain mixins:
│       ├── upstox_parsing.py      #     raw-response parsing + debug dumps
│       ├── upstox_connect.py      #     auth + token lifecycle + rate-limited transport
│       ├── upstox_resolution.py   #     symbol → instrument-key / lot-size resolution
│       ├── upstox_market_data.py  #     chains, quotes, futures, depth, margin, market info
│       └── upstox_fundamentals.py #     fundamentals / news / option Greeks
│
├── analytics/               # derived F&O analytics — pure functions over models
│   ├── __init__.py          #   re-exports 13 public names
│   └── options.py           #   compute_* / price_strategy / classify_buildup
│
├── mcp/                     # AI-facing MCP server
│   ├── server.py            #   assembly: shared McpServer + tool registration
│   ├── market_data.py       #   19 raw data tools (get_*)
│   ├── fundamentals.py      #   7 fundamentals/news/Greeks tools
│   └── options.py           #   16 derived/strategy tools (compute_*, price_*)
│
├── api/                     # human-facing Falcon web dashboard
│   ├── app.py               #   WSGI assembly: create_app/build_app + helpers
│   ├── render.py            #   pure HTML rendering for the chain table
│   └── routes/              #   one Resource class per HTTP endpoint, split by
│       ├── market.py        #     responsibility (re-exported via __init__.py):
│       ├── fundamentals.py  #     market data (ticker/quote/chain/expiries/history/vix)
│       ├── auth.py          #     fundamentals / news / option Greeks
│       ├── tools.py         #     settings + OAuth login flow
│       └── __init__.py      #     "test all" batch (Tools page)
│
├── services/
│   └── tools_runner.py      # runs every tool once ("Test All" batch, shared logic)
│
├── frontend/                # static HTML/JS single-page app (see frontend/guide.md)
├── tests/                   # see testing/README.md
├── zeromcp/                 # the forked ZeroMCP engine (self-contained project)
│   └── src/zeromcp/         #   the importable engine package
├── docs/                    # you are here
└── pyproject.toml           # app package metadata (name="tbmcp")
```

The fork `zeromcp/` is a **self-contained project** (its own `pyproject.toml`,
`uv.lock`, README, examples, CI). It is not pip-installed; the app adds
`zeromcp/src` to `sys.path` at import time (see "Engine import" below).

## Architectural layers

```
DataProvider  (providers/)  — one broker adapter behind a stable protocol
     ↓
Typed Models  (models.py)   — OptionChain, Candle, FuturesChain, ...
     ↓
Analytics     (analytics/)  — pure functions, no network, broker-agnostic
     ↓
 ┌──────────────┬──────────────┐
 │              │              │
 MCP            Falcon        (frontend/)
 │              │              │
 AI             Web UI
```

Rules implied by this diagram:

- **`DataProvider` is a hard boundary.** A new broker/data source must be able to
  fit behind `providers/base.py` without changing MCP tools or frontend pages.
  Do not bypass this abstraction because calling the current broker directly is
  easier. (Rationale: [decisions/adr-003-data-provider-abstraction.md](decisions/adr-003-data-provider-abstraction.md).)
- **Analytics are broker-agnostic.** Do not duplicate calculations across MCP
  tools, Falcon routes, frontend JS, and broker clients. Implement shared logic
  once in `analytics/` and call it from both servers.

## Key patterns

### Engine import (`mcp/server.py`)

The forked ZeroMCP engine lives at `zeromcp/src` (src-layout). `mcp/server.py`
adds it to `sys.path`:

```python
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zeromcp", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
from zeromcp import McpServer
```

### MCP assembly — one shared instance

`mcp/server.py` is **assembly only**: it builds the single `McpServer`, injects
the data client into each tool module (`market_data._client = client`), and
registers every tool from each module's `TOOLS` list:

```python
for _fn in fundamentals.TOOLS + market_data.TOOLS + options.TOOLS:
    mcp.tool()(_fn)
```

The registered tool name is the function's `__name__`, which keeps AI-facing
names stable regardless of internal layout. See [mcp/tools.md](mcp/tools.md) and
[decisions/adr-005-mcp-modularization.md](decisions/adr-005-mcp-modularization.md).

### Lazy / rebuildable client (`api/app.py`)

The Falcon app holds a module-level `_client = None`; `get_client()` creates it
on first use and `rebuild_client()` recreates it after a credential change — so
settings edits take effect without a restart.

### Error handling

Client calls are wrapped with `_safe()` in the API layer: a failure returns
`{"error": ...}` instead of raising, so the UI always gets a JSON body. MCP tools
return `json.dumps(...)` strings; the engine handles tool errors.

## Rules

1. **File Responsibility** — every important file has a clear reason to change;
   name files for their responsibility, not their position. Never use an
   existing file as a dumping ground. Details:
   [decisions/adr-004-file-responsibility.md](decisions/adr-004-file-responsibility.md).
2. **MCP Modularization** — no single enormous `mcp_server.py`; one module per
   tool category, all registered against the one shared `McpServer`; tool names
   are a stable contract. Details:
   [decisions/adr-005-mcp-modularization.md](decisions/adr-005-mcp-modularization.md).
3. **Frontend: no framework.** The dashboard is intentionally vanilla JS ES
   modules + HTML/CSS (see [frontend/guide.md](frontend/guide.md)). Do not
   introduce React/Vue/Angular/Next.js unless explicitly approved.
4. **Backend: keep it personal/local.** This is not a SaaS product. Do not add
   multi-user infra, billing, unnecessary auth systems, or cloud architecture
   unless explicitly requested.
5. **Don't create empty folders.** Folder structure follows content; introduce a
   directory when its contents justify it (Phase 4 direction).
6. **Development Workflow** — every new feature follows the fixed 7-step
   sequence (understand → ownership → modularity → implement → test → document →
   report), and major restructuring stops and is reported before proceeding.
   Details: [decisions/adr-006-development-workflow.md](decisions/adr-006-development-workflow.md)
   + [development/workflow.md](development/workflow.md).
7. **No giant files** — do not let files balloon to thousands of lines just
   because the application grew. Prefer 20 focused modules over 5 giant ones;
   split a file when it holds many unrelated responsibilities (line count is a
   smell, not the rule). Details:
   [decisions/adr-007-no-giant-files.md](decisions/adr-007-no-giant-files.md).

## What is explicitly NOT here

- **Run/setup instructions** → [development/local.md](development/local.md)
- **HTTP endpoint reference** → [api/endpoints.md](api/endpoints.md)
- **MCP tool reference** → [mcp/tools.md](mcp/tools.md)
- **Nuitka release build** → [packaging/nuitka.md](packaging/nuitka.md)
- **History and rationale** → [background.md](background.md) + [decisions/](decisions/README.md)
