"""Live-broker smoke test (opt-in, never part of CI).

These tests hit the real Upstox API and require a working token, so they are
skipped unless the operator explicitly opts in:

    $env:RTMCP_RUN_LIVE = "1"
    .venv/Scripts/python -m pytest tests/live -m live

The production batch runner (:func:`services.tools_runner.run_all_tools`) is
exercised against the live ``DataProvider`` — the same code path the MCP server
and dashboard use — and any tool that fails for a reason other than a
market-info gap fails the test.
"""
from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("RTMCP_RUN_LIVE") != "1",
        reason="live Upstox tests: set RTMCP_RUN_LIVE=1 with valid credentials",
    ),
]


def test_run_all_tools_against_live_upstox() -> None:
    from config import load_settings
    from providers import create_provider
    from services.tools_runner import run_all_tools

    client = create_provider(load_settings())
    client.ensure_initialized()

    out = run_all_tools(client, "NIFTY")
    assert out["symbol"] == "NIFTY"

    failed = {
        name: r for name, r in out["results"].items()
        if not r.get("ok")
    }
    assert not failed, f"Live batch failures:\n{failed}"


def test_live_option_chain_and_analytics() -> None:
    from analytics import compute_atm, compute_pcr
    from config import load_settings
    from providers import create_provider

    client = create_provider(load_settings())
    client.ensure_initialized()

    chain = client.get_option_chain("NIFTY", client.get_expiry_dates("NIFTY")[0])
    assert chain.get("rows")
    assert compute_pcr(chain)["pcr"] > 0
    assert compute_atm(chain)["atmStrike"] is not None
