"""MCP server boundary: the 42 registered tool names are a STABLE contract.

This replaces the old inline CI inventory check with a real test. If a refactor
renames a tool, this suite fails loudly.
"""
from __future__ import annotations

import mcp.fundamentals as fundamentals
import mcp.market_data as market_data
import mcp.options as options

# Golden contract — the exact 42 registered tool names (see docs/mcp/tools.md).
EXPECTED_MARKET_DATA_TOOLS = [
    "get_change_oi",
    "get_dii",
    "get_expiry_dates",
    "get_fii",
    "get_full_quote",
    "get_full_quotes",
    "get_futures_chain",
    "get_historical_data",
    "get_instruments",
    "get_margin",
    "get_market_depth",
    "get_market_holidays",
    "get_market_status",
    "get_market_timings",
    "get_max_pain",
    "get_oi",
    "get_option_chain",
    "get_pcr",
    "get_spot_price",
]

EXPECTED_OPTIONS_TOOLS = [
    "compute_atm",
    "compute_futures_basis",
    "compute_gex",
    "compute_iv_skew",
    "compute_max_pain",
    "compute_oi_buildup",
    "compute_pcr",
    "compute_straddle",
    "compute_support_resistance",
    "compute_top_oi_strikes",
    "price_bear_put_spread",
    "price_bull_call_spread",
    "price_iron_condor",
    "price_long_butterfly",
    "price_long_straddle",
    "price_long_strangle",
]

EXPECTED_FUNDAMENTALS_TOOLS = [
    "get_company_profile",
    "get_share_holdings",
    "get_key_ratios",
    "get_corporate_actions",
    "get_competitors",
    "get_news",
    "get_option_greeks",
]

EXPECTED_ALL = sorted(
    EXPECTED_MARKET_DATA_TOOLS + EXPECTED_OPTIONS_TOOLS + EXPECTED_FUNDAMENTALS_TOOLS
)


class TestToolInventory:
    def test_module_tool_lists_match_the_contract(self):
        assert sorted(f.__name__ for f in market_data.TOOLS) == sorted(EXPECTED_MARKET_DATA_TOOLS)
        assert sorted(f.__name__ for f in options.TOOLS) == sorted(EXPECTED_OPTIONS_TOOLS)
        assert sorted(f.__name__ for f in fundamentals.TOOLS) == sorted(EXPECTED_FUNDAMENTALS_TOOLS)

    def test_registered_server_methods_are_the_42_contract(self, monkeypatch):
        monkeypatch.delenv("TBMCP_PROVIDER", raising=False)
        import mcp.server as server

        names = sorted(server.mcp.tools.methods)
        assert names == EXPECTED_ALL
        assert len(names) == 42

    def test_registered_name_is_the_function_name(self, monkeypatch):
        monkeypatch.delenv("TBMCP_PROVIDER", raising=False)
        import mcp.server as server

        for fn in market_data.TOOLS + options.TOOLS + fundamentals.TOOLS:
            assert fn.__name__ in server.mcp.tools.methods
