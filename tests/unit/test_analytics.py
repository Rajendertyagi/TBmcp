"""Unit tests for the pure analytics functions in :mod:`analytics`.

No network, no broker credentials — every test feeds a synthetic
``OptionChain``/``FuturesChain`` built in ``conftest.py`` and asserts the
mathematically expected result.
"""
from __future__ import annotations

import pytest

from analytics import (
    compute_atm,
    compute_futures_basis,
    compute_gex,
    compute_iv_skew,
    compute_max_pain,
    compute_oi_buildup,
    compute_pcr,
    compute_straddle,
    compute_support_resistance,
    compute_top_oi_strikes,
)

from tests.unit.conftest import make_option_chain


# --- compute_pcr ------------------------------------------------------------
class TestComputePcr:
    def test_balanced(self, chain):
        out = compute_pcr(chain)  # 1000 / 1000
        assert out["pcr"] == 1.0
        assert out["totalCallOi"] == 1000
        assert out["totalPutOi"] == 1000
        assert out["interpretation"] == "Balanced sentiment"

    def test_put_heavy_boundary(self):
        chain = make_option_chain(totalCEOpenInterest=1000, totalPEOpenInterest=1200)
        out = compute_pcr(chain)
        assert out["pcr"] == 1.2
        assert "Put-heavy" in out["interpretation"]

    def test_call_heavy_boundary(self):
        chain = make_option_chain(totalCEOpenInterest=1000, totalPEOpenInterest=800)
        out = compute_pcr(chain)
        assert out["pcr"] == 0.8
        assert "Call-heavy" in out["interpretation"]

    def test_zero_call_oi_does_not_divide_by_zero(self):
        chain = make_option_chain(totalCEOpenInterest=0, totalPEOpenInterest=500)
        out = compute_pcr(chain)
        assert out["pcr"] == 0.0
        assert "Call-heavy" in out["interpretation"]

    def test_missing_totals(self):
        out = compute_pcr({})
        assert out["pcr"] == 0.0


# --- compute_max_pain -------------------------------------------------------
class TestComputeMaxPain:
    def test_finds_first_minimum_loss_strike(self):
        # CE OI only at 19600; PE OI at 20200 and 20400. Loss is minimised at
        # 20200 (the first strike reaching the 8000 minimum).
        chain = make_option_chain(
            ce_oi={19600: 10},
            pe_oi={20200: 90, 20400: 10},
        )
        out = compute_max_pain(chain)
        assert out["maxPain"] == 20200.0
        assert out["underlyingValue"] == 20000.0

    def test_empty_strikes_returns_zero(self):
        chain = make_option_chain(strikes=[])
        out = compute_max_pain(chain)
        assert out["maxPain"] == 0.0

    def test_empty_chain_no_crash(self):
        out = compute_max_pain({"strikePrices": [100.0, 200.0], "rows": []})
        assert isinstance(out["maxPain"], float)


# --- compute_top_oi_strikes -------------------------------------------------
class TestComputeTopOiStrikes:
    def test_orders_by_oi_and_respects_n(self, chain):
        for row in chain["rows"]:
            row["CE"]["openInterest"] = {19800: 1500, 20000: 900, 19600: 500}.get(row["strikePrice"], 10)
            row["PE"]["openInterest"] = {19600: 2000, 20400: 300}.get(row["strikePrice"], 10)
        out = compute_top_oi_strikes(chain, n=2)
        assert out["topCallOi"] == [
            {"strike": 19800.0, "oi": 1500},
            {"strike": 20000.0, "oi": 900},
        ]
        assert out["topPutOi"] == [
            {"strike": 19600.0, "oi": 2000},
            {"strike": 20400.0, "oi": 300},
        ]

    def test_missing_side_is_ignored(self):
        chain = make_option_chain()
        for row in chain["rows"]:
            row["CE"] = None  # no calls at all
        out = compute_top_oi_strikes(chain)
        assert out["topCallOi"] == []
        assert out["topPutOi"]  # puts still present


# --- compute_atm ------------------------------------------------------------
class TestComputeAtm:
    def test_exact_hit(self, chain):
        assert compute_atm(chain)["atmStrike"] == 20000.0

    def test_nearest_wins(self):
        chain = make_option_chain(underlying=20050.0)
        assert compute_atm(chain)["atmStrike"] == 20000.0  # first of the tie

    def test_no_strikes(self):
        assert compute_atm(make_option_chain(strikes=[]))["atmStrike"] == 0.0


# --- compute_iv_skew --------------------------------------------------------
class TestComputeIvSkew:
    def test_otm_ivs_only(self, chain):
        for row in chain["rows"]:
            s = row["strikePrice"]
            row["CE"]["impliedVolatility"] = {20100: 15.0, 20200: 18.0}.get(s)
            row["PE"]["impliedVolatility"] = {19800: 20.0, 19900: 22.0}.get(s)
        out = compute_iv_skew(chain)
        assert out["otmCallAvgIv"] == 16.5   # (15 + 18) / 2
        assert out["otmPutAvgIv"] == 21.0    # (20 + 22) / 2
        assert out["skew"] == 4.5

    def test_no_ivs_returns_zeros(self):
        chain = make_option_chain()
        for row in chain["rows"]:
            row["CE"]["impliedVolatility"] = None
            row["PE"]["impliedVolatility"] = None
        out = compute_iv_skew(chain)
        assert out == {"otmCallAvgIv": 0.0, "otmPutAvgIv": 0.0, "skew": 0.0}


# --- compute_oi_buildup -----------------------------------------------------
class TestComputeOiBuildup:
    def test_counts_tags_and_total_legs(self, chain):
        for row in chain["rows"]:
            s = row["strikePrice"]
            row["CE"]["buildTag"] = "Long Buildup" if s == 19800 else "Neutral"
            row["PE"]["buildTag"] = {
                19900: "Long Unwinding",
                20100: "Short Covering",
                20200: "Short Buildup",
            }.get(s, "Neutral")
        out = compute_oi_buildup(chain)
        assert out["totalLegs"] == 22  # 11 strikes x (CE + PE)
        assert out["buildupCounts"]["Long Buildup"] == 1
        assert out["buildupCounts"]["Short Buildup"] == 1
        assert out["buildupCounts"]["Long Unwinding"] == 1
        assert out["buildupCounts"]["Short Covering"] == 1
        assert out["buildupCounts"]["Neutral"] == 18

    def test_missing_build_tag_defaults_to_neutral(self, chain):
        for row in chain["rows"]:
            row["CE"].pop("buildTag", None)
        out = compute_oi_buildup(chain)
        assert out["buildupCounts"]["Neutral"] == out["totalLegs"]


# --- compute_support_resistance --------------------------------------------
class TestComputeSupportResistance:
    def test_max_put_oi_is_support_max_call_oi_is_resistance(self, chain):
        for row in chain["rows"]:
            s = row["strikePrice"]
            row["PE"]["openInterest"] = 5000 if s == 19900 else 100
            row["CE"]["openInterest"] = 6000 if s == 20100 else 100
        out = compute_support_resistance(chain)
        assert out["support"] == 19900.0
        assert out["supportOi"] == 5000
        assert out["resistance"] == 20100.0
        assert out["resistanceOi"] == 6000

    def test_empty_rows(self):
        out = compute_support_resistance({"rows": []})
        assert out == {"support": 0.0, "supportOi": 0, "resistance": 0.0, "resistanceOi": 0}


# --- compute_straddle -------------------------------------------------------
class TestComputeStraddle:
    def test_cost_and_breakevens(self, chain):
        for row in chain["rows"]:
            if row["strikePrice"] == 20000.0:
                row["CE"]["lastPrice"] = 90.0
                row["PE"]["lastPrice"] = 80.0
        out = compute_straddle(chain)
        assert out["atmStrike"] == 20000.0
        assert out["straddleCost"] == 170.0
        assert out["upperBreakeven"] == 20170.0
        assert out["lowerBreakeven"] == 19830.0

    def test_missing_pe_at_atm_returns_zeros(self, chain):
        for row in chain["rows"]:
            if row["strikePrice"] == 20000.0:
                row["PE"] = None
        out = compute_straddle(chain)
        assert out["straddleCost"] == 0.0
        assert out["upperBreakeven"] == 0.0


# --- compute_gex ------------------------------------------------------------
class TestComputeGex:
    def test_net_gamma_exposure(self, chain):
        for row in chain["rows"]:
            row["CE"]["gamma"] = 0.01
            row["PE"]["gamma"] = 0.02
            row["CE"]["openInterest"] = 1000
            row["PE"]["openInterest"] = 1000
        out = compute_gex(chain)
        # 11 CE legs: 0.01 * 1000 * 11 = 110 ; 11 PE legs: 0.02 * 1000 * 11 = 220
        assert out["callGammaExposure"] == 110.0
        assert out["putGammaExposure"] == 220.0
        assert out["netGex"] == -110.0
        assert "negative" in out["interpretation"]

    def test_zero_net_is_negative_interp(self):
        chain = make_option_chain()
        for row in chain["rows"]:
            row["CE"]["gamma"] = None
            row["PE"]["gamma"] = None
        out = compute_gex(chain)
        assert out["netGex"] == 0.0
        assert "negative" in out["interpretation"]


# --- compute_futures_basis --------------------------------------------------
class TestComputeFuturesBasis:
    def test_basis_premium_and_discount(self):
        fchain = {
            "symbol": "NIFTY",
            "underlyingValue": 20000.0,
            "expiryDates": ["2025-01-30", "2025-02-27"],
            "legs": [
                {"expiryDate": "2025-01-30", "lastPrice": 20200.0},
                {"expiryDate": "2025-02-27", "lastPrice": 19900.0},
            ],
            "timestamp": "2025-01-24T10:00:00+05:30",
        }
        out = compute_futures_basis(fchain, spot=20000.0)
        assert out["spot"] == 20000.0
        c1, c2 = out["contracts"]
        assert c1["basis"] == 200.0 and c1["basisPct"] == 1.0     # premium
        assert c2["basis"] == -100.0 and c2["basisPct"] == -0.5   # discount

    def test_empty_legs(self):
        out = compute_futures_basis({"legs": []}, spot=100.0)
        assert out["contracts"] == []
        assert out["spot"] == 100.0

    def test_zero_spot_no_division_error(self):
        fchain = {"legs": [{"expiryDate": "d", "lastPrice": 100.0}]}
        out = compute_futures_basis(fchain, spot=0.0)
        assert out["contracts"][0]["basisPct"] == 0.0


# --- robustness: every compute_* survives a hollow chain --------------------
@pytest.mark.parametrize("fn", [
    compute_pcr, compute_max_pain, compute_top_oi_strikes, compute_atm,
    compute_iv_skew, compute_oi_buildup, compute_support_resistance,
    compute_straddle, compute_gex,
])
def test_all_analytics_survive_hollow_chain(fn):
    """None of the analytics may raise on a chain with no rows/strikes."""
    result = fn({"symbol": "NIFTY", "strikePrices": [], "rows": [],
                 "totalCEOpenInterest": 0, "totalPEOpenInterest": 0,
                 "underlyingValue": 0.0})
    assert isinstance(result, dict)
