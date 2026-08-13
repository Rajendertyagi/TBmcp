"""MCP server (AI-facing) built on the forked zeromcp engine.

Serves the raw market-data tools (:mod:`mcp.market_data`) and the derived
F&O analytics / strategy-pricing tools (:mod:`mcp.options`) through the
designated AI engine (zeromcp/). Run via `python main.py mcp`.

Tool names are a STABLE contract: raw data comes from where the `DataProvider`
sits (so a broker swap needs no rename), and chain-derived analytics live in
`analytics` as pure functions over the `OptionChain` model.
"""
from __future__ import annotations

import os
import sys

# Make the local forked zeromcp package importable without a pip install.
# The engine is a self-contained project at zeromcp/ (repo root) with a
# src-layout, so the importable package directory is <repo>/zeromcp/src.
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zeromcp", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from zeromcp import McpServer

from config import load_settings
from providers import create_provider

from . import fundamentals, market_data, options

client = create_provider(load_settings())
fundamentals._client = client
market_data._client = client
options._client = client

mcp = McpServer(
    "tbmcp",
    instructions=(
        "TBMCP provides Indian equity/options/futures market data, fundamentals, Greeks, and F&O "
        "analytics via the Upstox broker API. Raw data tools: get_option_chain, get_expiry_dates, "
        "get_spot_price, get_full_quote(s), get_historical_data, get_futures_chain, "
        "get_market_depth, get_margin, get_pcr, get_max_pain, get_oi, get_change_oi, get_fii, "
        "get_dii, get_market_status, get_market_holidays, get_market_timings, get_instruments. "
        "Fundamentals (by stock ISIN): get_company_profile, get_share_holdings, get_key_ratios, "
        "get_corporate_actions, get_competitors, get_news. Option Greeks: get_option_greeks "
        "(fetches chain keys then batch-fetches live IV/delta/gamma/theta/vega). Derived analytics "
        "(no extra API call - computed from a chain you already fetched): compute_pcr, "
        "compute_max_pain, compute_top_oi_strikes, compute_atm, compute_iv_skew, "
        "compute_oi_buildup, compute_support_resistance, compute_straddle, compute_gex, "
        "compute_futures_basis. Strategy pricers: price_long_straddle, price_long_strangle, "
        "price_bull_call_spread, price_bear_put_spread, price_iron_condor, price_long_butterfly."
    ),
)

# Bind every tool to the registry. The tool name is the function's __name__,
# which keeps the AI-facing names identical to the old flat mcp_server.py.
for _fn in fundamentals.TOOLS + market_data.TOOLS + options.TOOLS:
    mcp.tool()(_fn)

__all__ = ["mcp", "client"]
