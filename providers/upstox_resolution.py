"""Instrument-key and lot-size resolution for the Upstox client — tbmcp.

Symbols must be turned into Upstox instrument keys before any data call; this
mixin owns that mapping (index map, search API, cache, fallback) plus the
contracts-per-lot size derivation used to normalise volumes.
"""
from __future__ import annotations

from constants import (
    EQUITY_KEY_PREFIX,
    INDEX_KEYS,
    INDEX_LOT_SIZES,
    INSTRUMENTS_SEARCH_PATH,
    OPTION_CONTRACT_PATH,
)

from .upstox_parsing import _dump_search_debug, logger


class UpstoxResolutionMixin:
    """Resolve symbols to instrument keys and derive lot sizes."""

    def resolve_key(self, symbol: str) -> str:
        upper = symbol.strip().upper()
        if upper in INDEX_KEYS:
            logger.debug("[resolve] %s: index map -> %s", upper, INDEX_KEYS[upper])
            return INDEX_KEYS[upper]
        # Unknown symbol: resolve the index instrument_key via the search API
        # (Upstox guidance: never hardcode or guess keys). Cached per symbol.
        if upper in self._index_key_cache:
            logger.debug("[resolve] %s: cache -> %s", upper, self._index_key_cache[upper])
            return self._index_key_cache[upper]
        key = self._search_instrument_key(upper) or f"{EQUITY_KEY_PREFIX}{upper}"
        if key.startswith(EQUITY_KEY_PREFIX) and upper not in self._index_key_cache:
            logger.debug("[resolve] %s: search FAILED, fallback -> %s (likely invalid)", upper, key)
        self._index_key_cache[upper] = key
        return key

    def get_lot_size(self, symbol: str) -> int:
        """Lot size (contracts per lot) for `symbol`.

        Indices use the static :data:`INDEX_LOT_SIZES` map (fast, no API call).
        Stocks aren't in that map, so their lot size is derived from the live
        option-contract data via the ``/option/contract`` endpoint and cached.
        Falls back to 1 if it can't be resolved.
        """
        upper = symbol.strip().upper()
        if upper in INDEX_LOT_SIZES:
            return INDEX_LOT_SIZES[upper]
        if upper in self._lot_size_cache:
            return self._lot_size_cache[upper]
        lot = 1
        try:
            raw = self._request(
                OPTION_CONTRACT_PATH, {"instrument_key": self.resolve_key(upper)}
            )
            payload = raw.get("data")
            contracts = (
                payload
                if isinstance(payload, list)
                else (payload.get("data") if isinstance(payload, dict) else [])
            )
            for c in contracts:
                ls = c.get("lot_size") or c.get("lotSize")
                if isinstance(ls, int) and ls > 0:
                    lot = ls
                    break
        except Exception:
            pass
        self._lot_size_cache[upper] = lot
        return lot

    def _search_instrument_key(self, symbol: str) -> str | None:
        """Resolve an instrument_key for `symbol` via Upstox's Instrument Search API.

        Handles both indices and stocks (equities). Returns the key of the
        underlying instrument (instrument_type EQ or INDEX) whose trading_symbol
        matches exactly, falling back to an exact name match then a substring
        match. We never guess the display-name portion of the key. FUT/CE/PE
        derivatives are ignored so we resolve the underlying, not a contract.
        """
        try:
            raw = self._request(
                INSTRUMENTS_SEARCH_PATH,
                {"query": symbol, "segments": "EQ,INDEX", "records": "30"},
            )
        except Exception as exc:
            logger.debug("[resolve] %s: search request error -> %s", symbol, exc)
            return None
        _dump_search_debug(symbol, raw)
        data = raw.get("data") if isinstance(raw, dict) else raw
        if not isinstance(data, list):
            logger.debug(
                "[resolve] %s: search returned no data array (status=%s)",
                symbol,
                raw.get("status") if isinstance(raw, dict) else "?",
            )
            return None
        # Pick the best underlying match (exact trading_symbol first, then exact
        # name, then substring) so we never grab the wrong contract.
        exact_ts = exact_nm = substring = None
        for item in data:
            itype = str(item.get("instrument_type", "")).upper()
            # Only the underlying (equity or index) - never a derivative contract.
            if itype not in ("EQ", "INDEX"):
                continue
            ts = str(item.get("trading_symbol", "")).upper()
            nm = str(item.get("name", "")).upper()
            if ts == symbol:
                exact_ts = item.get("instrument_key")
            elif nm == symbol:
                exact_nm = item.get("instrument_key")
            elif symbol in ts or symbol in nm:
                substring = substring or item.get("instrument_key")
        key = exact_ts or exact_nm or substring
        logger.debug(
            "[resolve] %s: search rows=%s exact_ts=%s exact_nm=%s substring=%s -> %s",
            symbol, len(data), exact_ts, exact_nm, substring, key,
        )
        return key
