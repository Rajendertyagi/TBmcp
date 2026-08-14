# What is TBMCP?

**TBMCP** (package name `tbmcp`) is a Python project that puts Indian market
data (NIFTY, BANKNIFTY, FINNIFTY, SENSEX, India VIX options and futures, etc.)
in front of two kinds of users:

1. **An AI assistant** (e.g. Claude Desktop) — so it can answer questions about
   the market by calling MCP tools.
2. **A human** — through a web dashboard opened in a browser.

Both sides read the same live data through a shared provider layer. The primary
broker is **Upstox**; a secondary **FYERS** data source is available as a
fallback (or single-provider mode) when enabled. Routing is per-symbol with
sticky affinity so the AI view and the human view never disagree.

## The two deliverables

| Deliverable | For whom | What it is | How it runs |
|---|---|---|---|
| **MCP server (AI)** | The AI client | A server built on the forked ZeroMCP engine exposing **42 tools** (raw market data + fundamentals/news/Greeks + derived F&O analytics / strategy pricers) | `python main.py mcp` (stdio transport) |
| **Web dashboard (human)** | A human | A single-page app with a live ticker, option-chain table, charts, and one-click Upstox login | `python main.py ui` (Falcon web server, static HTML/JS) |

Both can run together with `python main.py` (default) or `python main.py both`.

## What it can do

- **Market data:** live quotes (LTP/OHLC), option chains, futures chains, expiry
  dates, historical candles, market depth, and exchange status/holidays/timings.
- **Fundamentals (stocks):** company profile, shareholding pattern, key ratios
  (P/E, ROE, ROCE, etc.), corporate actions (dividends, splits, bonuses),
  competitors, and news articles.
- **Option Greeks:** live IV, delta, gamma, theta, vega per strike via the V3
  market-quote endpoint.
- **Derived F&O analytics:** put-call ratio, max pain, top-OI strikes, ATM
  strike, IV skew, OI buildup classification, support/resistance, straddle
  pricing, gamma exposure, futures basis.
- **Strategy pricing:** long straddle, long strangle, bull call spread, bear put
  spread, iron condor, long butterfly.
- **Dashboard pages:** Home (overview cards), market pages per index, India VIX,
  chart builder, Tools (runs every tool once), and an Upstox settings/login page.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python **>= 3.11** | — |
| AI server engine | **ZeroMCP** — forked, zero-dependency MCP framework at `zeromcp/` | We control it; stdio transport; see [decisions/adr-001-zeromcp-engine.md](decisions/adr-001-zeromcp-engine.md) |
| Human dashboard backend | **Falcon** — zero-dependency WSGI framework | Cleanest Nuitka freeze; see [decisions/adr-002-falcon-dashboard.md](decisions/adr-002-falcon-dashboard.md) |
| Human dashboard frontend | **Vanilla JS** ES modules + HTML/CSS | No framework; see [frontend/guide.md](frontend/guide.md) |
| Charts | TradingView **lightweight-charts** v4 (bundled locally) | Browser-side; fed with Upstox candles |
| Data sources | **Upstox v2/v3** (`providers/upstox.py`) primary, **FYERS v3** (`providers/fyers.py`) secondary opt-in | Behind the `DataProvider` abstraction; see [decisions/adr-003-data-provider-abstraction.md](decisions/adr-003-data-provider-abstraction.md) + [decisions/adr-008-multi-provider-routing.md](decisions/adr-008-multi-provider-routing.md) |
| HTTP server (prod) | **Waitress** | Serves the Falcon app |
| Packaging | **Nuitka** onefile `.exe` (release only) | Single portable binary; see [packaging/nuitka.md](packaging/nuitka.md) |

Credentials live in a local `.env` file next to the app (API key, secret,
redirect URI); the OAuth token is stored in `.upstox-token.json` in the same
folder. See [development/local.md](development/local.md).
