"""Unit tests for the strategy pricer (:func:`analytics.price_strategy`).

These assert the *correct* expiry payoff math: max profit/loss and breakevens
for long strategies (straddle, strangle) and short-leg strategies (spreads,
condor, butterfly). They double as the regression test for the signed-quantity
bug in ``_payoff_at`` (a sold leg must subtract, not add, its payoff).
"""
from __future__ import annotations

from analytics import price_strategy
from analytics.options import _payoff_at

from tests.unit.conftest import make_option_chain


def _set_premium(chain, strike: float, otype: str, price: float) -> None:
    """Set the lastPrice (premium) of one leg in the synthetic chain."""
    for row in chain["rows"]:
        if row["strikePrice"] == strike:
            row[otype]["lastPrice"] = price
            return
    raise AssertionError(f"no {otype} row at strike {strike}")


# --- direct payoff math (regression for the signed-qty bug) -----------------
class TestPayoffAt:
    def test_sold_leg_subtracts_payoff(self):
        # Bull call spread: buy 20000 CE @100, sell 20100 CE @80.
        legs = [
            {"strike": 20000.0, "type": "CE", "qty": 1, "signedQty": 1, "price": 100.0},
            {"strike": 20100.0, "type": "CE", "qty": 1, "signedQty": -1, "price": 80.0},
        ]
        assert _payoff_at(legs, 19000.0) == -20.0   # max loss = net debit
        assert _payoff_at(legs, 20050.0) == 30.0
        assert _payoff_at(legs, 20100.0) == 80.0    # capped at max profit
        assert _payoff_at(legs, 21000.0) == 80.0

    def test_plain_signed_qty_contract_still_works(self):
        # Documented contract: qty itself is signed when no signedQty key.
        legs = [
            {"strike": 20000.0, "type": "CE", "qty": -1, "price": 100.0},
        ]
        assert _payoff_at(legs, 19000.0) == 100.0   # short CE gains the premium
        assert _payoff_at(legs, 20500.0) == -400.0  # ...and loses intrinsic


# --- long straddle ----------------------------------------------------------
class TestLongStraddle:
    def test_net_debit_max_loss_and_breakevens(self, chain):
        out = price_strategy("long_straddle", chain, [
            {"strike": 20000, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": 20000, "type": "PE", "qty": 1, "side": "BUY"},
        ])
        assert out["netDebit"] == -200.0          # paid 100 + 100
        assert out["maxLoss"] == -200.0           # both expire worthless
        assert out["maxProfit"] == 9800.0         # 1 lot captured at the wings
        assert out["breakevens"] == [19800.0, 20200.0]


# --- long strangle ----------------------------------------------------------
class TestLongStrangle:
    def test_breakevens_flank_the_wing_strikes(self, chain):
        out = price_strategy("long_strangle", chain, [
            {"strike": 20100, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": 19900, "type": "PE", "qty": 1, "side": "BUY"},
        ])
        assert out["netDebit"] == -200.0
        assert out["maxLoss"] == -200.0
        assert len(out["breakevens"]) == 2
        assert any(abs(be - 19700) < 60 for be in out["breakevens"])
        assert any(abs(be - 20300) < 60 for be in out["breakevens"])


# --- bull call spread (short leg) -------------------------------------------
class TestBullCallSpread:
    def test_limited_risk_reward(self, chain):
        _set_premium(chain, 20100, "CE", 80.0)
        out = price_strategy("bull_call_spread", chain, [
            {"strike": 20000, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": 20100, "type": "CE", "qty": 1, "side": "SELL"},
        ])
        assert out["netDebit"] == -20.0           # paid 100, collected 80
        assert out["maxLoss"] == -20.0            # spread can't lose more than debit
        assert out["maxProfit"] == 80.0           # width (100) minus debit (20)
        assert len(out["breakevens"]) == 1
        assert 20000.0 <= out["breakevens"][0] <= 20100.0


# --- bear put spread (short leg) --------------------------------------------
class TestBearPutSpread:
    def test_limited_risk_reward(self, chain):
        _set_premium(chain, 20000, "PE", 80.0)
        out = price_strategy("bear_put_spread", chain, [
            {"strike": 20100, "type": "PE", "qty": 1, "side": "BUY"},
            {"strike": 20000, "type": "PE", "qty": 1, "side": "SELL"},
        ])
        assert out["netDebit"] == -20.0
        assert out["maxLoss"] == -20.0
        assert out["maxProfit"] == 80.0
        assert len(out["breakevens"]) == 1


# --- iron condor + butterfly (sanity: mixed long/short wings) ---------------
class TestMultiLegSanity:
    def test_iron_condor(self, chain):
        out = price_strategy("iron_condor", chain, [
            {"strike": 19900, "type": "PE", "qty": 1, "side": "SELL"},
            {"strike": 19800, "type": "PE", "qty": 1, "side": "BUY"},
            {"strike": 20100, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": 20200, "type": "CE", "qty": 1, "side": "SELL"},
        ])
        # All premiums equal (100) -> zero net credit, bounded wings.
        assert out["netDebit"] == 0.0
        assert out["maxLoss"] <= 0.0
        assert out["maxProfit"] >= 0.0
        assert len(out["legs"]) == 4

    def test_long_butterfly(self, chain):
        legs = [
            {"strike": 19900, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": 20000, "type": "CE", "qty": 2, "side": "SELL"},
            {"strike": 20100, "type": "CE", "qty": 1, "side": "BUY"},
        ]
        # Analytic peak is exactly 100.0 at the body strike (20000)...
        assert _payoff_at([
            {"strike": 19900, "type": "CE", "qty": 1, "signedQty": 1, "price": 100.0},
            {"strike": 20000, "type": "CE", "qty": 2, "signedQty": -2, "price": 100.0},
            {"strike": 20100, "type": "CE", "qty": 1, "signedQty": 1, "price": 100.0},
        ], 20000.0) == 100.0
        out = price_strategy("long_butterfly", chain, legs)
        assert out["netDebit"] == 0.0
        assert out["maxLoss"] == 0.0              # net zero outside the wings
        # ...and the coarse 101-point sampler never overstates it.
        assert 0.0 < out["maxProfit"] <= 100.0


# --- leg resolution & side/type parsing -------------------------------------
class TestLegResolution:
    def test_nearest_strike_price_is_used(self, chain):
        # 20050 is not a chain strike; nearest is 20000 (tie -> first hit).
        out = price_strategy("custom", chain, [
            {"strike": 20050, "type": "CE", "qty": 1, "side": "BUY"},
        ])
        assert out["legs"][0]["strike"] == 20050.0  # requested strike kept
        assert out["legs"][0]["price"] == 100.0     # premium from 20000 row

    def test_side_and_type_case_insensitive(self, chain):
        out = price_strategy("custom", chain, [
            {"strike": 20000, "type": "c", "qty": 1, "side": "sell"},
        ])
        leg = out["legs"][0]
        assert leg["type"] == "CE"
        assert leg["side"] == "SELL"
        assert leg["signedQty"] == -1.0

    def test_missing_strike_prices_zero(self):
        out = price_strategy("custom", make_option_chain(strikes=[]), [
            {"strike": 20000, "type": "CE", "qty": 1, "side": "BUY"},
        ])
        assert out["legs"][0]["price"] == 0.0
        assert out["netDebit"] == 0.0
