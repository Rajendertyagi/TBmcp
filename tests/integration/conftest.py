"""Shared fixtures for integration tests — a deterministic in-memory
``DataProvider`` stand-in plus a Falcon test client bound to it.

No network, no credentials: the web/MCP layers are exercised against the
``DataProvider`` protocol boundary exactly as they would be against Upstox.
"""
from __future__ import annotations

import pytest

from tests.unit.conftest import make_option_chain


class FakeProvider:
    """A ``DataProvider``-shaped stub with canned, deterministic data.

    ``fail`` raises a RuntimeError from every data method (used to prove the
    boundary turns upstream errors into JSON error responses). ``empty_expiries``
    makes ``get_expiry_dates`` return ``[]`` (used to prove the batch runner
    marks expiry-dependent tools as skipped rather than crashing).
    """

    def __init__(self, fail: bool = False, empty_expiries: bool = False) -> None:
        self.fail = fail
        self.empty_expiries = empty_expiries
        self._chain = make_option_chain()

    def _maybe_raise(self) -> None:
        if self.fail:
            raise RuntimeError("upstream failure (test)")

    # --- raw market data -----------------------------------------------------
    def get_option_chain(self, symbol: str, expiry_date=None):
        self._maybe_raise()
        return self._chain

    def get_expiry_dates(self, symbol: str) -> list[str]:
        self._maybe_raise()
        return [] if self.empty_expiries else ["2025-01-30", "2025-02-27"]

    def get_spot_price(self, symbol: str) -> float:
        self._maybe_raise()
        return 20000.0

    def get_full_quote(self, symbol: str) -> dict:
        self._maybe_raise()
        return {"last_price": 20000.0, "net_change": 10.0, "p_change": 0.05}

    def get_full_quotes(self, symbols: list[str]) -> dict:
        self._maybe_raise()
        return {s: {"last_price": 20000.0, "net_change": 0.0, "p_change": 0.0} for s in symbols}

    def get_historical_data(self, symbol: str, interval: str = "day", days: int = 60) -> list:
        self._maybe_raise()
        return [
            {"time": 1700000000 + i * 86400, "open": 100.0, "high": 110.0,
             "low": 90.0, "close": 105.0, "volume": 1000.0}
            for i in range(5)
        ]

    def get_futures_chain(self, symbol: str, expiry_date=None) -> dict:
        self._maybe_raise()
        return {
            "symbol": symbol,
            "underlyingValue": 20000.0,
            "expiryDates": ["2025-01-30", "2025-02-27"],
            "legs": [{
                "instrumentKey": "NSE_INDEX|Nifty 50", "expiryDate": "2025-01-30",
                "strikePrice": 0.0, "lastPrice": 20100.0, "change": 0.0,
                "pChange": 0.0, "openInterest": 1000, "volume": 1000, "lotSize": 50,
            }],
            "timestamp": "2025-01-24T10:00:00+05:30",
        }

    def get_market_depth(self, symbol: str) -> dict:
        self._maybe_raise()
        return {"symbol": symbol, "instrumentKey": "k", "lastPrice": 20000.0,
                "totalBuyQuantity": 10, "totalSellQuantity": 20, "buy": [], "sell": [],
                "timestamp": "t"}

    def get_margin(self, instruments: list[dict]) -> dict:
        self._maybe_raise()
        return {"requiredMargin": 50000.0, "finalMargin": 50000.0, "margins": []}

    # --- market-info endpoints ----------------------------------------------
    def get_pcr(self, symbol, expiry, date, bucket_interval=60) -> dict:
        self._maybe_raise()
        return {"pcr": 1.1}

    def get_max_pain(self, symbol, expiry, date, bucket_interval=60) -> dict:
        self._maybe_raise()
        return {"max_pain": 20000.0}

    def get_oi(self, symbol, expiry, date) -> dict:
        self._maybe_raise()
        return {"oi": 1000}

    def get_change_oi(self, symbol, expiry, date, interval=1) -> dict:
        self._maybe_raise()
        return {"change_oi": 50}

    def get_fii(self, data_type="NSE_FO|INDEX_FUTURES", interval="1D") -> dict:
        self._maybe_raise()
        return {"fii": 100}

    def get_dii(self, data_type="NSE_EQ|CASH", interval="1D") -> dict:
        self._maybe_raise()
        return {"dii": 200}

    def get_market_status(self, exchange="NSE") -> dict:
        self._maybe_raise()
        return {"exchange": exchange, "status": "open"}

    def get_market_holidays(self, date=None) -> list:
        self._maybe_raise()
        return [{"date": "2025-01-26", "description": "Republic Day", "trading": False, "clearing": False}]

    def get_market_timings(self, date: str) -> dict:
        self._maybe_raise()
        return {"date": date, "open": "09:15", "close": "15:30"}

    def get_instruments(self, query: str, exchange: str = "NSE") -> list:
        self._maybe_raise()
        return [{"instrument_key": "NSE_INDEX|Nifty 50", "trading_symbol": "Nifty 50",
                 "name": "Nifty 50", "exchange": exchange, "instrument_type": "I",
                 "segment": "NSE_INDEX", "lot_size": 0}]

    # --- auth -----------------------------------------------------------------
    def build_login_url(self, api_key: str, redirect_uri: str, code_challenge=None) -> str:
        return f"https://upstox.test/login?client_id={api_key}&redirect_uri={redirect_uri}"

    def exchange_code_for_token(self, code: str, redirect_uri: str, code_verifier=None) -> str:
        self._maybe_raise()
        return "fake-access-token"


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def api_client(fake_provider, monkeypatch):
    """Falcon test client whose routes resolve to the fake provider."""
    import api.app as app

    monkeypatch.setattr(app, "_client", fake_provider)
    monkeypatch.setattr("services.tools_runner.TEST_ALL_GAP_SECONDS", 0.0)

    from falcon import testing

    return testing.TestClient(app.create_app())
