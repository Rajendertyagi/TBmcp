"""Fundamentals and news tools exposed over MCP.

Each tool wraps a :meth:`DataProvider` method and returns JSON. Tool names are
a STABLE contract - the AI references them by name, so never rename or reorder
them without a coordinated migration.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

# Bound to the real provider by mcp.server at startup.
_client = None


async def get_company_profile(symbol: str) -> str:
    """Business description, sector, and sector market cap for a stock."""
    data = await asyncio.to_thread(_client.get_company_profile, _isin_of(symbol))
    return json.dumps(data, indent=2, default=str)


async def get_share_holdings(symbol: str) -> str:
    """Quarterly shareholding pattern: promoters, FII, DII, mutual funds, retail."""
    data = await asyncio.to_thread(_client.get_share_holdings, _isin_of(symbol))
    return json.dumps(data, indent=2, default=str)


async def get_key_ratios(symbol: str) -> str:
    """P/E, P/B, ROA, ROE, ROCE, EV/EBITDA with sector benchmarks."""
    data = await asyncio.to_thread(_client.get_key_ratios, _isin_of(symbol))
    return json.dumps(data, indent=2, default=str)


async def get_corporate_actions(symbol: str) -> str:
    """Dividends, bonuses, splits, rights issues with ex-dates and amounts."""
    data = await asyncio.to_thread(_client.get_corporate_actions, _isin_of(symbol))
    return json.dumps(data, indent=2, default=str)


async def get_competitors(symbol: str) -> str:
    """Peer companies with instrument keys and sector market cap."""
    data = await asyncio.to_thread(_client.get_competitors, _isin_of(symbol))
    return json.dumps(data, indent=2, default=str)


async def get_news(symbol: str) -> str:
    """News articles for a symbol (past 7 days, up to 100 items)."""
    key = _client.resolve_key(symbol)
    data = await asyncio.to_thread(_client.get_news, [key])
    return json.dumps(data, indent=2, default=str)


async def get_option_greeks(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Live option Greeks (IV, delta, gamma, theta, vega) for a symbol's chain.

    Fetches the option chain, extracts all instrument keys, then batch-fetches
    greeks via the V3 endpoint (up to 50 keys per call). Returns the raw greeks
    dict keyed by instrument key.
    """
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    rows = chain.get("rows", [])
    keys: list[str] = []
    for row in rows:
        for side in ("CE", "PE"):
            leg = row.get(side)
            if leg and leg.get("instrumentKey"):
                keys.append(leg["instrumentKey"])
    if not keys:
        return json.dumps({"error": f"no option keys found for {symbol}"}, indent=2)
    data = await asyncio.to_thread(_client.get_option_greeks, keys)
    return json.dumps(data, indent=2, default=str)


def _isin_of(symbol: str) -> str:
    """Extract ISIN from a resolved instrument key (``NSE_EQ|<ISIN>``)."""
    key = _client.resolve_key(symbol.strip().upper())
    if not (key.startswith("NSE_EQ|") or key.startswith("BSE_EQ|")):
        raise RuntimeError(
            f"[Fundamentals] Cannot derive ISIN from key '{key}' "
            f"(not an equity instrument) for symbol '{symbol}'."
        )
    return key.split("|", 1)[1]


TOOLS = [
    get_company_profile,
    get_share_holdings,
    get_key_ratios,
    get_corporate_actions,
    get_competitors,
    get_news,
    get_option_greeks,
]
