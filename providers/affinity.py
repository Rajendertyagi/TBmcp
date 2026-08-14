"""Per-symbol sticky-affinity router across multiple data providers — tbmcp.

When more than one broker is active (e.g. Upstox primary + FYERS secondary), the
router sits in front of them and presents the same ``DataProvider`` surface to
the MCP tools and the dashboard. Its job is to decide *which* broker answers
each call:

- **Per-symbol stickiness.** The first time a symbol is requested, the router
  picks a healthy provider that supports the method and *pins* that symbol to
  it. Every later call for the same symbol goes to the same broker, so a single
  option chain never mixes Upstox and FYERS numbers.
- **Secondary / fallback.** The primary (Upstox) is tried first; if it is down
  or doesn't serve a method, the router fails over to the next healthy provider
  and pins the symbol there.
- **Circuit breaker.** A provider that errors is briefly marked "down" so we
  don't hammer it, then retried after a cooldown.
- **``resolve_key`` is special.** The dashboard's batch runner expects the
  Upstox key format, so the router always prefers the primary's ``resolve_key``
  and only falls back if the primary is unavailable — it never raises.

Affinity is **in-memory only** (per session); sharing it between the AI and the
dashboard is a later phase.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from providers.exceptions import UnsupportedByProvider

# Methods whose first positional argument is the underlying `symbol` and so are
# routed by per-symbol affinity. Everything else (fundamentals, market-info,
# auth, basket margin) is not symbol-keyed and always goes through the order.
_SYMBOL_KEYED = {
    "get_option_chain",
    "get_expiry_dates",
    "get_spot_price",
    "get_full_quote",
    "get_full_quotes",
    "get_historical_data",
    "get_futures_chain",
    "get_market_depth",
    "get_pcr",
    "get_max_pain",
    "get_oi",
    "get_change_oi",
    "get_option_greeks_for_symbol",
}

# Methods generated as thin dispatchers (resolve_key is handled explicitly).
_DISPATCHED = [
    "get_option_chain", "get_expiry_dates", "get_spot_price", "get_full_quote",
    "get_full_quotes", "get_historical_data", "get_futures_chain",
    "get_market_depth", "get_margin", "get_pcr", "get_max_pain", "get_oi",
    "get_change_oi", "get_fii", "get_dii", "get_market_status",
    "get_market_holidays", "get_market_timings", "get_instruments",
    "get_company_profile", "get_share_holdings", "get_key_ratios",
    "get_corporate_actions", "get_competitors", "get_news",
    "get_option_greeks", "get_option_greeks_for_symbol",
    "build_login_url", "exchange_code_for_token",
]

CIRCUIT_COOLDOWN_SECONDS = 30.0


class AffinityRouter:
    """Routes DataProvider calls across active providers with per-symbol pinning."""

    def __init__(self, providers: dict[str, Any], primary: str = "upstox") -> None:
        self._providers = providers
        self._primary = primary if primary in providers else next(iter(providers))
        self._order = [self._primary] + [n for n in providers if n != self._primary]
        self._affinity: dict[str, str] = {}
        self._down: dict[str, float] = {}

    # -- health / circuit breaker ---------------------------------------------
    def _healthy(self, name: str) -> bool:
        until = self._down.get(name)
        return until is None or time.time() > until

    def _mark_down(self, name: str) -> None:
        self._down[name] = time.time() + CIRCUIT_COOLDOWN_SECONDS

    # -- routing core ----------------------------------------------------------
    def _dispatch(self, method: str, args: tuple, kwargs: dict) -> Any:
        key = args[0] if (method in _SYMBOL_KEYED and args) else None
        if key is not None and key in self._affinity:
            order = [self._affinity[key]] + [n for n in self._order if n != self._affinity[key]]
        else:
            order = list(self._order)
        pinned = key is not None and key in self._affinity
        last_exc: Optional[Exception] = None
        for name in order:
            if not self._healthy(name):
                continue
            provider = self._providers[name]
            fn = getattr(provider, method)
            try:
                result = fn(*args, **kwargs)
            except UnsupportedByProvider as exc:
                last_exc = exc
                continue
            except Exception as exc:
                self._mark_down(name)
                last_exc = exc
                if pinned:
                    raise
                continue
            if key is not None and key not in self._affinity:
                self._affinity[key] = name
            return result
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("[router] No healthy provider available for " + method)

    # resolve_key is special: the dashboard batch expects the Upstox key format,
    # so always prefer the primary and never raise.
    def resolve_key(self, symbol: str) -> str:
        for name in self._order:
            if not self._healthy(name):
                continue
            try:
                return getattr(self._providers[name], "resolve_key")(symbol)
            except Exception:
                self._mark_down(name)
        return f"NSE_INDEX|{symbol}"


def _make_dispatcher(method: str):
    def _call(self, *args, **kwargs):
        return self._dispatch(method, args, kwargs)
    _call.__name__ = method
    return _call


for _m in _DISPATCHED:
    setattr(AffinityRouter, _m, _make_dispatcher(_m))


__all__ = ["AffinityRouter"]
