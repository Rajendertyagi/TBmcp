"""Raw Upstox market-data tools exposed over MCP.

One thin async wrapper per ``DataProvider`` method (:mod:`providers`). The
functions are plain (undecorated) so this module never imports the server
instance; :mod:`mcp.server` binds them to the MCP registry at startup.

Tool names are a STABLE contract - the AI references them by name, so never
rename or reorder them without a coordinated migration.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

# Bound to the real provider by mcp.server at startup (avoids a circular import).
_client = None


async def get_option_chain(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Full option chain (calls + puts per strike with OI, OI %, LTP %, IV, Greeks, buildup tag).

    Args:
        symbol: Index or stock, e.g. 'NIFTY', 'BANKNIFTY', 'RELIANCE'.
        expiry_date: Optional 'YYYY-MM-DD'; defaults to the nearest expiry.
    """
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(chain, indent=2, default=str)


async def get_expiry_dates(symbol: str) -> str:
    """List available option expiry dates for a symbol."""
    dates = await asyncio.to_thread(_client.get_expiry_dates, symbol)
    return json.dumps(dates, indent=2)


async def get_spot_price(symbol: str) -> str:
    """Current spot/last price of an index or stock."""
    price = await asyncio.to_thread(_client.get_spot_price, symbol)
    return json.dumps({"symbol": symbol, "last_price": price}, indent=2)


async def get_full_quote(symbol: str) -> str:
    """Last price, net change and percent change for one symbol (index or stock)."""
    q = await asyncio.to_thread(_client.get_full_quote, symbol)
    return json.dumps({"symbol": symbol, **q}, indent=2)


async def get_full_quotes(symbols: list[str]) -> str:
    """Batched last price / change for many symbols in one call (e.g. a watchlist)."""
    out = await asyncio.to_thread(_client.get_full_quotes, symbols)
    return json.dumps(out, indent=2)


async def get_historical_data(symbol: str, interval: str = "day", days: int = 60) -> str:
    """OHLC candles for a symbol. interval: day|1minute|30minute|week|month."""
    candles = await asyncio.to_thread(_client.get_historical_data, symbol, interval, days)
    return json.dumps(candles, indent=2, default=str)


async def get_futures_chain(symbol: str, expiry_date: Optional[str] = None) -> str:
    """All futures contracts for a symbol across expiries, with live quotes and OI."""
    chain = await asyncio.to_thread(_client.get_futures_chain, symbol, expiry_date)
    return json.dumps(chain, indent=2, default=str)


async def get_market_depth(symbol: str) -> str:
    """Top-of-book order book (5 bid + 5 ask levels) for a symbol."""
    depth = await asyncio.to_thread(_client.get_market_depth, symbol)
    return json.dumps(depth, indent=2, default=str)


async def get_margin(instruments: list[dict]) -> str:
    """Required margin for a basket of instruments (max 20).

    Each instrument: {"instrument_key": "...", "quantity": int, "transaction_type":
    "BUY"|"SELL", "product": "I"|"D"|"CO"|"MTF", "price"?: float}.
    """
    margin = await asyncio.to_thread(_client.get_margin, instruments)
    return json.dumps(margin, indent=2, default=str)


async def get_pcr(symbol: str, expiry: str, date: str, bucket_interval: int = 60) -> str:
    """Put-Call Ratio for an underlying on a given expiry/date (Upstox Market Info)."""
    data = await asyncio.to_thread(_client.get_pcr, symbol, expiry, date, bucket_interval)
    return json.dumps(data, indent=2, default=str)


async def get_max_pain(symbol: str, expiry: str, date: str, bucket_interval: int = 60) -> str:
    """Max Pain strike for an underlying on a given expiry/date (Upstox Market Info)."""
    data = await asyncio.to_thread(_client.get_max_pain, symbol, expiry, date, bucket_interval)
    return json.dumps(data, indent=2, default=str)


async def get_oi(symbol: str, expiry: str, date: str) -> str:
    """Open Interest across all strikes for an underlying (Upstox Market Info)."""
    data = await asyncio.to_thread(_client.get_oi, symbol, expiry, date)
    return json.dumps(data, indent=2, default=str)


async def get_change_oi(symbol: str, expiry: str, date: str, interval: int = 1) -> str:
    """Change in Open Interest per strike over `interval` days (Upstox Market Info)."""
    data = await asyncio.to_thread(_client.get_change_oi, symbol, expiry, date, interval)
    return json.dumps(data, indent=2, default=str)


async def get_fii(data_type: str = "NSE_FO|INDEX_FUTURES", interval: str = "1D") -> str:
    """Foreign Institutional Investor activity (Upstox Market Info).

    data_type: segment e.g. 'NSE_FO|INDEX_FUTURES', 'NSE_FO|STOCK_FUTURES'.
    interval: '1D' or '1M'.
    """
    data = await asyncio.to_thread(_client.get_fii, data_type, interval)
    return json.dumps(data, indent=2, default=str)


async def get_dii(data_type: str = "NSE_EQ|CASH", interval: str = "1D") -> str:
    """Domestic Institutional Investor activity (Upstox Market Info).

    data_type: segment e.g. 'NSE_EQ|CASH', 'BSE_EQ|CASH'. interval: '1D' or '1M'.
    """
    data = await asyncio.to_thread(_client.get_dii, data_type, interval)
    return json.dumps(data, indent=2, default=str)


async def get_market_status(exchange: str = "NSE") -> str:
    """Trading status for an exchange (NSE, BSE, NSE_FO, ...)."""
    data = await asyncio.to_thread(_client.get_market_status, exchange)
    return json.dumps(data, indent=2, default=str)


async def get_market_holidays(date: Optional[str] = None) -> str:
    """Trading holidays. `date` (yyyy-mm-dd) is optional; omit for the full list."""
    data = await asyncio.to_thread(_client.get_market_holidays, date)
    return json.dumps(data, indent=2, default=str)


async def get_market_timings(date: str) -> str:
    """Market session timings for a date (yyyy-mm-dd) — required."""
    data = await asyncio.to_thread(_client.get_market_timings, date)
    return json.dumps(data, indent=2, default=str)


async def get_instruments(query: str, exchange: str = "NSE") -> str:
    """Search tradable instruments by name or symbol."""
    data = await asyncio.to_thread(_client.get_instruments, query, exchange)
    return json.dumps(data, indent=2, default=str)


TOOLS = [
    get_option_chain,
    get_expiry_dates,
    get_spot_price,
    get_full_quote,
    get_full_quotes,
    get_historical_data,
    get_futures_chain,
    get_market_depth,
    get_margin,
    get_pcr,
    get_max_pain,
    get_oi,
    get_change_oi,
    get_fii,
    get_dii,
    get_market_status,
    get_market_holidays,
    get_market_timings,
    get_instruments,
]
