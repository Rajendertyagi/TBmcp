# MCP — Tools Reference

The MCP server exposes **35 tools** to AI clients. They are registered against a
single shared `McpServer` instance in `mcp/server.py`; the registered name is the
function's `__name__`, so **tool names are a stable contract** — internal
refactoring must never rename a tool (see
[decisions/adr-005-mcp-modularization.md](../decisions/adr-005-mcp-modularization.md)).

All tools return JSON **strings** (`json.dumps(..., indent=2, default=str)`).

## Raw market data (`mcp/market_data.py` — 19 tools)

| Tool | Args | Returns |
|---|---|---|
| `get_option_chain` | `symbol`, `expiry_date?` | Full option chain (calls + puts per strike). |
| `get_expiry_dates` | `symbol` | Available expiry dates for a symbol. |
| `get_spot_price` | `symbol` | Current spot/last price of an index or stock. |
| `get_full_quote` | `symbol` | Full quote (LTP, net change, OHLC). |
| `get_full_quotes` | `symbols: list[str]` | Full quotes for several symbols. |
| `get_historical_data` | `symbol`, `interval="day"`, `days=60` | Historical candles. |
| `get_futures_chain` | `symbol`, `expiry_date?` | Futures chain for a symbol. |
| `get_market_depth` | `symbol` | Market depth. |
| `get_margin` | `instruments: list[dict]` | Margin requirement for a list of instruments. |
| `get_pcr` | `symbol`, `expiry`, `date`, `bucket_interval=60` | Put-call ratio (Upstox market endpoint). |
| `get_max_pain` | `symbol`, `expiry`, `date`, `bucket_interval=60` | Max-pain strike (Upstox market endpoint). |
| `get_oi` | `symbol`, `expiry`, `date` | Open interest. |
| `get_change_oi` | `symbol`, `expiry`, `date`, `interval=1` | Change in open interest. |
| `get_fii` | `data_type="NSE_FO\|INDEX_FUTURES"`, `interval="1D"` | FII data. |
| `get_dii` | `data_type="NSE_EQ\|CASH"`, `interval="1D"` | DII data. |
| `get_market_status` | `exchange="NSE"` | Exchange open/closed status. |
| `get_market_holidays` | `date?` | Market holidays. |
| `get_market_timings` | `date` | Market timings for a date. |
| `get_instruments` | `query`, `exchange="NSE"` | Instrument search. |

## Derived analytics (`mcp/options.py` — 10 tools)

Each tool fetches one option chain and computes a local metric using the pure
functions in `analytics/` (no extra API call).

| Tool | Args | Computes |
|---|---|---|
| `compute_pcr` | `symbol`, `expiry_date?` | Put-call ratio from total OI. |
| `compute_max_pain` | `symbol`, `expiry_date?` | Max-pain strike. |
| `compute_top_oi_strikes` | `symbol`, `expiry_date?`, `n=5` | Highest-OI call and put strikes (battle levels). |
| `compute_atm` | `symbol`, `expiry_date?` | At-the-money strike. |
| `compute_iv_skew` | `symbol`, `expiry_date?` | OTM put IV minus OTM call IV. |
| `compute_oi_buildup` | `symbol`, `expiry_date?` | Leg count per buildup tag (Long/Short Buildup, ...). |
| `compute_support_resistance` | `symbol`, `expiry_date?` | Support (max put OI) / resistance (max call OI). |
| `compute_straddle` | `symbol`, `expiry_date?` | ATM straddle cost + breakevens. |
| `compute_gex` | `symbol`, `expiry_date?` | Gamma-exposure proxy. |
| `compute_futures_basis` | `symbol`, `expiry_date?` | Futures premium/discount vs spot. |

## Strategy pricers (`mcp/options.py` — 6 tools)

Each prices a multi-leg options strategy from a fetched chain.

| Tool | Args | Strategy |
|---|---|---|
| `price_long_straddle` | `symbol`, `expiry_date?`, `strike?` | Buy ATM call + buy ATM put. |
| `price_long_strangle` | `symbol`, `call_strike`, `put_strike`, `expiry_date?` | Buy OTM call + buy OTM put. |
| `price_bull_call_spread` | `symbol`, `lower_strike`, `higher_strike`, `expiry_date?` | Buy lower call, sell higher call. |
| `price_bear_put_spread` | `symbol`, `higher_strike`, `lower_strike`, `expiry_date?` | Buy higher put, sell lower put. |
| `price_iron_condor` | `symbol`, `put_sell_strike`, `put_buy_strike`, `call_buy_strike`, `call_sell_strike`, `expiry_date?` | Sell OTM put/buy lower put, buy OTM call/sell higher call. |
| `price_long_butterfly` | `symbol`, `lower_strike`, `middle_strike`, `upper_strike`, `expiry_date?` | Buy lower call, sell 2× middle call, buy upper call. |

## How tools are registered

```python
# mcp/server.py (assembly only)
mcp = McpServer("tbmcp", instructions=(...))
for _fn in market_data.TOOLS + options.TOOLS:
    mcp.tool()(_fn)
```

Each module keeps a module-level `_client = None`; `server.py` injects the real
provider at startup (`market_data._client = client`), so tool modules stay
decoupled from provider construction.

## Verify the inventory

```bash
python -c "import mcp.server as s; print(sorted(s.mcp.tools.methods))"
```
