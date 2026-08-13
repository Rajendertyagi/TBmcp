"""Market-data HTTP endpoints: ticker, quote, chain, expiries, history, vix.

Each class is a thin Falcon Resource that translates one HTTP endpoint to a
DataProvider call, sharing the ``_json`` / ``_safe`` / ``get_client`` helpers
from :mod:`api.app`.
"""
from __future__ import annotations

import falcon

from constants import TICKER_SYMBOLS, VIX_SYMBOL

from ..render import chain_css, render_chain
from ..app import _json, _safe, get_client


class TickerResource:
    def on_get(self, req, resp):
        result = _safe(get_client().get_full_quotes, list(TICKER_SYMBOLS))
        if isinstance(result, dict) and "error" not in result:
            out = []
            for sym in TICKER_SYMBOLS:
                q = dict(result.get(sym, {"error": "no quote"}))
                q["symbol"] = sym
                out.append(q)
            _json(resp, out)
        else:
            msg = result.get("error", "no quote") if isinstance(result, dict) else "no quote"
            _json(resp, [{"symbol": s, "error": msg} for s in TICKER_SYMBOLS])

class QuoteResource:
    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        if not sym:
            _json(resp, {"error": "missing symbol"}, falcon.HTTP_400)
            return
        _json(resp, _safe(get_client().get_full_quote, sym))

class ChainResource:
    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        expiry = (req.get_param("expiry") or "").strip() or None
        if not sym:
            _json(resp, {"error": "missing symbol"}, falcon.HTTP_400)
            return
        chain = _safe(get_client().get_option_chain, sym, expiry)
        if isinstance(chain, dict) and "error" in chain:
            _json(resp, chain)
            return
        ce_oi = chain.get("totalCEOpenInterest", 0) or 0
        pe_oi = chain.get("totalPEOpenInterest", 0) or 0
        pcr = (pe_oi / ce_oi) if ce_oi else 0
        _json(resp, {
            "html": render_chain(chain),
            "css": chain_css(),
            "stats": {
                "spot": chain.get("underlyingValue", 0),
                "pcr": pcr,
                "ceOi": ce_oi,
                "peOi": pe_oi,
            },
            "expiryDates": chain.get("expiryDates", []),
            "expiryDate": chain.get("expiryDate", ""),
            "timestamp": chain.get("timestamp", ""),
        })

class ExpiriesResource:
    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        if not sym:
            _json(resp, {"error": "missing symbol"}, falcon.HTTP_400)
            return
        _json(resp, {"expiries": _safe(get_client().get_expiry_dates, sym)})

class HistoryResource:
    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "").strip().upper()
        interval = (req.get_param("interval") or "day").strip()
        try:
            days = int(req.get_param("days") or 60)
        except ValueError:
            days = 60
        if not sym:
            _json(resp, {"error": "missing symbol"}, falcon.HTTP_400)
            return
        candles = _safe(get_client().get_historical_data, sym, interval, days)
        _json(resp, {"candles": candles if isinstance(candles, list) else []})

class VixResource:
    def on_get(self, req, resp):
        _json(resp, _safe(get_client().get_full_quote, VIX_SYMBOL))
