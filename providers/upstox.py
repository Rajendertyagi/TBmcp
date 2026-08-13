"""Upstox v2 data client (PRIMARY broker backend) — tbmcp.

Broker-backed market data only: option chain, expiries, spot price. All fixed
values come from `constants`; the buildup logic lives in `analytics`; the output
shape is defined in `models`. Unit conventions mirror the TypeScript TBMCP version:
Upstox returns option `volume` in shares but `oi` in contracts, so volume is divided
by the lot size to match NSE's "Volume (Contracts)" column.

NseKit / NSE scraping is intentionally NOT used here — this client is Upstox-only.

The client is split by responsibility into focused mixins (connect, resolution,
market data, fundamentals) plus a shared response-parsing module; this file only
assembles them, so `UpstoxClient` keeps its single stable name and public surface
(the class satisfying the `DataProvider` protocol).
"""
from __future__ import annotations

from .upstox_connect import UpstoxConnectMixin
from .upstox_fundamentals import UpstoxFundamentalsMixin
from .upstox_market_data import UpstoxMarketDataMixin
from .upstox_resolution import UpstoxResolutionMixin


class UpstoxClient(
    UpstoxConnectMixin,
    UpstoxResolutionMixin,
    UpstoxMarketDataMixin,
    UpstoxFundamentalsMixin,
):
    """Thin wrapper over the Upstox v2 REST API — one shared instance."""


__all__ = ["UpstoxClient"]
