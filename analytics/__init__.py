"""Derived F&O analytics - pure functions over the typed data models.

Nothing here touches the network or a broker. Every function takes an
`OptionChain` (or `FuturesChain`) and returns a small typed dict, so the same
analytics work whether the chain came from Upstox, a CSV, or a future provider.
The MCP tools and the dashboard call these after fetching a chain, keeping the
broker layer thin.
"""
from __future__ import annotations

from .option_chain import (
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
    classify_buildup,
    buildup_color,
)
from .strategies import price_strategy

__all__ = [
    "compute_pcr",
    "compute_max_pain",
    "compute_top_oi_strikes",
    "compute_atm",
    "compute_iv_skew",
    "compute_oi_buildup",
    "compute_support_resistance",
    "compute_straddle",
    "compute_gex",
    "compute_futures_basis",
    "price_strategy",
    "classify_buildup",
    "buildup_color",
]
