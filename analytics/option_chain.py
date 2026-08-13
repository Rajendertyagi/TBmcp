"""Derived F&O chain analytics — pure functions over the typed data models.

Nothing here touches the network or a broker. Every function takes an
`OptionChain` (or `FuturesChain`) and returns a small typed dict, so the same
analytics work whether the chain came from Upstox, a CSV, or a future provider.
The MCP tools and the dashboard call these after fetching the chain, keeping the
broker layer thin. Strategy pricing lives in :mod:`analytics.strategies`.
"""
from __future__ import annotations

from typing import Optional

from constants import BUILDUP_COLORS, NEUTRAL_BUILDUP
from models import FuturesChain, OptionChain


def _atm_strike(chain: OptionChain) -> float:
    underlying = float(chain.get("underlyingValue", 0) or 0)
    strikes = [float(s) for s in chain.get("strikePrices", [])]
    if not strikes:
        return 0.0
    return min(strikes, key=lambda s: abs(s - underlying))


def compute_pcr(chain: OptionChain) -> dict:
    """Put-Call Ratio from total open interest. >1 = put-heavy (bearish bias)."""
    ce_oi = int(chain.get("totalCEOpenInterest", 0) or 0)
    pe_oi = int(chain.get("totalPEOpenInterest", 0) or 0)
    pcr = (pe_oi / ce_oi) if ce_oi else 0.0
    if pcr >= 1.2:
        interp = "Put-heavy — bearish sentiment / possible oversold"
    elif pcr <= 0.8:
        interp = "Call-heavy — bullish sentiment / possible overbought"
    else:
        interp = "Balanced sentiment"
    return {"pcr": round(pcr, 4), "totalCallOi": ce_oi, "totalPutOi": pe_oi, "interpretation": interp}


def compute_max_pain(chain: OptionChain) -> dict:
    """Strike where total option-writer payout is minimised (max pain theory)."""
    strikes = [float(s) for s in chain.get("strikePrices", [])]
    if not strikes:
        return {"maxPain": 0.0, "underlyingValue": float(chain.get("underlyingValue", 0) or 0)}
    best_strike = strikes[0]
    best_loss = None
    for s in strikes:
        loss = 0.0
        for row in chain.get("rows", []):
            ce = row.get("CE")
            pe = row.get("PE")
            if ce:
                k = float(ce.get("strikePrice", 0) or 0)
                oi = int(ce.get("openInterest", 0) or 0)
                if s > k:
                    loss += (s - k) * oi
            if pe:
                k = float(pe.get("strikePrice", 0) or 0)
                oi = int(pe.get("openInterest", 0) or 0)
                if s < k:
                    loss += (k - s) * oi
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best_strike = s
    return {"maxPain": best_strike, "underlyingValue": float(chain.get("underlyingValue", 0) or 0)}


def compute_top_oi_strikes(chain: OptionChain, n: int = 5) -> dict:
    """Strikes with the highest call OI and highest put OI (key battle levels)."""
    rows = chain.get("rows", [])
    call_rows = sorted(
        [r for r in rows if r.get("CE")], key=lambda r: r["CE"]["openInterest"], reverse=True
    )[:n]
    put_rows = sorted(
        [r for r in rows if r.get("PE")], key=lambda r: r["PE"]["openInterest"], reverse=True
    )[:n]
    return {
        "topCallOi": [
            {"strike": r["strikePrice"], "oi": r["CE"]["openInterest"]} for r in call_rows
        ],
        "topPutOi": [
            {"strike": r["strikePrice"], "oi": r["PE"]["openInterest"]} for r in put_rows
        ],
    }


def compute_atm(chain: OptionChain) -> dict:
    return {"atmStrike": _atm_strike(chain), "underlyingValue": float(chain.get("underlyingValue", 0) or 0)}


def compute_iv_skew(chain: OptionChain) -> dict:
    """IV skew: average OTM put IV minus average OTM call IV (negative = fear)."""
    atm = _atm_strike(chain)
    call_ivs: list[float] = []
    put_ivs: list[float] = []
    for r in chain.get("rows", []):
        if r.get("CE") and float(r["strikePrice"]) > atm:
            iv = r["CE"].get("impliedVolatility")
            if iv:
                call_ivs.append(float(iv))
        if r.get("PE") and float(r["strikePrice"]) < atm:
            iv = r["PE"].get("impliedVolatility")
            if iv:
                put_ivs.append(float(iv))
    avg_call = sum(call_ivs) / len(call_ivs) if call_ivs else 0.0
    avg_put = sum(put_ivs) / len(put_ivs) if put_ivs else 0.0
    return {
        "otmCallAvgIv": round(avg_call, 4),
        "otmPutAvgIv": round(avg_put, 4),
        "skew": round(avg_put - avg_call, 4),
    }


def compute_oi_buildup(chain: OptionChain) -> dict:
    """Count of legs per buildup tag (Long/Short Buildup, Long Unwinding, ...)."""
    counts: dict[str, int] = {}
    total = 0
    for r in chain.get("rows", []):
        for side in ("CE", "PE"):
            leg = r.get(side)
            if leg:
                tag = leg.get("buildTag", "Neutral") or "Neutral"
                counts[tag] = counts.get(tag, 0) + 1
                total += 1
    return {"buildupCounts": counts, "totalLegs": total}


def compute_support_resistance(chain: OptionChain) -> dict:
    """Support = strike with max put OI; resistance = strike with max call OI."""
    max_put: Optional[tuple[float, int]] = None
    max_call: Optional[tuple[float, int]] = None
    for r in chain.get("rows", []):
        if r.get("PE"):
            oi = int(r["PE"]["openInterest"] or 0)
            if max_put is None or oi > max_put[1]:
                max_put = (float(r["strikePrice"]), oi)
        if r.get("CE"):
            oi = int(r["CE"]["openInterest"] or 0)
            if max_call is None or oi > max_call[1]:
                max_call = (float(r["strikePrice"]), oi)
    return {
        "support": max_put[0] if max_put else 0.0,
        "supportOi": max_put[1] if max_put else 0,
        "resistance": max_call[0] if max_call else 0.0,
        "resistanceOi": max_call[1] if max_call else 0,
    }


def compute_straddle(chain: OptionChain) -> dict:
    """ATM straddle cost and its two breakeven levels."""
    atm = _atm_strike(chain)
    row = next((r for r in chain.get("rows", []) if float(r["strikePrice"]) == atm), None)
    if not row or not row.get("CE") or not row.get("PE"):
        return {"atmStrike": atm, "straddleCost": 0.0, "upperBreakeven": 0.0, "lowerBreakeven": 0.0}
    cost = float(row["CE"]["lastPrice"]) + float(row["PE"]["lastPrice"])
    return {
        "atmStrike": atm,
        "straddleCost": round(cost, 2),
        "upperBreakeven": round(atm + cost, 2),
        "lowerBreakeven": round(atm - cost, 2),
    }


def compute_gex(chain: OptionChain) -> dict:
    """Gamma Exposure proxy: net of (gamma * OI) across calls minus puts."""
    call_gex = 0.0
    put_gex = 0.0
    for r in chain.get("rows", []):
        if r.get("CE"):
            g = float(r["CE"].get("gamma") or 0)
            call_gex += g * int(r["CE"].get("openInterest", 0) or 0)
        if r.get("PE"):
            g = float(r["PE"].get("gamma") or 0)
            put_gex += g * int(r["PE"].get("openInterest", 0) or 0)
    net = call_gex - put_gex
    return {
        "callGammaExposure": round(call_gex, 2),
        "putGammaExposure": round(put_gex, 2),
        "netGex": round(net, 2),
        "interpretation": "positive (dealers long gamma, stabilising)" if net > 0
        else "negative (dealers short gamma, amplifying)",
    }


def compute_futures_basis(futures_chain: FuturesChain, spot: float) -> dict:
    """Futures premium/discount vs spot for each expiry (carry / cost-of-carry)."""
    contracts = []
    for l in futures_chain.get("legs", []):
        fut = float(l.get("lastPrice", 0) or 0)
        basis = fut - spot
        pct = (basis / spot * 100) if spot else 0.0
        contracts.append({
            "expiry": l.get("expiryDate"),
            "futurePrice": round(fut, 2),
            "spot": round(spot, 2),
            "basis": round(basis, 2),
            "basisPct": round(pct, 4),
        })
    return {"spot": round(spot, 2), "contracts": contracts}


def classify_buildup(oi_change: float, price_change: float) -> str:
    """Classify a single option leg from its OI change and price change.

    OI up   + price up   -> Long Buildup
    OI up   + price down -> Short Buildup
    OI down + price down -> Long Unwinding
    OI down + price up   -> Short Covering
    otherwise            -> Neutral
    """
    oi_up, oi_down = oi_change > 0, oi_change < 0
    price_up, price_down = price_change > 0, price_change < 0
    if oi_up and price_up:
        return "Long Buildup"
    if oi_up and price_down:
        return "Short Buildup"
    if oi_down and price_down:
        return "Long Unwinding"
    if oi_down and price_up:
        return "Short Covering"
    return NEUTRAL_BUILDUP


def buildup_color(build_tag: str) -> str:
    """Return the display colour for a buildup tag (falls back to Neutral)."""
    return BUILDUP_COLORS.get(build_tag, BUILDUP_COLORS[NEUTRAL_BUILDUP])
