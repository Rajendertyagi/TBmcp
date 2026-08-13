"""Production runner for the "Test All" / Market-Info batch tool.

This used to live in ``tests/tool_test.py`` but the WebUI's Tools page
(``api.routes`` :class:`TestAllResource`) also needs it. To keep the
application from depending on the ``tests/`` package at startup, the shared
logic now lives here in a normal production module that both the dashboard
and the test harness import.

Run the whole batch once and get every tool's result back as a single dict:

    from services.tools_runner import run_all_tools
    out = run_all_tools(client, "NIFTY")
"""
from __future__ import annotations

import time
from datetime import date

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
    price_strategy,
)

# Pause inserted between each tool call in the batch so it stays well under
# Upstox rate limits.
TEST_ALL_GAP_SECONDS = 0.3


def run_all_tools(client, symbol: str) -> dict:
    """Run every Market-Info / analytics tool once and return all results.

    Each tool is called defensively: a failure is recorded as
    ``{"ok": False, "error": ...}`` rather than aborting the whole batch. Params
    that need an expiry or a concrete instrument are derived from the symbol
    where possible, otherwise the tool is marked "skipped" with a clear reason.
    """
    sym = str(symbol).strip().upper()
    today = date.today().isoformat()

    results = {}

    def run(name, fn, *args):
        try:
            results[name] = {"ok": True, "data": fn(*args)}
        except Exception as exc:  # noqa: BLE001 - record, don't abort the batch
            results[name] = {"ok": False, "error": str(exc)}
        time.sleep(TEST_ALL_GAP_SECONDS)

    # Derive an expiry for the option-chain-backed tools.
    expiry = None
    try:
        expiries = client.get_expiry_dates(sym)
        if isinstance(expiries, list) and expiries:
            expiry = expiries[0]
        else:
            results["_expiry_lookup"] = {
                "ok": False,
                "error": "get_expiry_dates returned no expiries for " + sym,
            }
    except Exception as exc:
        results["_expiry_lookup"] = {"ok": False, "error": str(exc)}
    time.sleep(TEST_ALL_GAP_SECONDS)

    # Futures chain (also reused to build the margin sample + futures basis).
    fchain = None
    try:
        fchain = client.get_futures_chain(sym)
        results["futures_chain"] = {"ok": True, "data": fchain}
    except Exception as exc:
        results["futures_chain"] = {"ok": False, "error": str(exc)}
    time.sleep(TEST_ALL_GAP_SECONDS)

    # --- Raw market-data tools that need no chain -------------------------
    run("spot_price", client.get_spot_price, sym)
    run("full_quote", client.get_full_quote, sym)
    run("full_quotes", client.get_full_quotes, [sym])
    run("historical_data", client.get_historical_data, sym, "day", 30)
    run("market_depth", client.get_market_depth, sym)
    run("fii", client.get_fii)
    run("dii", client.get_dii)
    run("market_status", client.get_market_status, "NSE")
    run("market_holidays", client.get_market_holidays)
    run("market_timings", client.get_market_timings, today)
    run("instruments", client.get_instruments, sym)

    # --- Fundamentals (equity-only: skip for indices) ----------------------
    key = client.resolve_key(sym)
    if key.startswith("NSE_EQ|") or key.startswith("BSE_EQ|"):
        isin = key.split("|", 1)[1]
        exchange = key.split("|", 1)[0].replace("_EQ", "")  # "NSE" or "BSE"
        run("company_profile", client.get_company_profile, isin)
        run("share_holdings", client.get_share_holdings, isin)
        run("key_ratios", client.get_key_ratios, isin)
        run("corporate_actions", client.get_corporate_actions, isin)
        run("competitors", client.get_competitors, isin, exchange)
        run("news", client.get_news, [key])
    else:
        for _name in ("company_profile", "share_holdings", "key_ratios",
                      "corporate_actions", "competitors", "news"):
            results[_name] = {
                "ok": False,
                "error": "skipped: fundamentals only available for equity stocks",
            }

    # --- Option chain (fetched once, reused by the analytics) -------------
    chain = None
    if expiry:
        try:
            chain = client.get_option_chain(sym, expiry)
            results["option_chain"] = {"ok": True, "data": chain}
        except Exception as exc:
            results["option_chain"] = {"ok": False, "error": str(exc)}
    else:
        results["option_chain"] = {
            "ok": False,
            "error": "skipped: no option expiry resolved for " + sym,
        }
    time.sleep(TEST_ALL_GAP_SECONDS)

    # --- Option Greeks (requires a valid chain) ----------------------------
    if chain:
        try:
            results["option_greeks"] = {
                "ok": True,
                "data": client.get_option_greeks_for_symbol(sym, expiry),
            }
        except Exception as exc:
            results["option_greeks"] = {"ok": False, "error": str(exc)}
    else:
        results["option_greeks"] = {
            "ok": False,
            "error": "skipped: no option chain for " + sym,
        }
    time.sleep(TEST_ALL_GAP_SECONDS)

    # Expiry-dependent raw tools: skip cleanly if we couldn't resolve one.
    if expiry:
        run("pcr", client.get_pcr, sym, expiry, today)
        run("max_pain", client.get_max_pain, sym, expiry, today)
        run("oi", client.get_oi, sym, expiry, today)
        run("change_oi", client.get_change_oi, sym, expiry, today)
    else:
        for name in ("pcr", "max_pain", "oi", "change_oi"):
            results[name] = {
                "ok": False,
                "error": "skipped: no option expiry resolved for " + sym,
            }

    # --- Analytics (compute_*) tools: pure functions over the chain ------
    if chain:
        run("compute_pcr", compute_pcr, chain)
        run("compute_max_pain", compute_max_pain, chain)
        run("compute_top_oi_strikes", compute_top_oi_strikes, chain, 5)
        run("compute_atm", compute_atm, chain)
        run("compute_iv_skew", compute_iv_skew, chain)
        run("compute_oi_buildup", compute_oi_buildup, chain)
        run("compute_support_resistance", compute_support_resistance, chain)
        run("compute_straddle", compute_straddle, chain)
        run("compute_gex", compute_gex, chain)
        if fchain:
            run("compute_futures_basis", compute_futures_basis,
                fchain, chain.get("underlyingValue", 0))
        else:
            results["compute_futures_basis"] = {
                "ok": False, "error": "skipped: no futures chain for " + sym,
            }
        # Strategy pricers (price_*) - legs built from the chain's strikes.
        _run_strategy_pricers(results, run, chain)
    else:
        for name in ("compute_pcr", "compute_max_pain", "compute_top_oi_strikes",
                     "compute_atm", "compute_iv_skew", "compute_oi_buildup",
                     "compute_support_resistance", "compute_straddle", "compute_gex",
                     "compute_futures_basis", "price_long_straddle", "price_long_strangle",
                     "price_bull_call_spread", "price_bear_put_spread",
                     "price_iron_condor", "price_long_butterfly"):
            results[name] = {
                "ok": False,
                "error": "skipped: no option chain resolved for " + sym,
            }

    # Margin: build a sample instrument from the first futures leg. Quantity
    # must be a multiple of the lot size, so we use exactly one lot.
    legs = fchain.get("legs", []) if isinstance(fchain, dict) else []
    if legs and legs[0].get("instrumentKey"):
        lot = legs[0].get("lotSize") or 0
        if lot > 0:
            run("margin", client.get_margin, [{
                "instrument_key": legs[0]["instrumentKey"],
                "quantity": lot,
                "transaction_type": "BUY",
                "product": "I",
            }])
        else:
            results["margin"] = {
                "ok": False,
                "error": "skipped: futures leg has no lot size for " + sym,
            }
    else:
        results["margin"] = {
            "ok": False,
            "error": "skipped: no futures leg to build a sample margin request for " + sym,
        }

    return {
        "symbol": sym,
        "expiry": expiry,
        "date": today,
        "results": results,
    }


def _run_strategy_pricers(results, run, chain):
    """Exercise every price_* strategy pricer with legs derived from the chain."""
    strikes = sorted(chain.get("strikePrices") or [])
    if not strikes:
        for name in ("price_long_straddle", "price_long_strangle",
                     "price_bull_call_spread", "price_bear_put_spread",
                     "price_iron_condor", "price_long_butterfly"):
            results[name] = {
                "ok": False,
                "error": "skipped: no strikes in chain for " + str(chain.get("symbol", "")),
            }
        return
    atm_val = (compute_atm(chain) or {}).get("atmStrike")
    if atm_val is None:
        atm_val = strikes[len(strikes) // 2]
    atm = min(strikes, key=lambda x: abs(x - atm_val))
    i = strikes.index(atm)

    def at(idx):
        return strikes[idx] if 0 <= idx < len(strikes) else None

    lower, higher = at(i - 1), at(i + 1)
    lower2, higher2 = at(i - 2), at(i + 2)

    run("price_long_straddle", price_strategy, "long_straddle", chain, [
        {"strike": atm, "type": "CE", "qty": 1, "side": "BUY"},
        {"strike": atm, "type": "PE", "qty": 1, "side": "BUY"},
    ])
    if lower and higher:
        run("price_long_strangle", price_strategy, "long_strangle", chain, [
            {"strike": higher, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": lower, "type": "PE", "qty": 1, "side": "BUY"},
        ])
        run("price_bull_call_spread", price_strategy, "bull_call_spread", chain, [
            {"strike": lower, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": higher, "type": "CE", "qty": 1, "side": "SELL"},
        ])
        run("price_bear_put_spread", price_strategy, "bear_put_spread", chain, [
            {"strike": higher, "type": "PE", "qty": 1, "side": "BUY"},
            {"strike": lower, "type": "PE", "qty": 1, "side": "SELL"},
        ])
    if lower2 is not None and lower is not None and higher is not None and higher2 is not None:
        run("price_iron_condor", price_strategy, "iron_condor", chain, [
            {"strike": lower, "type": "PE", "qty": 1, "side": "SELL"},
            {"strike": lower2, "type": "PE", "qty": 1, "side": "BUY"},
            {"strike": higher, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": higher2, "type": "CE", "qty": 1, "side": "SELL"},
        ])
        run("price_long_butterfly", price_strategy, "long_butterfly", chain, [
            {"strike": lower, "type": "CE", "qty": 1, "side": "BUY"},
            {"strike": atm, "type": "CE", "qty": 2, "side": "SELL"},
            {"strike": higher, "type": "CE", "qty": 1, "side": "BUY"},
        ])
