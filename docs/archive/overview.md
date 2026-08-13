# What is TBMCP?

**TBMCP** is a Python project that puts your Indian market data (NIFTY, BANKNIFTY
options, etc.) in front of two kinds of users:

1. **An AI assistant** (like Claude Desktop) — so it can answer questions about the market.
2. **You (a human)** — through a web dashboard you open in a browser.

Both sides read the same live data from the **Upstox** broker.

## The two deliverables

| Deliverable | For whom | What it is | How it runs |
|-------------|----------|------------|-------------|
| **MCP server (AI)** | The AI client | A server built on the forked *ZeroMCP* engine that exposes 3 data tools | `python main.py mcp` (stdio transport) |
| **Web dashboard (human)** | You | A web page with a live ticker, option-chain table, and charts | `python main.py ui` (Falcon web server, static HTML/JS) |

### The 3 AI tools
The MCP server currently exposes three tools (all backed by Upstox):
- `get_option_chain` — full option chain (calls + puts per strike)
- `get_expiry_dates` — available expiry dates for a symbol
- `get_spot_price` — current spot/last price of an index or stock

## Tech stack

- **Language:** Python (3.10+)
- **AI server engine:** ZeroMCP (a forked, zero-dependency MCP server framework) at `zeromcp/` (self-contained project at the repo root)
- **Human dashboard:** Falcon (a zero-dependency WSGI framework) serving a plain static `index.html` + JavaScript page, with charts drawn by the bundled lightweight-charts library (see [background.md](../background.md))
- **Data source:** Upstox v2 API via `client.UpstoxClient` / `providers.create_provider`
- **Credentials:** stored in a local `.env` file (API key, secret, redirect URI)

## Components at a glance

```
TBMCP/                       # git repo root = the app
├── main.py                  # entry point: `mcp` (AI server) and `ui` (dashboard) subcommands
├── config.py                # settings + portable .env handling
├── constants.py             # shared constants/enums
├── models.py                # data models (OptionChain, Candle, ...)
├── zeromcp/                 # the forked MCP server engine (self-contained project)
│   └── src/zeromcp/         #   the "AI engine" package (imported via sys.path)
├── analytics/               # chain-derived F&O analytics (pure functions)
├── providers/               # data-provider abstraction (swap brokers here)
├── mcp/                     # AI server: server.py + raw tools (market_data, options)
├── api/                     # Falcon web dashboard backend (app.py + routes/)
├── services/                # cross-layer services (tools_runner)
├── frontend/                # static HTML/JS dashboard (lightweight-charts)
├── tests/                   # tests
├── docs/                    # project docs (incl. PLAN_*.md)
└── pyproject.toml           # app package metadata (name="tbmcp")
```

See [architecture.md](../architecture.md) for how these pieces fit together and how to run them.
