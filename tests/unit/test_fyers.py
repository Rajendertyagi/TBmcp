"""Unit tests for the FYERS v3 data client (offline, no network)."""
from __future__ import annotations

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
    # FYERS option-chain shape: a spot entry (option_type == "") whose `ltp`
    # is the underlying, plus CE/PE legs with ltp/oi/prev_oi/volume/ltpch/
    # ltpchp/bid/ask/greeks.
    client = FyersClient()
    data = {
        "optionsChain": [
            {"strike_price": -1, "option_type": "", "ltp": 22000.0},
            {"strike_price": 22000, "option_type": "CE", "ltp": 100, "oi": 5000,
             "prev_oi": 4000, "volume": 200, "ltpch": 5, "ltpchp": 0.5,
             "greeks": {"iv": 18.0, "delta": 0.5, "gamma": 0.01, "theta": -1.0, "vega": 2.0},
             "bid": 99, "ask": 101},
            {"strike_price": 22000, "option_type": "PE", "ltp": 80, "oi": 3000,
             "prev_oi": 3500, "volume": 150, "ltpch": -3, "ltpchp": -0.3,
             "greeks": {"iv": 19.0, "delta": -0.5, "gamma": 0.02, "theta": -1.1, "vega": 2.1},
             "bid": 79, "ask": 81},
            {"strike_price": 22100, "option_type": "CE", "ltp": 50, "oi": 1000,
             "prev_oi": 900, "volume": 50, "ltpch": 1, "ltpchp": 0.1,
             "greeks": {"iv": 17.0}, "bid": 49, "ask": 51},
        ],
    }
    rows, underlying, totals = client._parse_chain_rows(data, "2024-03-01")
    assert underlying == 22000.0
    assert len(rows) == 2
    assert rows[0]["strikePrice"] == 22000.0
    assert rows[0]["CE"]["openInterest"] == 5000
    assert rows[0]["PE"]["openInterest"] == 3000
    assert rows[0]["CE"]["lastPrice"] == 100
    assert rows[0]["CE"]["change"] == 5
    assert rows[0]["CE"]["pChange"] == 0.5
    assert rows[0]["CE"]["bidPrice"] == 99
    assert rows[0]["CE"]["askPrice"] == 101
    assert rows[0]["CE"]["delta"] == 0.5
    assert totals["ce_oi"] == 6000
    assert totals["pe_oi"] == 3000
    # buildup tag is computed (long buildup for CE: oi up + price up)
    assert rows[0]["CE"]["buildTag"] in (
        "Long Buildup", "Short Buildup", "Long Unwinding", "Short Covering", "Neutral")


def test_quote_entry_extracts_ltp_change():
    # FYERS /quotes returns {"d":[{"v":{"symbol":..., "lp":..., "ch":..., "chp":...}}]}.
    client = FyersClient()
    raw = {"d": [{"v": {"symbol": "NSE:NIFTY50-INDEX", "lp": 22000, "ch": 50, "chp": 0.2}}]}
    entry = client._quote_entry(raw, "NSE:NIFTY50-INDEX")
    assert entry["last_price"] == 22000
    assert entry["net_change"] == 50
    assert entry["p_change"] == 0.2


def test_get_option_chain_uses_calloi_putoi_totals(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "ensure_initialized", lambda: None)
    monkeypatch.setattr(client, "_request", lambda path, params=None, attempt=1: {
        "s": "ok",
        "data": {
            "optionsChain": [
                {"strike_price": -1, "option_type": "", "ltp": 22000.0},
                {"strike_price": 22000, "option_type": "CE", "ltp": 100, "oi": 5000,
                 "prev_oi": 4000, "volume": 200, "ltpch": 5, "ltpchp": 0.5,
                 "greeks": {"iv": 18.0}, "bid": 99, "ask": 101},
                {"strike_price": 22000, "option_type": "PE", "ltp": 80, "oi": 3000,
                 "prev_oi": 3500, "volume": 150, "ltpch": -3, "ltpchp": -0.3,
                 "greeks": {"iv": 19.0}, "bid": 79, "ask": 81},
            ],
            "callOi": 5000,
            "putOi": 3000,
            "expiryData": [1709251200],
        },
    })
    chain = client.get_option_chain("NIFTY", "2024-03-01")
    assert chain["underlyingValue"] == 22000.0
    assert chain["totalCEOpenInterest"] == 5000
    assert chain["totalPEOpenInterest"] == 3000
    assert len(chain["rows"]) == 1
    assert chain["rows"][0]["CE"]["openInterest"] == 5000


def test_get_option_greeks_parses_d_v_greeks(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "ensure_initialized", lambda: None)
    monkeypatch.setattr(client, "_request", lambda path, params=None, attempt=1: {
        "d": [{"v": {
            "symbol": "NSE:SBIN24DEC650CE",
            "greeks": {"iv": 18.0, "delta": 0.5, "gamma": 0.01, "theta": -1.0, "vega": 2.0},
        }}],
    })
    g = client.get_option_greeks(["NSE:SBIN24DEC650CE"])
    assert g["NSE:SBIN24DEC650CE"]["delta"] == 0.5
    assert g["NSE:SBIN24DEC650CE"]["iv"] == 18.0
    assert g["NSE:SBIN24DEC650CE"]["vega"] == 2.0


def test_get_market_depth_uses_ask_array(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "ensure_initialized", lambda: None)
    monkeypatch.setattr(client, "_request", lambda path, params=None, attempt=1: {
        "d": [{"v": {
            "symbol": "NSE:SBIN-EQ",
            "ask": [{"price": 650.5, "volume": 100, "ord": 5}],
            "bids": [{"price": 650.0, "volume": 200, "ord": 3}],
        }}],
    })
    depth = client.get_market_depth("SBIN")
    assert depth["sell"][0]["price"] == 650.5
    assert depth["buy"][0]["price"] == 650.0


def test_get_historical_data_reads_top_level_candles(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "ensure_initialized", lambda: None)
    monkeypatch.setattr(client, "_request", lambda path, params=None, attempt=1: {
        "candles": [
            [1709251200, 100.0, 101.0, 99.0, 100.5, 1000],
            [1709337600, 100.5, 102.0, 100.0, 101.5, 1100],
        ],
    })
    candles = client.get_historical_data("SBIN", "D", 1)
    assert len(candles) == 2
    assert candles[0]["open"] == 100.0
    assert candles[1]["close"] == 101.5


def test_get_market_status_parses_marketstatus_list(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "ensure_initialized", lambda: None)
    monkeypatch.setattr(client, "_request", lambda path, params=None, attempt=1: {
        "marketStatus": [
            {"exchange": "NSE", "segment": "CM", "market_type": "NSE",
             "status": "Open", "last_updated": "2024-03-01T09:15:00"},
        ],
    })
    result = client.get_market_status("NSE")
    assert result["exchange"] == "NSE"
    assert result["status"] == "Open"
    assert result["lastUpdated"] == "2024-03-01T09:15:00"


def test_unsupported_methods_raise():
    client = FyersClient()
    calls = {
        "get_futures_chain": ("X", None),
        "get_margin": ([],),
        "get_fii": ("X", "1D"),
        "get_dii": ("X", "1D"),
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


def _fake_chain():
    return {
        "symbol": "NIFTY",
        "underlyingValue": 22000.0,
        "expiryDate": "2024-03-01",
        "strikePrices": [21900.0, 22000.0, 22100.0],
        "rows": [
            {"strikePrice": 21900.0,
             "CE": {"strikePrice": 21900.0, "openInterest": 1000, "changeinOpenInterest": 100},
             "PE": {"strikePrice": 21900.0, "openInterest": 2000, "changeinOpenInterest": -50}},
            {"strikePrice": 22000.0,
             "CE": {"strikePrice": 22000.0, "openInterest": 5000, "changeinOpenInterest": 300},
             "PE": {"strikePrice": 22000.0, "openInterest": 3000, "changeinOpenInterest": -200}},
            {"strikePrice": 22100.0,
             "CE": {"strikePrice": 22100.0, "openInterest": 1500, "changeinOpenInterest": 50},
             "PE": {"strikePrice": 22100.0, "openInterest": 2500, "changeinOpenInterest": -100}},
        ],
        "totalCEOpenInterest": 7500,
        "totalPEOpenInterest": 7500,
    }


def test_get_pcr_computes_from_chain(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "get_option_chain", lambda s, e=None: _fake_chain())
    result = client.get_pcr("NIFTY", "2024-03-01")
    assert result["pcr"] == 1.0
    assert result["totalCallOi"] == 7500
    assert result["totalPutOi"] == 7500


def test_get_max_pain_computes_from_chain(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "get_option_chain", lambda s, e=None: _fake_chain())
    result = client.get_max_pain("NIFTY", "2024-03-01")
    assert result["maxPain"] in (21900.0, 22000.0, 22100.0)
    assert result["underlyingValue"] == 22000.0


def test_get_oi_breakdown_from_chain(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "get_option_chain", lambda s, e=None: _fake_chain())
    result = client.get_oi("NIFTY", "2024-03-01")
    assert result["totalCallOi"] == 7500
    assert result["totalPutOi"] == 7500
    assert len(result["strikes"]) == 3
    assert result["strikes"][1]["ceOi"] == 5000
    assert result["strikes"][1]["peOi"] == 3000
    assert result["strikes"][1]["totalOi"] == 8000


def test_get_change_oi_from_chain(monkeypatch):
    client = FyersClient()
    monkeypatch.setattr(client, "get_option_chain", lambda s, e=None: _fake_chain())
    result = client.get_change_oi("NIFTY", "2024-03-01")
    assert len(result["strikes"]) == 3
    assert result["strikes"][1]["ceChangeOi"] == 300
    assert result["strikes"][1]["peChangeOi"] == -200
    assert result["strikes"][1]["totalChangeOi"] == 100


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
