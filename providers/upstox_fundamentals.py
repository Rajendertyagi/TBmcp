"""Fundamentals, news, and option Greeks from Upstox — tbmcp.

The Upstox fundamentals API is keyed by ISIN; news and greeks are keyed by
instrument keys. This mixin owns those calls and is composed into
:class:`UpstoxClient` alongside the other mixins.
"""
from __future__ import annotations

from typing import Any, Optional

from constants import (
    FUNDAMENTALS_BASE_PATH,
    FUNDAMENTAL_COMPANY_PROFILE,
    FUNDAMENTAL_CORPORATE_ACTIONS,
    FUNDAMENTAL_COMPETITORS,
    FUNDAMENTAL_KEY_RATIOS,
    FUNDAMENTAL_SHARE_HOLDINGS,
    NEWS_PATH,
    OPTION_CONTRACT_PATH,
    OPTION_GREEKS_PATH,
    UPSTOX_V3_BASE_URL,
)


class UpstoxFundamentalsMixin:
    """Fundamentals endpoints, news, and option Greeks."""

    def _fundamental(self, isin: str, path_suffix: str) -> Any:
        """Fetch a single fundamentals endpoint for an ISIN.

        The Upstox fundamentals API is keyed by ISIN (e.g. ``INE002A01018``).
        Response shape is uniform: ``{"status": "success", "data": <object|list>}``.
        Returns ``{"error": ...}`` on 4xx so callers can surface a clean message.
        """
        self.ensure_initialized()
        try:
            raw = self._request(f"{FUNDAMENTALS_BASE_PATH}/{isin}{path_suffix}")
        except RuntimeError as exc:
            # Upstox returns 400 for unknown ISINs or missing data — surface it cleanly.
            return {"error": str(exc)}
        if isinstance(raw, dict) and raw.get("status") == "error":
            return {"error": raw.get("message") or "fundamentals request failed"}
        return raw.get("data") if isinstance(raw, dict) else raw

    def get_company_profile(self, isin: str) -> dict:
        """Business description, sector, and sector market cap for a company."""
        return self._fundamental(isin, FUNDAMENTAL_COMPANY_PROFILE)

    def get_share_holdings(self, isin: str) -> list:
        """Quarterly shareholding pattern by category (promoters, FII, DII, ...)."""
        return self._fundamental(isin, FUNDAMENTAL_SHARE_HOLDINGS)

    def get_key_ratios(self, isin: str) -> list:
        """P/E, P/B, ROA, ROE, ROCE, EV/EBITDA with sector benchmarks."""
        return self._fundamental(isin, FUNDAMENTAL_KEY_RATIOS)

    def get_corporate_actions(self, isin: str) -> list:
        """Dividends, bonuses, splits, rights issues with dates and amounts."""
        return self._fundamental(isin, FUNDAMENTAL_CORPORATE_ACTIONS)

    def get_competitors(self, isin: str, exchange: str = "NSE") -> list:
        """Peer companies with their instrument keys and sector market cap.

        NOTE: Unlike other fundamentals endpoints, this one requires a full
        instrument key (e.g. ``NSE_EQ|INE002A01018``), not just the ISIN.
        """
        key = f"{exchange}_EQ|{isin}"
        return self._fundamental(key, FUNDAMENTAL_COMPETITORS)

    def get_news(self, instrument_keys: list[str]) -> dict:
        """News articles for up to 30 instrument keys (past 7 days)."""
        self.ensure_initialized()
        keys_param = ",".join(str(k) for k in instrument_keys[:30])
        raw = self._request(
            NEWS_PATH,
            {"category": "instrument_keys", "instrument_keys": keys_param},
        )
        return raw.get("data") if isinstance(raw, dict) else {}

    def get_option_greeks(self, instrument_keys: list[str]) -> dict:
        """Option Greeks (IV, delta, gamma, theta, vega) for up to 50 keys.

        Uses the V3 market-quote endpoint. Returns a dict keyed by instrument key
        (with ':' separator in response, e.g. ``NSE_FO:NIFTY2540923000CE``).
        """
        self.ensure_initialized()
        keys_param = ",".join(str(k) for k in instrument_keys[:50])
        raw = self._request(
            OPTION_GREEKS_PATH,
            {"instrument_key": keys_param},
            base_url=UPSTOX_V3_BASE_URL,
        )
        return raw.get("data") if isinstance(raw, dict) else {}

    def get_option_greeks_for_symbol(self, symbol: str, expiry_date: Optional[str] = None) -> dict:
        """Fetch option Greeks for all strikes in a symbol's chain.

        Chains: resolve symbol -> fetch option contracts (for instrument keys)
        -> optionally filter by expiry -> batch-fetch greeks -> return result.
        """
        key = self.resolve_key(symbol)
        # Fetch all option contracts for the underlying
        raw = self._request(OPTION_CONTRACT_PATH, {"instrument_key": key})
        contracts = raw.get("data", []) if isinstance(raw, dict) else []
        if not contracts:
            return {"error": f"no option contracts found for {symbol}"}
        # Extract instrument keys, optionally filtering by expiry
        instrument_keys: list[str] = []
        for c in contracts:
            k = c.get("instrument_key")
            if not k:
                continue
            if expiry_date:
                # Match by expiry string (YYYY-MM-DD)
                contract_expiry = c.get("expiry", "")
                if contract_expiry != expiry_date:
                    continue
            instrument_keys.append(k)
            if len(instrument_keys) >= 50:
                break
        if not instrument_keys:
            return {"error": f"no option keys found for {symbol}" + (f" expiry={expiry_date}" if expiry_date else "")}
        return self.get_option_greeks(instrument_keys)
