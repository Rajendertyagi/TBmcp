"""Strategy pricers — pure payoff math over option premiums.

A "leg" is {strike, type: 'CE'|'PE', qty (signed: +buy/-sell), price}.
These compute max profit/loss and breakevens from the option premiums alone
(intrinsic at expiry), which is what the AI needs to compare strategies.
No network, no broker — a pure function over the same `OptionChain` model
as :mod:`analytics.option_chain`.
"""
from __future__ import annotations

from models import OptionChain, OptionChainRow

from .option_chain import _atm_strike


def _payoff_at(legs: list[dict], spot: float) -> float:
    total = 0.0
    for leg in legs:
        k = float(leg["strike"])
        typ = leg["type"]
        # Signed quantity: negative = short. price_strategy stores the signed
        # value under "signedQty" (keeping "qty" as the absolute size); direct
        # callers may put the sign on "qty" itself per the leg contract.
        qty = float(leg.get("signedQty", leg.get("qty", 0)))
        price = float(leg["price"])
        intrinsic = max(spot - k, 0.0) if typ == "CE" else max(k - spot, 0.0)
        # buyer pays price, seller receives; qty negative = short
        total += qty * (intrinsic - price)
    return total


def _breakevens(legs: list[dict]) -> list[float]:
    """Numerically find expiry breakeven spots where net payoff == 0."""
    strikes = sorted({float(l["strike"]) for l in legs})
    if not strikes:
        return []
    lo = min(strikes) * 0.5
    hi = max(strikes) * 1.5
    points = [lo + (hi - lo) * i / 200 for i in range(201)]
    payoffs = [(s, _payoff_at(legs, s)) for s in points]
    bes: list[float] = []
    for i in range(1, len(payoffs)):
        prev_s, prev_p = payoffs[i - 1]
        cur_s, cur_p = payoffs[i]
        if prev_p == 0:
            bes.append(round(prev_s, 2))
        elif prev_p * cur_p < 0:
            bes.append(round((prev_s + cur_s) / 2, 2))
    return bes


def price_strategy(strategy: str, chain: OptionChain, legs_spec: list[dict]) -> dict:
    """Generic pricer. `legs_spec` = list of {strike, type, qty, side:'BUY'/'SELL'}.

    Resolves each leg's premium from the chain (by nearest strike + type), then
    computes net debit/credit, max profit, max loss, and breakevens at expiry.
    """
    atm = _atm_strike(chain)
    rows_by_strike: dict[float, OptionChainRow] = {
        float(r["strikePrice"]): r for r in chain.get("rows", [])
    }

    def _price_for(strike: float, otype: str) -> float:
        # pick the row whose strike is closest to the requested strike
        nearest = min(rows_by_strike, key=lambda s: abs(s - strike)) if rows_by_strike else strike
        row = rows_by_strike.get(nearest)
        if not row:
            return 0.0
        leg = row.get(otype)
        return float(leg["lastPrice"]) if leg else 0.0

    priced_legs: list[dict] = []
    for spec in legs_spec:
        otype = "CE" if str(spec["type"]).upper().startswith("C") else "PE"
        strike = float(spec["strike"])
        side = str(spec.get("side", "BUY")).upper()
        qty = abs(float(spec.get("qty", 1)))
        signed = qty if side == "BUY" else -qty
        price = _price_for(strike, otype)
        priced_legs.append({
            "strike": strike,
            "type": otype,
            "side": side,
            "qty": qty,
            "price": round(price, 2),
        })
        priced_legs[-1]["signedQty"] = signed

    net_debit = sum(-l["signedQty"] * l["price"] for l in priced_legs)

    # sample payoff across a wide spot range to bound max profit / loss
    strikes = [l["strike"] for l in priced_legs]
    lo = min(strikes) * 0.5 if strikes else 0
    hi = max(strikes) * 1.5 if strikes else 0
    samples = [_payoff_at(priced_legs, lo + (hi - lo) * i / 100) for i in range(101)]
    max_p = max(samples)
    max_l = min(samples)
    # For debit spreads the loss is bounded by net debit; keep raw bounds.
    return {
        "strategy": strategy,
        "underlyingValue": float(chain.get("underlyingValue", 0) or 0),
        "atmStrike": atm,
        "netDebit": round(net_debit, 2),
        "maxProfit": round(max_p, 2),
        "maxLoss": round(max_l, 2),
        "breakevens": _breakevens(priced_legs),
        "legs": priced_legs,
    }
