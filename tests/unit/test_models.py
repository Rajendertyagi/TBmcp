"""Structural sanity for the typed data models in :mod:`models`.

TypedDicts are plain dicts at runtime, so these tests lock in the *shape* the
rest of the app depends on (required keys, value types, the Candle time
int-or-string contract) without a broker.
"""
from __future__ import annotations

from models import (
    Candle,
    FuturesChain,
    FuturesLeg,
    MarketDepth,
    OptionChain,
    OptionChainRow,
    OptionLeg,
)

from tests.unit.conftest import make_option_chain

REQUIRED_OPTION_LEG_KEYS = {
    "strikePrice", "expiryDate", "optionType", "lastPrice", "change", "pChange",
    "openInterest", "changeinOpenInterest", "totalTradedVolume",
    "impliedVolatility", "delta", "gamma", "theta", "vega", "bidQty",
    "bidPrice", "askQty", "askPrice", "underlyingValue", "oiChangePct",
    "buildTag",
}

REQUIRED_OPTION_CHAIN_KEYS = {
    "symbol", "underlyingValue", "expiryDate", "expiryDates", "strikePrices",
    "rows", "timestamp", "totalCEOpenInterest", "totalPEOpenInterest",
    "totalCEVolume", "totalPEVolume",
}


class TestOptionLegShape:
    def test_legs_carry_every_required_key(self, chain):
        ce = chain["rows"][0]["CE"]
        assert set(ce) >= REQUIRED_OPTION_LEG_KEYS

    def test_typed_dicts_accept_extra_keys(self):
        # TypedDict is a compile-time check; at runtime extra keys are allowed.
        leg: OptionLeg = {
            **{k: 0 for k in REQUIRED_OPTION_LEG_KEYS},
            "unexpected": "still fine",
        }
        assert leg["unexpected"] == "still fine"


class TestOptionChainShape:
    def test_factory_output_matches_model(self):
        chain: OptionChain = make_option_chain()
        assert set(chain) >= REQUIRED_OPTION_CHAIN_KEYS
        assert isinstance(chain["strikePrices"], list)
        assert all(isinstance(r["strikePrice"], float) for r in chain["rows"])

    def test_row_can_have_optional_missing_side(self):
        row: OptionChainRow = {"strikePrice": 20000.0}
        assert row.get("CE") is None
        assert row.get("PE") is None


class TestCandleTimeContract:
    def test_intraday_time_is_int(self):
        candle: Candle = {"time": 1700000000, "open": 1.0, "high": 2.0,
                          "low": 0.5, "close": 1.5, "volume": 100}
        assert isinstance(candle["time"], int)

    def test_daily_time_is_string(self):
        candle: Candle = {"time": "2025-01-24", "open": 1.0, "high": 2.0,
                          "low": 0.5, "close": 1.5, "volume": 100}
        assert isinstance(candle["time"], str)


class TestFuturesAndDepthShape:
    def test_futures_chain(self):
        fchain: FuturesChain = {
            "symbol": "NIFTY", "underlyingValue": 20000.0,
            "expiryDates": ["2025-01-30"], "legs": [], "timestamp": "t",
        }
        assert set(fchain) == {"symbol", "underlyingValue", "expiryDates",
                               "legs", "timestamp"}
        leg: FuturesLeg = {"instrumentKey": "NSE_INDEX|Nifty 50", "expiryDate": "d",
                           "strikePrice": 0.0, "lastPrice": 20000.0, "change": 0.0,
                           "pChange": 0.0, "openInterest": 0, "volume": 0, "lotSize": 50}
        fchain["legs"].append(leg)
        assert fchain["legs"][0]["lotSize"] == 50

    def test_market_depth(self):
        depth: MarketDepth = {
            "symbol": "NIFTY", "instrumentKey": "k", "lastPrice": 20000.0,
            "totalBuyQuantity": 10, "totalSellQuantity": 20,
            "buy": [{"quantity": 1, "price": 100.0, "orders": 1}],
            "sell": [], "timestamp": "t",
        }
        assert depth["buy"][0]["quantity"] == 1
