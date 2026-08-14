"""Copy-paste template for a new TBMCP data provider — tbmcp.

This is a **starting point**, not a working provider. Copy this file to
``providers/<yourbroker>.py`` and implement the methods your backend serves.
Every method below raises :class:`UnsupportedByProvider` so the
``AffinityRouter`` can fall back to another provider for anything you don't
implement — a data-only backend (like FYERS) only needs a subset.

Study the two real adapters for shape and parsing patterns:
- ``providers/upstox.py`` (+ its mixins) — the full-feature primary provider.
- ``providers/fyers.py`` — a data-only secondary provider (the closest template
  to "implement just the market-data slice").

Rules:
- Keep the public method names identical to the ``DataProvider`` protocol
  (``providers/base.py``). Renaming breaks the contract.
- Return the typed shapes from ``models.py`` (``OptionChain``, ``Candle``,
  ``MarketDepth``, ...).
- Do NOT call your broker directly from MCP tools, Falcon routes, or pages —
  only through this provider.
- Register the new class in ``providers/__init__.py`` (one branch). Removing it
  is then a one-line delete.
"""
from __future__ import annotations

from typing import Any, Optional

from providers.exceptions import UnsupportedByProvider


class ExampleProvider:
    """Skeleton data provider. Replace method bodies with real API calls."""

    name = "example"

    def __init__(self, settings: Any = None, **kwargs: Any) -> None:
        # Accept whatever the factory passes; read your own creds here.
        self._access_token = ""

    # -- auth (only if your backend serves user auth; else leave raising) ------
    def build_login_url(self, api_key: str, redirect_uri: str,
                        code_challenge: Optional[str] = None) -> str:
        raise UnsupportedByProvider(self.name, "build_login_url")

    def exchange_code_for_token(self, code: str, redirect_uri: str,
                                code_verifier: Optional[str] = None) -> str:
        raise UnsupportedByProvider(self.name, "exchange_code_for_token")

    # -- symbol resolution -----------------------------------------------------
    def resolve_key(self, symbol: str) -> str:
        """Return your backend's symbol form for `symbol` (e.g. an index key)."""
        # TODO: map known indices; fall back to an equity form.
        return symbol.upper()

    # -- raw market data (implement the ones your backend serves) ---------------
    def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> dict:
        raise UnsupportedByProvider(self.name, "get_option_chain")

    def get_expiry_dates(self, symbol: str) -> list[str]:
        raise UnsupportedByProvider(self.name, "get_expiry_dates")

    def get_spot_price(self, symbol: str) -> float:
        raise UnsupportedByProvider(self.name, "get_spot_price")

    def get_full_quote(self, symbol: str) -> dict[str, float]:
        raise UnsupportedByProvider(self.name, "get_full_quote")

    def get_full_quotes(self, symbols: list[str]) -> dict[str, dict]:
        raise UnsupportedByProvider(self.name, "get_full_quotes")

    def get_historical_data(self, symbol: str, interval: str = "day",
                            days: int = 60) -> list[dict]:
        raise UnsupportedByProvider(self.name, "get_historical_data")

    def get_futures_chain(self, symbol: str, expiry_date: Optional[str] = None) -> dict:
        raise UnsupportedByProvider(self.name, "get_futures_chain")

    def get_market_depth(self, symbol: str) -> dict:
        raise UnsupportedByProvider(self.name, "get_market_depth")

    def get_margin(self, instruments: list[dict]) -> dict:
        raise UnsupportedByProvider(self.name, "get_margin")

    # -- market information ----------------------------------------------------
    def get_pcr(self, symbol, expiry, date, bucket_interval=60) -> Any:
        raise UnsupportedByProvider(self.name, "get_pcr")

    def get_max_pain(self, symbol, expiry, date, bucket_interval=60) -> Any:
        raise UnsupportedByProvider(self.name, "get_max_pain")

    def get_oi(self, symbol, expiry, date) -> Any:
        raise UnsupportedByProvider(self.name, "get_oi")

    def get_change_oi(self, symbol, expiry, date, interval=1) -> Any:
        raise UnsupportedByProvider(self.name, "get_change_oi")

    def get_fii(self, data_type="NSE_FO|INDEX_FUTURES", interval="1D") -> Any:
        raise UnsupportedByProvider(self.name, "get_fii")

    def get_dii(self, data_type="NSE_EQ|CASH", interval="1D") -> Any:
        raise UnsupportedByProvider(self.name, "get_dii")

    def get_market_status(self, exchange="NSE") -> dict:
        raise UnsupportedByProvider(self.name, "get_market_status")

    def get_market_holidays(self, date: Optional[str] = None) -> list:
        raise UnsupportedByProvider(self.name, "get_market_holidays")

    def get_market_timings(self, date: str) -> Any:
        raise UnsupportedByProvider(self.name, "get_market_timings")

    def get_instruments(self, query: str, exchange: str = "NSE") -> list:
        raise UnsupportedByProvider(self.name, "get_instruments")

    # -- fundamentals / news / greeks -----------------------------------------
    def get_company_profile(self, isin: str) -> Any:
        raise UnsupportedByProvider(self.name, "get_company_profile")

    def get_share_holdings(self, isin: str) -> Any:
        raise UnsupportedByProvider(self.name, "get_share_holdings")

    def get_key_ratios(self, isin: str) -> Any:
        raise UnsupportedByProvider(self.name, "get_key_ratios")

    def get_corporate_actions(self, isin: str) -> Any:
        raise UnsupportedByProvider(self.name, "get_corporate_actions")

    def get_competitors(self, isin: str) -> Any:
        raise UnsupportedByProvider(self.name, "get_competitors")

    def get_news(self, instrument_keys: list[str]) -> Any:
        raise UnsupportedByProvider(self.name, "get_news")

    def get_option_greeks(self, instrument_keys: list[str]) -> dict:
        raise UnsupportedByProvider(self.name, "get_option_greeks")

    def get_option_greeks_for_symbol(self, symbol: str,
                                     expiry_date: Optional[str] = None) -> dict:
        raise UnsupportedByProvider(self.name, "get_option_greeks_for_symbol")


__all__ = ["ExampleProvider"]
