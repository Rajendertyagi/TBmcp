"""Fundamentals / news / option-Greeks HTTP endpoints.

Each class is a thin Falcon Resource that translates one HTTP endpoint to a
DataProvider call, sharing the ``_json`` / ``_safe`` / ``get_client`` helpers
from :mod:`api.app`. ``_fundamentals_call`` dispatches to the individual
fundamentals endpoints by name.
"""
from __future__ import annotations

import falcon

from ..app import _json, _safe, get_client


class OptionGreeksResource:
    """Live option Greeks for a symbol's option chain (IV, delta, gamma, theta, vega)."""

    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        expiry = (req.get_param("expiry") or "").strip() or None
        if not sym:
            _json(resp, {"error": "missing symbol"}, falcon.HTTP_400)
            return
        client = get_client()
        _json(resp, _safe(client.get_option_greeks_for_symbol, sym, expiry))


class FundamentalsResource:
    """Fetch a single fundamentals endpoint for a symbol."""

    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        endpoint = (req.get_param("endpoint") or "").strip().lower()
        if not sym or not endpoint:
            _json(resp, {"error": "missing symbol or endpoint"}, falcon.HTTP_400)
            return
        _json(resp, _safe(_fundamentals_call, sym, endpoint))


class NewsResource:
    """Fetch news articles for a symbol (past 7 days)."""

    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        if not sym:
            _json(resp, {"error": "missing symbol"}, falcon.HTTP_400)
            return
        _json(resp, _safe(get_client().get_news, [get_client().resolve_key(sym)]))


def _fundamentals_call(sym: str, endpoint: str) -> dict:
    """Dispatch a fundamentals call by endpoint name."""
    client = get_client()
    key = client.resolve_key(sym)
    if "|" not in key:
        return {"error": f"symbol '{sym}' is not an equity (no ISIN)"}
    isin = key.split("|", 1)[1]
    dispatch = {
        "company_profile": client.get_company_profile,
        "share_holdings": client.get_share_holdings,
        "key_ratios": client.get_key_ratios,
        "corporate_actions": client.get_corporate_actions,
        "competitors": client.get_competitors,
    }
    fn = dispatch.get(endpoint)
    if fn is None:
        return {"error": f"unknown fundamentals endpoint: {endpoint}"}
    return fn(isin)
