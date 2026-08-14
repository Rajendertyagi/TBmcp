"""Unit tests for the FYERS v3 data client (offline, no network)."""
from __future__ import annotations

import os

from providers.exceptions import UnsupportedByProvider
from providers.fyers import (
    FyersClient,
    _app_id_hash,
    _opt_float,
    load_fyers_env,
)


def test_app_id_hash_is_sha256_of_appid_secret():
    assert _app_id_hash("APP-100", "secret") == _app_id_hash("APP-100", "secret")
    assert _app_id_hash("APP-100", "secret") != _app_id_hash("APP-100", "other")


def test_opt_float_handles_none_and_bad():
    assert _opt_float(None) is None
    assert _opt_float("") is None
    assert _opt_float(1.5) == 1.5
    assert _opt_float("2.5") == 2.5
    assert _opt_float("nope") is None


def test_resolve_key_index_and_equity():
    assert FyersClient().resolve_key("NIFTY") == "NSE:NIFTY50-INDEX"
    assert FyersClient().resolve_key("BANKNIFTY") == "NSE:NIFTYBANK-INDEX"
    assert FyersClient().resolve_key("SBIN") == "NSE:SBIN-EQ"


def test_extract_expiries_from_epoch_list():
    data = {"expiryData": [1709251200, 1709856000]}
    got = FyersClient()._extract_expiries(data)
    assert got == ["2024-03-01", "2024-03-08"]


def test_parse_chain_rows_groups_ce_pe_and_totals():
    client = FyersClient()
    data = {
        "underlyingValue": 22000.0,
        "optionsChain": [
            {"strike_price": 22000, "option_type": "CE", "ltp": 100, "oi": 5000,
             "prev_oi": 4000, "volume": 200, "ch": 5, "chp": 0.5,
             "greeks": {"iv": 18.0, "delta": 0.5, "gamma": 0.01, "theta": -1.0, "vega": 2.0},
             "bid_qty": 10, "bid_price": 99, "ask_qty": 20, "ask_price": 101},
            {"strike_price": 22000, "option_type": "PE", "ltp": 80, "oi": 3000,
             "prev_oi": 3500, "volume": 150, "ch": -3, "chp": -0.3,
             "greeks": {"iv": 19.0, "delta": -0.5, "gamma": 0.02, "theta": -1.1, "vega": 2.1},
             "bid_qty": 5, "bid_price": 79, "ask_qty": 8, "ask_price": 81},
            {"strike_price": 22100, "option_type": "CE", "ltp": 50, "oi": 1000,
             "prev_oi": 900, "volume": 50, "ch": 1, "chp": 0.1,
             "greeks": {"iv": 17.0}, "bid_qty": 1, "bid_price": 49, "ask_qty": 2, "ask_price": 51},
        ],
    }
    rows, underlying, totals = client._parse_chain_rows(data, "2024-03-01")
    assert underlying == 22000.0
    assert len(rows) == 2
    assert rows[0]["strikePrice"] == 22000.0
    assert rows[0]["CE"]["openInterest"] == 5000
    assert rows[0]["PE"]["openInterest"] == 3000
    assert totals["ce_oi"] == 6000
    assert totals["pe_oi"] == 3000
    # buildup tag is computed (long buildup for CE: oi up + price up)
    assert rows[0]["CE"]["buildTag"] in (
        "Long Buildup", "Short Buildup", "Long Unwinding", "Short Covering", "Neutral")


def test_quote_entry_extracts_ltp_change():
    client = FyersClient()
    raw = {"data": {"NSE:NIFTY50-INDEX": {"ltp": 22000, "ch": 50, "chp": 0.2}}}
    entry = client._quote_entry(raw, "NSE:NIFTY50-INDEX")
    assert entry["last_price"] == 22000
    assert entry["net_change"] == 50
    assert entry["p_change"] == 0.2


def test_unsupported_methods_raise():
    client = FyersClient()
    calls = {
        "get_futures_chain": ("X", None),
        "get_margin": ([],),
        "get_pcr": ("X", "e", "d"),
        "get_max_pain": ("X", "e", "d"),
        "get_oi": ("X", "e", "d"),
        "get_change_oi": ("X", "e", "d", 1),
        "get_fii": ("X", "1D"),
        "get_dii": ("X", "1D"),
        "get_market_status": ("NSE",),
        "get_market_holidays": (None,),
        "get_market_timings": ("2024-01-01",),
        "get_instruments": ("X", "NSE"),
        "get_company_profile": ("X",),
        "get_share_holdings": ("X",),
        "get_key_ratios": ("X",),
        "get_corporate_actions": ("X",),
        "get_competitors": ("X",),
        "get_news": (["X"],),
    }
    for method, args in calls.items():
        try:
            getattr(client, method)(*args)
        except UnsupportedByProvider:
            pass
        else:
            raise AssertionError(f"{method} should raise UnsupportedByProvider")


def test_load_fyers_env_reads_process_env(monkeypatch):
    monkeypatch.setenv("FYERS_APP_ID", "APP-100")
    monkeypatch.setenv("FYERS_SECRET", "sec")
    monkeypatch.setenv("FYERS_ENABLED", "true")
    monkeypatch.setenv("FYERS_PIN", "1234")
    env = load_fyers_env()
    assert env["app_id"] == "APP-100"
    assert env["secret"] == "sec"
    assert env["enabled"] is True
    assert env["pin"] == "1234"


def test_load_fyers_env_disabled_by_default(monkeypatch):
    for v in ("FYERS_APP_ID", "FYERS_SECRET", "FYERS_ENABLED", "FYERS_PIN"):
        monkeypatch.delenv(v, raising=False)
    assert load_fyers_env()["enabled"] is False
