"""Unit tests for the MCP tool functions (:mod:`mcp.market_data`,
:mod:`mcp.options`).

Each tool is a thin async wrapper: fetch from ``_client`` (bound at startup by
``mcp.server``), compute via the pure ``analytics`` functions, and return a
``json.dumps`` string. These tests run **all 35 tools** against a recording
stub client — no network, no credentials — and assert the JSON contract,
argument forwarding, and the key computed values.

They double as the regression test for the old flat-server shadowing bug,
where every ``compute_*`` tool raised ``TypeError`` at runtime because the
tool name shadowed the analytics function it called.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import mcp.fundamentals as fundamentals
import mcp.market_data as market_data
import mcp.options as options

from tests.unit.conftest import make_option_chain


def _futures_chain() -> dict:
    return {
        "symbol": "NIFTY",
        "underlyingValue": 20000.0,
        "expiryDates": ["2025-01-30", "2025-02-27"],
        "legs": [
            {"instrumentKey": "NSE_INDEX|Nifty 50", "expiryDate": "2025-01-30",
             "strikePrice": 0.0, "lastPrice": 20100.0, "change": 0.0, "pChange": 0.0,
             "openInterest": 1000, "volume": 1000, "lotSize": 50},
        ],
        "timestamp": "2025-01-24T10:00:00+05:30",
    }


class StubClient:
    """DataProvider-shaped stub: records every call, returns canned values."""

    def __init__(self, chain: dict, futures: dict) -> None:
        self.chain = chain
        self.futures = futures
        self.calls: list[tuple] = []

    def get_option_chain(self, symbol, expiry_date=None):
        self.calls.append(("get_option_chain", symbol, expiry_date))
        return self.chain

    def get_futures_chain(self, symbol, expiry_date=None):
        self.calls.append(("get_futures_chain", symbol, expiry_date))
        return self.futures

    def get_expiry_dates(self, symbol):
        self.calls.append(("get_expiry_dates", symbol))
        return ["2025-01-30", "2025-02-27"]

    def get_spot_price(self, symbol):
        self.calls.append(("get_spot_price", symbol))
        return 20000.0

    def get_full_quote(self, symbol):
        self.calls.append(("get_full_quote", symbol))
        return {"last_price": 20000.0, "net_change": 10.0, "p_change": 0.05}

    def get_full_quotes(self, symbols):
        self.calls.append(("get_full_quotes", symbols))
        return {s: {"last_price": 20000.0, "net_change": 0.0, "p_change": 0.0} for s in symbols}

    def get_historical_data(self, symbol, interval, days):
        self.calls.append(("get_historical_data", symbol, interval, days))
        return [{"time": 1700000000, "open": 100.0, "high": 110.0,
                 "low": 90.0, "close": 105.0, "volume": 1000.0}]

    def get_market_depth(self, symbol):
        self.calls.append(("get_market_depth", symbol))
        return {"symbol": symbol, "buy": [], "sell": []}

    def get_margin(self, instruments):
        self.calls.append(("get_margin", instruments))
        return {"requiredMargin": 50000.0, "finalMargin": 50000.0, "margins": []}

    def get_pcr(self, symbol, expiry, date, bucket_interval=60):
        self.calls.append(("get_pcr", symbol, expiry, date, bucket_interval))
        return {"pcr": 1.1}

    def get_max_pain(self, symbol, expiry, date, bucket_interval=60):
        self.calls.append(("get_max_pain", symbol, expiry, date, bucket_interval))
        return {"max_pain": 20000.0}

    def get_oi(self, symbol, expiry, date):
        self.calls.append(("get_oi", symbol, expiry, date))
        return {"oi": 1000}

    def get_change_oi(self, symbol, expiry, date, interval=1):
        self.calls.append(("get_change_oi", symbol, expiry, date, interval))
        return {"change_oi": 50}

    def get_fii(self, data_type="NSE_FO|INDEX_FUTURES", interval="1D"):
        self.calls.append(("get_fii", data_type, interval))
        return {"fii": 100}

    def get_dii(self, data_type="NSE_EQ|CASH", interval="1D"):
        self.calls.append(("get_dii", data_type, interval))
        return {"dii": 200}

    def get_market_status(self, exchange="NSE"):
        self.calls.append(("get_market_status", exchange))
        return {"exchange": exchange, "status": "open"}

    def get_market_holidays(self, date=None):
        self.calls.append(("get_market_holidays", date))
        return [{"date": "2025-01-26", "trading": False}]

    def get_market_timings(self, date):
        self.calls.append(("get_market_timings", date))
        return {"date": date, "open": "09:15", "close": "15:30"}

    def get_instruments(self, query, exchange="NSE"):
        self.calls.append(("get_instruments", query, exchange))
        return [{"trading_symbol": query, "exchange": exchange}]

    # fundamentals / news / greeks
    def resolve_key(self, symbol):
        self.calls.append(("resolve_key", symbol))
        return "NSE_EQ|INE000000000"

    def get_company_profile(self, isin):
        self.calls.append(("get_company_profile", isin))
        return {"isin": isin, "name": "Fake Corp", "sector": "Technology"}

    def get_share_holdings(self, isin):
        self.calls.append(("get_share_holdings", isin))
        return [{"category": "Promoters", "shares": 1000000}]

    def get_key_ratios(self, isin):
        self.calls.append(("get_key_ratios", isin))
        return [{"ratio": "pe", "value": 20.0}]

    def get_corporate_actions(self, isin):
        self.calls.append(("get_corporate_actions", isin))
        return [{"type": "DIVIDEND", "exDate": "2025-02-14", "amount": 5.0}]

    def get_competitors(self, isin, exchange="NSE"):
        self.calls.append(("get_competitors", isin, exchange))
        return [{"name": "Peer Corp", "instrument_key": f"{exchange}_EQ|INE000000001"}]

    def get_news(self, instrument_keys):
        self.calls.append(("get_news", instrument_keys))
        return {"articles": [{"headline": "test news", "instrument_key": instrument_keys[0]}]}

    def get_option_greeks(self, instrument_keys):
        self.calls.append(("get_option_greeks", instrument_keys))
        return {
            k: {"iv": 20.0, "delta": 0.5, "gamma": 0.01, "theta": -0.1, "vega": 0.2}
            for k in instrument_keys
        }


@pytest.fixture
def stub(monkeypatch) -> StubClient:
    client = StubClient(make_option_chain(), _futures_chain())
    monkeypatch.setattr(market_data, "_client", client)
    monkeypatch.setattr(options, "_client", client)
    monkeypatch.setattr(fundamentals, "_client", client)
    return client


# --- invocation table for all 42 tools --------------------------------------
_TOOL_CALLS: dict[str, tuple[tuple, dict]] = {
    # market_data (19)
    "get_option_chain": (("NIFTY",), {}),
    "get_expiry_dates": (("NIFTY",), {}),
    "get_spot_price": (("NIFTY",), {}),
    "get_full_quote": (("NIFTY",), {}),
    "get_full_quotes": ((["NIFTY", "BANKNIFTY"],), {}),
    "get_historical_data": (("NIFTY",), {}),
    "get_futures_chain": (("NIFTY",), {}),
    "get_market_depth": (("NIFTY",), {}),
    "get_margin": (([{"instrument_key": "k", "quantity": 50,
                      "transaction_type": "BUY", "product": "I"}],), {}),
    "get_pcr": (("NIFTY", "2025-01-30", "2025-01-24"), {}),
    "get_max_pain": (("NIFTY", "2025-01-30", "2025-01-24"), {}),
    "get_oi": (("NIFTY", "2025-01-30", "2025-01-24"), {}),
    "get_change_oi": (("NIFTY", "2025-01-30", "2025-01-24"), {}),
    "get_fii": ((), {}),
    "get_dii": ((), {}),
    "get_market_status": ((), {}),
    "get_market_holidays": ((), {}),
    "get_market_timings": (("2025-01-24",), {}),
    "get_instruments": (("NIFTY",), {}),
    # options (16)
    "compute_pcr": (("NIFTY",), {}),
    "compute_max_pain": (("NIFTY",), {}),
    "compute_top_oi_strikes": (("NIFTY",), {}),
    "compute_atm": (("NIFTY",), {}),
    "compute_iv_skew": (("NIFTY",), {}),
    "compute_oi_buildup": (("NIFTY",), {}),
    "compute_support_resistance": (("NIFTY",), {}),
    "compute_straddle": (("NIFTY",), {}),
    "compute_gex": (("NIFTY",), {}),
    "compute_futures_basis": (("NIFTY",), {}),
    "price_long_straddle": (("NIFTY",), {}),
    "price_long_strangle": (("NIFTY",), {"call_strike": 20500.0, "put_strike": 19500.0}),
    "price_bull_call_spread": (("NIFTY",), {"lower_strike": 20000.0, "higher_strike": 20500.0}),
    "price_bear_put_spread": (("NIFTY",), {"higher_strike": 20000.0, "lower_strike": 19500.0}),
    "price_iron_condor": (("NIFTY",), {"put_sell_strike": 19900.0, "put_buy_strike": 19800.0,
                                       "call_buy_strike": 20100.0, "call_sell_strike": 20200.0}),
    "price_long_butterfly": (("NIFTY",), {"lower_strike": 19900.0, "middle_strike": 20000.0,
                                          "upper_strike": 20100.0}),
    # fundamentals / news / greeks (7)
    "get_company_profile": (("RELIANCE",), {}),
    "get_share_holdings": (("RELIANCE",), {}),
    "get_key_ratios": (("RELIANCE",), {}),
    "get_corporate_actions": (("RELIANCE",), {}),
    "get_competitors": (("RELIANCE",), {}),
    "get_news": (("RELIANCE",), {}),
    "get_option_greeks": (("NIFTY",), {}),
}

# The one key every options tool is guaranteed to return.
_OPTIONS_SIGNATURE_KEYS = {
    "compute_pcr": "pcr",
    "compute_max_pain": "maxPain",
    "compute_top_oi_strikes": "topCallOi",
    "compute_atm": "atmStrike",
    "compute_iv_skew": "skew",
    "compute_oi_buildup": "buildupCounts",
    "compute_support_resistance": "support",
    "compute_straddle": "straddleCost",
    "compute_gex": "netGex",
    "compute_futures_basis": "contracts",
    "price_long_straddle": "maxLoss",
    "price_long_strangle": "maxLoss",
    "price_bull_call_spread": "maxLoss",
    "price_bear_put_spread": "maxLoss",
    "price_iron_condor": "maxLoss",
    "price_long_butterfly": "maxLoss",
}


def _invoke(tool) -> str:
    args, kwargs = _TOOL_CALLS[tool.__name__]
    return asyncio.run(tool(*args, **kwargs))


ALL_TOOLS = market_data.TOOLS + options.TOOLS + fundamentals.TOOLS


class TestToolLists:
    def test_tool_split_is_19_and_16_and_7(self):
        assert len(market_data.TOOLS) == 19
        assert len(options.TOOLS) == 16
        assert len(fundamentals.TOOLS) == 7
        assert len(ALL_TOOLS) == 42

    def test_every_tool_has_an_invocation_entry(self):
        missing = [f.__name__ for f in ALL_TOOLS if f.__name__ not in _TOOL_CALLS]
        assert missing == []


@pytest.mark.parametrize("tool", sorted(ALL_TOOLS, key=lambda f: f.__name__))
class TestEveryToolContract:
    def test_returns_parseable_json(self, stub, tool):
        parsed = json.loads(_invoke(tool))
        assert isinstance(parsed, (dict, list))


@pytest.mark.parametrize("tool", sorted(options.TOOLS, key=lambda f: f.__name__))
class TestOptionsToolContract:
    def test_returns_its_signature_key(self, stub, tool):
        assert _OPTIONS_SIGNATURE_KEYS[tool.__name__] in json.loads(_invoke(tool))

    def test_fetches_the_chain_via_the_client(self, stub, tool):
        _invoke(tool)
        assert stub.calls.count(("get_option_chain", "NIFTY", None)) >= 1


@pytest.mark.parametrize("tool", sorted(fundamentals.TOOLS, key=lambda f: f.__name__))
class TestFundamentalsToolContract:
    def test_returns_parseable_json(self, stub, tool):
        parsed = json.loads(_invoke(tool))
        assert isinstance(parsed, (dict, list))

    def test_equity_tools_resolve_symbol_via_the_client(self, stub, tool):
        _invoke(tool)
        if tool is fundamentals.get_option_greeks:
            # greeks reads instrument keys off the chain; no ISIN resolution
            assert ("get_option_chain", "NIFTY", None) in stub.calls
            assert any(c[0] == "get_option_greeks" for c in stub.calls)
        else:
            assert stub.calls.count(("resolve_key", "RELIANCE")) >= 1


# --- market_data output shapes ----------------------------------------------
class TestMarketDataShapes:
    def test_spot_price_wraps_with_symbol(self, stub):
        assert json.loads(_invoke(market_data.get_spot_price)) == {
            "symbol": "NIFTY", "last_price": 20000.0,
        }

    def test_full_quote_merges_symbol(self, stub):
        out = json.loads(_invoke(market_data.get_full_quote))
        assert out["symbol"] == "NIFTY"
        assert out["last_price"] == 20000.0
        assert out["p_change"] == 0.05

    def test_full_quotes_returns_every_symbol(self, stub):
        out = json.loads(_invoke(market_data.get_full_quotes))
        assert set(out) == {"NIFTY", "BANKNIFTY"}

    def test_margin_returns_requirement(self, stub):
        out = json.loads(_invoke(market_data.get_margin))
        assert out["requiredMargin"] == 50000.0

    def test_expiry_dates_are_a_list(self, stub):
        assert json.loads(_invoke(market_data.get_expiry_dates)) == [
            "2025-01-30", "2025-02-27",
        ]


# --- argument forwarding ----------------------------------------------------
class TestArgumentForwarding:
    def test_option_chain_forwards_symbol_and_expiry(self, stub):
        _invoke(market_data.get_option_chain)
        assert ("get_option_chain", "NIFTY", None) in stub.calls

    def test_history_forwards_default_interval_and_days(self, stub):
        _invoke(market_data.get_historical_data)
        assert ("get_historical_data", "NIFTY", "day", 60) in stub.calls

    def test_defaults_reach_the_client(self, stub):
        _invoke(market_data.get_market_status)
        assert ("get_market_status", "NSE") in stub.calls
        _invoke(market_data.get_fii)
        assert ("get_fii", "NSE_FO|INDEX_FUTURES", "1D") in stub.calls
        _invoke(market_data.get_dii)
        assert ("get_dii", "NSE_EQ|CASH", "1D") in stub.calls

    def test_futures_basis_fetches_both_chain_and_futures(self, stub):
        _invoke(options.compute_futures_basis)
        assert ("get_option_chain", "NIFTY", None) in stub.calls
        assert ("get_futures_chain", "NIFTY", None) in stub.calls


# --- computed values (smoke: full math is covered by test_analytics) --------
class TestComputedValues:
    def test_compute_pcr_balanced_chain(self, stub):
        assert json.loads(_invoke(options.compute_pcr))["pcr"] == 1.0

    def test_compute_atm(self, stub):
        assert json.loads(_invoke(options.compute_atm))["atmStrike"] == 20000.0

    def test_compute_futures_basis_basis_of_100(self, stub):
        out = json.loads(_invoke(options.compute_futures_basis))
        assert out["spot"] == 20000.0
        assert out["contracts"][0]["basis"] == 100.0  # 20100 - 20000

    def test_long_straddle_is_a_net_debit_of_200(self, stub):
        out = json.loads(_invoke(options.price_long_straddle))
        assert out["netDebit"] == -200.0
        assert out["maxLoss"] == -200.0
        assert out["breakevens"] == [19800.0, 20200.0]

    def test_oi_buildup_counts_all_legs(self, stub):
        out = json.loads(_invoke(options.compute_oi_buildup))
        assert out["totalLegs"] == 22  # 11 strikes x CE + PE
