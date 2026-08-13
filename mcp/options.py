"""Derived F&O analytics + strategy-pricing tools exposed over MCP.

Each tool fetches an option chain once and computes a local metric using the
pure functions in :mod:`analytics`. The analytics imports are aliased with a
leading underscore so a tool's name (e.g. ``compute_pcr``) never shadows the
analytics function it calls - the old flat ``mcp_server.py`` had exactly that
bug, and every ``compute_*`` tool raised a TypeError at runtime.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from analytics import (
    compute_atm as _compute_atm,
    compute_futures_basis as _compute_futures_basis,
    compute_gex as _compute_gex,
    compute_iv_skew as _compute_iv_skew,
    compute_max_pain as _compute_max_pain,
    compute_oi_buildup as _compute_oi_buildup,
    compute_pcr as _compute_pcr,
    compute_support_resistance as _compute_support_resistance,
    compute_straddle as _compute_straddle,
    compute_top_oi_strikes as _compute_top_oi_strikes,
    price_strategy as _price_strategy,
)

# Bound to the real provider by mcp.server at startup.
_client = None


async def compute_pcr(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Put-Call Ratio from total OI of a fetched chain (no extra API call)."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_pcr(chain), indent=2, default=str)


async def compute_max_pain(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Max Pain strike computed from a fetched chain (no extra API call)."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_max_pain(chain), indent=2, default=str)


async def compute_top_oi_strikes(symbol: str, expiry_date: Optional[str] = None, n: int = 5) -> str:
    """Strikes with the highest call OI and highest put OI (key battle levels)."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_top_oi_strikes(chain, n), indent=2, default=str)


async def compute_atm(symbol: str, expiry_date: Optional[str] = None) -> str:
    """At-the-money strike for the underlying's current value."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_atm(chain), indent=2, default=str)


async def compute_iv_skew(symbol: str, expiry_date: Optional[str] = None) -> str:
    """IV skew: average OTM put IV minus OTM call IV (negative = fear premium)."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_iv_skew(chain), indent=2, default=str)


async def compute_oi_buildup(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Count of legs per buildup tag (Long/Short Buildup, Long Unwinding, ...)."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_oi_buildup(chain), indent=2, default=str)


async def compute_support_resistance(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Support (max put OI) and resistance (max call OI) from the chain."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_support_resistance(chain), indent=2, default=str)


async def compute_straddle(symbol: str, expiry_date: Optional[str] = None) -> str:
    """ATM straddle cost and its two breakeven levels."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_straddle(chain), indent=2, default=str)


async def compute_gex(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Gamma Exposure proxy: net (gamma * OI) across calls minus puts."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    return json.dumps(_compute_gex(chain), indent=2, default=str)


async def compute_futures_basis(symbol: str, expiry_date: Optional[str] = None) -> str:
    """Futures premium/discount vs spot for each expiry (cost-of-carry)."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    spot = chain.get("underlyingValue", 0)
    futures = await asyncio.to_thread(_client.get_futures_chain, symbol, expiry_date)
    return json.dumps(_compute_futures_basis(futures, spot), indent=2, default=str)


async def price_long_straddle(symbol: str, expiry_date: Optional[str] = None, strike: Optional[float] = None) -> str:
    """Long straddle: buy ATM call + buy ATM put. Profits on big moves either way."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    atm = strike or _compute_atm(chain)["atmStrike"]
    legs = [
        {"strike": atm, "type": "CE", "qty": 1, "side": "BUY"},
        {"strike": atm, "type": "PE", "qty": 1, "side": "BUY"},
    ]
    return json.dumps(_price_strategy("long_straddle", chain, legs), indent=2, default=str)


async def price_long_strangle(symbol: str, call_strike: float, put_strike: float, expiry_date: Optional[str] = None) -> str:
    """Long strangle: buy OTM call + buy OTM put. Cheaper than a straddle, needs bigger move."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    legs = [
        {"strike": call_strike, "type": "CE", "qty": 1, "side": "BUY"},
        {"strike": put_strike, "type": "PE", "qty": 1, "side": "BUY"},
    ]
    return json.dumps(_price_strategy("long_strangle", chain, legs), indent=2, default=str)


async def price_bull_call_spread(symbol: str, lower_strike: float, higher_strike: float, expiry_date: Optional[str] = None) -> str:
    """Bull call spread: buy lower-strike call, sell higher-strike call. Capped upside."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    legs = [
        {"strike": lower_strike, "type": "CE", "qty": 1, "side": "BUY"},
        {"strike": higher_strike, "type": "CE", "qty": 1, "side": "SELL"},
    ]
    return json.dumps(_price_strategy("bull_call_spread", chain, legs), indent=2, default=str)


async def price_bear_put_spread(symbol: str, higher_strike: float, lower_strike: float, expiry_date: Optional[str] = None) -> str:
    """Bear put spread: buy higher-strike put, sell lower-strike put. Capped downside."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    legs = [
        {"strike": higher_strike, "type": "PE", "qty": 1, "side": "BUY"},
        {"strike": lower_strike, "type": "PE", "qty": 1, "side": "SELL"},
    ]
    return json.dumps(_price_strategy("bear_put_spread", chain, legs), indent=2, default=str)


async def price_iron_condor(symbol: str, put_sell_strike: float, put_buy_strike: float,
                            call_buy_strike: float, call_sell_strike: float,
                            expiry_date: Optional[str] = None) -> str:
    """Iron condor: sell OTM put, buy lower put, buy OTM call, sell higher call. Range-bound income."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    legs = [
        {"strike": put_sell_strike, "type": "PE", "qty": 1, "side": "SELL"},
        {"strike": put_buy_strike, "type": "PE", "qty": 1, "side": "BUY"},
        {"strike": call_buy_strike, "type": "CE", "qty": 1, "side": "BUY"},
        {"strike": call_sell_strike, "type": "CE", "qty": 1, "side": "SELL"},
    ]
    return json.dumps(_price_strategy("iron_condor", chain, legs), indent=2, default=str)


async def price_long_butterfly(symbol: str, lower_strike: float, middle_strike: float, upper_strike: float,
                               expiry_date: Optional[str] = None) -> str:
    """Long butterfly: buy lower call, sell 2 middle calls, buy upper call. Profits at middle."""
    chain = await asyncio.to_thread(_client.get_option_chain, symbol, expiry_date)
    legs = [
        {"strike": lower_strike, "type": "CE", "qty": 1, "side": "BUY"},
        {"strike": middle_strike, "type": "CE", "qty": 2, "side": "SELL"},
        {"strike": upper_strike, "type": "CE", "qty": 1, "side": "BUY"},
    ]
    return json.dumps(_price_strategy("long_butterfly", chain, legs), indent=2, default=str)


TOOLS = [
    compute_pcr,
    compute_max_pain,
    compute_top_oi_strikes,
    compute_atm,
    compute_iv_skew,
    compute_oi_buildup,
    compute_support_resistance,
    compute_straddle,
    compute_gex,
    compute_futures_basis,
    price_long_straddle,
    price_long_strangle,
    price_bull_call_spread,
    price_bear_put_spread,
    price_iron_condor,
    price_long_butterfly,
]
