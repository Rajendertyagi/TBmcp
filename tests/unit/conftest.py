"""Shared fixtures for offline unit tests (no network, no credentials)."""
from __future__ import annotations

import pytest


def _leg(strike: float, otype: str, **over: object) -> dict:
    """One OptionLeg-shaped dict with sane defaults, overridable per test."""
    leg: dict = {
        "strikePrice": float(strike),
        "expiryDate": "2025-01-30",
        "optionType": otype,
        "lastPrice": 100.0,
        "change": 1.0,
        "pChange": 0.5,
        "openInterest": 1000,
        "changeinOpenInterest": 50,
        "totalTradedVolume": 500,
        "impliedVolatility": 20.0,
        "delta": 0.5,
        "gamma": 0.01,
        "theta": -0.1,
        "vega": 0.2,
        "bidQty": 100,
        "bidPrice": 99.0,
        "askQty": 100,
        "askPrice": 101.0,
        "underlyingValue": 20000.0,
        "oiChangePct": 1.0,
        "buildTag": "Neutral",
    }
    leg.update(over)
    return leg


def make_option_chain(
    underlying: float = 20000.0,
    strikes: list[float] | None = None,
    ce_oi: dict[float, int] | None = None,
    pe_oi: dict[float, int] | None = None,
    **over: object,
) -> dict:
    """Build a deterministic synthetic ``OptionChain``.

    One row per strike with both a CE and a PE leg. ``ce_oi`` / ``pe_oi``
    override open interest per strike (missing strikes get OI 0 — pass the dict
    when you need precise control, e.g. max-pain); without them every leg gets
    the ``_leg`` default of 1000. Other per-test tweaks (IV, gamma, lastPrice,
    buildTag) are applied by mutating the returned chain in the test itself.
    """
    if strikes is None:
        strikes = [19500.0, 19600.0, 19700.0, 19800.0, 19900.0,
                   20000.0, 20100.0, 20200.0, 20300.0, 20400.0, 20500.0]
    rows = []
    for s in strikes:
        rows.append({
            "strikePrice": s,
            "expiryDate": "2025-01-30",
            "CE": _leg(s, "CE", openInterest=ce_oi.get(s, 0) if ce_oi is not None else 1000),
            "PE": _leg(s, "PE", openInterest=pe_oi.get(s, 0) if pe_oi is not None else 1000),
        })
    chain: dict = {
        "symbol": "NIFTY",
        "underlyingValue": underlying,
        "expiryDate": "2025-01-30",
        "expiryDates": ["2025-01-30", "2025-02-27"],
        "strikePrices": strikes,
        "rows": rows,
        "timestamp": "2025-01-24T10:00:00+05:30",
        "totalCEOpenInterest": 1000,
        "totalPEOpenInterest": 1000,
        "totalCEVolume": 10000,
        "totalPEVolume": 10000,
    }
    chain.update(over)
    return chain


@pytest.fixture
def chain() -> dict:
    """A default synthetic NIFTY option chain (ATM strike 20000)."""
    return make_option_chain()
