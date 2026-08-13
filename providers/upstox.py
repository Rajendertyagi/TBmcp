"""Upstox v2 data client (PRIMARY broker backend) — rtmcp.

Broker-backed market data only: option chain, expiries, spot price. All fixed
values come from `constants`; the buildup logic lives in `analytics`; the output
shape is defined in `models`. Unit conventions mirror the TypeScript RTMCP version:
Upstox returns option `volume` in shares but `oi` in contracts, so volume is divided
by the lot size to match NSE's "Volume (Contracts)" column.

NseKit / NSE scraping is intentionally NOT used here — this client is Upstox-only.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import date, timedelta
from typing import Any, Optional
from urllib.parse import quote, urlencode

import requests

from config import Settings, now_iso, parse_iso, resolve_token_read_path, save_token
from constants import (
    AUTH_DIALOG_PATH,
    AUTH_RETRY_ATTEMPTS,
    AUTH_SCHEME,
    DEFAULT_RATE_GAP_SECONDS,
    EQUITY_KEY_PREFIX,
    FUNDAMENTAL_COMPANY_PROFILE,
    FUNDAMENTAL_CORPORATE_ACTIONS,
    FUNDAMENTAL_COMPETITORS,
    FUNDAMENTAL_KEY_RATIOS,
    FUNDAMENTAL_SHARE_HOLDINGS,
    FUNDAMENTALS_BASE_PATH,
    HISTORICAL_CANDLE_PATH,
    INDEX_KEYS,
    INDEX_LOT_SIZES,
    INSTRUMENTS_SEARCH_PATH,
    MARGIN_PATH,
    MARKET_CHANGE_OI_PATH,
    MARKET_DII_PATH,
    MARKET_FII_PATH,
    MARKET_HOLIDAYS_PATH,
    MARKET_MAX_PAIN_PATH,
    MARKET_OI_PATH,
    MARKET_PCR_PATH,
    MARKET_QUOTE_LTP_PATH,
    MARKET_QUOTE_QUOTES_PATH,
    MARKET_STATUS_PATH,
    MARKET_TIMINGS_PATH,
    NEWS_PATH,
    OPTION_CHAIN_PATH,
    OPTION_CONTRACT_PATH,
    RATE_LIMIT_BACKOFF_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    TOKEN_ENDPOINT,
    TOKEN_PROACTIVE_REFRESH_AGE_SECONDS,
    UPSTOX_AUTH_SCOPE,
    UPSTOX_BASE_URL,
    UPSTOX_V3_BASE_URL,
)
from analytics import classify_buildup
from models import (
    Candle,
    DepthLevel,
    FuturesChain,
    FuturesLeg,
    Instrument,
    Margin,
    MarginItem,
    MarketDepth,
    MarketHoliday,
    MarketStatus,
    OptionChain,
    OptionChainRow,
    OptionLeg,
)


def _to_float(value: object) -> float | None:
    """Coerce numeric values; Upstox sometimes returns numbers as strings."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


# Module-level logger. Diagnostics are emitted at DEBUG and stay silent unless the
# embedding app configures logging to show them - so a packaged build never floods.
logger = logging.getLogger(__name__)


# Module-level guard so the one-time diagnostic dump is written only once per run.
_FULLQUOTE_DUMPED = False


def _debug_dir() -> str:
    """Runtime directory for one-off debug dumps (system temp, never the source tree)."""
    d = os.path.join(tempfile.gettempdir(), "tbmcp_debug")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _dump_fullquote_debug(symbol: str, key: str, raw: object) -> None:
    """Write the raw /market-quote/quotes response to a debug file once.

    Lets us see exactly what Upstox returns when quote extraction fails, instead of
    guessing. Written under the system temp dir (``tbmcp_debug/``) so it never lands
    in the source tree or a packaged build. Best-effort only and never raises.
    """
    global _FULLQUOTE_DUMPED
    if _FULLQUOTE_DUMPED:
        return
    _FULLQUOTE_DUMPED = True
    try:
        path = os.path.join(_debug_dir(), "debug_fullquote.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"symbol": symbol, "key": key, "response": raw}, fh, default=str, indent=2)
    except Exception:
        pass


def _dump_search_debug(symbol: str, raw: object) -> None:
    """Write the raw instrument-search response to a debug file (overwrites).

    Lets us see exactly what Upstox returns for a symbol lookup - e.g. whether the
    equity (instrument_type EQ) row is present and what its instrument_key is - so
    we stop guessing why resolution fails. Written under the system temp dir.
    Best-effort, never raises.
    """
    try:
        path = os.path.join(_debug_dir(), "debug_search.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"symbol": symbol, "response": raw}, fh, default=str, indent=2)
    except Exception:
        pass


def _dump_contract_debug(symbol: str, key: str, raw: object) -> None:
    """Write the raw /option/contract response to a debug file when empty.

    Shows what Upstox returns for the resolved key so we can tell a bad key apart
    from a genuinely empty contract list. Written under the system temp dir.
    Best-effort, never raises.
    """
    try:
        path = os.path.join(_debug_dir(), "debug_contract.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"symbol": symbol, "key": key, "response": raw}, fh, default=str, indent=2)
    except Exception:
        pass


def _extract_quote_entry(raw: dict[str, Any], key: str) -> dict[str, Any] | None:
    """Find the quote object inside an Upstox /market-quote/quotes response.

    The endpoint is shape-unstable across keys/versions: `data` may be a dict keyed
    by the decoded instrument key, by the URL-encoded key, or be a list of quotes.
    We try the documented shapes first, then fall back to a structural search for the
    first object that carries a price so we never silently miss a valid quote.
    """
    data = raw.get("data")
    if isinstance(data, dict):
        # 1. exact decoded key, then URL-encoded key
        entry = data.get(key) or data.get(quote(key, safe=""))
        if isinstance(entry, dict):
            return entry
        # 2. a value whose own instrument_key matches
        for value in data.values():
            if isinstance(value, dict) and value.get("instrument_key") == key:
                return value
        # 3. structural fallback: first object that carries a last price
        for value in data.values():
            if isinstance(value, dict) and ("last_price" in value or "lastPrice" in value):
                return value
        # 4. `data` itself is the quote (single-instrument responses sometimes omit the key wrapper)
        if "last_price" in data or "lastPrice" in data:
            return data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and (
                item.get("instrument_key") == key
                or "last_price" in item
                or "lastPrice" in item
            ):
                return item
    return None


def _normalize_quote_entry(entry: dict[str, Any] | None) -> dict[str, float] | None:
    """Turn a raw Upstox quote object into {last_price, net_change, p_change}.

    Returns None when there is no usable price (so callers can flag an error
    instead of surfacing a bogus zero). Accepts Upstox's common field variants.
    """
    if not isinstance(entry, dict):
        return None
    last = _to_float(entry.get("last_price") or entry.get("lastPrice"))
    if last is None or last <= 0:
        return None
    raw_change = _to_float(entry.get("net_change") or entry.get("change"))
    ohlc_raw = entry.get("ohlc") or entry
    ohlc = ohlc_raw if isinstance(ohlc_raw, dict) else {}
    prev_close = (
        _to_float(ohlc.get("close"))
        or _to_float(entry.get("prev_close"))
        or 0.0
    )
    if raw_change is not None:
        net_change = raw_change
    elif prev_close > 0:
        net_change = last - prev_close
    else:
        net_change = 0.0
    p_change = (net_change / prev_close * 100) if (prev_close > 0) else 0.0
    return {
        "last_price": last,
        "net_change": net_change,
        "p_change": p_change,
    }


class UpstoxClient:
    """Thin wrapper over the Upstox v2 REST API."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        self._access_token = settings.access_token
        self._rate_gap = max(settings.rate_limit_gap_ms, 0) / 1000.0 or DEFAULT_RATE_GAP_SECONDS
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._ready = False
        # Resolved index instrument keys (Upstox guidance: resolve via the
        # search API rather than hardcoding/guessing display-name strings).
        self._index_key_cache: dict[str, str] = {}
        # Resolved lot sizes. Indices use the static map; stocks are derived
        # from the live option-contract data so volume(contracts) is correct.
        self._lot_size_cache: dict[str, int] = {}

    # -- auth helpers --------------------------------------------------------
    @property
    def access_token(self) -> str:
        return self._access_token

    @access_token.setter
    def access_token(self, value: str) -> None:
        self._access_token = value or ""

    @staticmethod
    def build_login_url(api_key: str, redirect_uri: str, code_challenge: Optional[str] = None) -> str:
        """URL the owner opens in a browser to perform the one-time OAuth login."""
        params: dict[str, str] = {
            "client_id": api_key,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": UPSTOX_AUTH_SCOPE,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{UPSTOX_BASE_URL}{AUTH_DIALOG_PATH}?{urlencode(params)}"

    def exchange_code_for_token(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> str:
        """Exchange an OAuth `code` for an access token and persist it."""
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.api_key,
            "client_secret": self.api_secret,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            body["code_verifier"] = code_verifier
        resp = requests.post(
            f"{UPSTOX_BASE_URL}{TOKEN_ENDPOINT}",
            data=urlencode(body),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        payload = resp.json() if resp.content else {}
        if not resp.ok or not payload.get("access_token"):
            raise RuntimeError(
                f"[Upstox] Token exchange failed ({resp.status_code}): "
                f"{payload.get('error', '')} {payload.get('error_description', '')}".strip()
            )
        save_token(payload["access_token"], payload.get("refresh_token", ""))
        self._access_token = payload["access_token"]
        return payload["access_token"]

    def refresh_access_token(self) -> bool:
        """Silently mint a new access token using the stored refresh token."""
        path = resolve_token_read_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as fh:
                refresh = json_load(fh).get("refresh_token")
        except Exception:
            return False
        if not refresh:
            return False
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": self.api_key,
            "client_secret": self.api_secret,
        }
        try:
            resp = requests.post(
                f"{UPSTOX_BASE_URL}{TOKEN_ENDPOINT}",
                data=urlencode(body),
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            payload = resp.json() if resp.content else {}
        except requests.RequestException as exc:
            logger.debug("[Upstox] Refresh request error: %s", exc)
            return False
        if not resp.ok or not payload.get("access_token"):
            logger.debug("[Upstox] Refresh failed - re-do the one-time login.")
            return False
        save_token(payload["access_token"], payload.get("refresh_token", ""))
        self._access_token = payload["access_token"]
        logger.debug("[Upstox] Access token auto-renewed via refresh token.")
        return True

    # -- lifecycle ------------------------------------------------------------
    def initialize(self) -> None:
        if not self._access_token:
            path = resolve_token_read_path()
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        self._access_token = json_load(fh).get("access_token", "")
                except Exception:
                    pass
        if not self._access_token:
            raise RuntimeError(
                "[Upstox] Access token missing. Do a one-time login:\n"
                "  1. Open the URL from client.build_login_url(api_key, redirect_uri).\n"
                "  2. Log in and copy the `code` from the redirect.\n"
                "  3. Call client.exchange_code_for_token(code, redirect_uri), or set "
                "UPSTOX_ACCESS_TOKEN in your .env."
            )
        # Proactively renew if the stored token is older than ~23h (it expires ~24h).
        path = resolve_token_read_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    saved = json_load(fh).get("savedAt")
                if saved and (time.time() - parse_iso(saved)) > TOKEN_PROACTIVE_REFRESH_AGE_SECONDS:
                    self.refresh_access_token()
            except Exception:
                pass
        self._ready = True

    def ensure_initialized(self) -> None:
        if not self._ready:
            self.initialize()

    # -- transport ------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"{AUTH_SCHEME} {self._access_token}", "Accept": "application/json"}

    def _request(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
        attempt: int = 1,
        base_url: str = UPSTOX_BASE_URL,
    ) -> Any:
        """Rate-limited GET. Retries once after a 401/403 by refreshing the token.

        Note: the Upstox JSON response is unstructured at this network edge; it is
        mapped into typed models by the callers below. This is the only place `Any`
        appears — all domain logic is strongly typed.
        """
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._rate_gap:
                time.sleep(self._rate_gap - elapsed)
            self._last_request_at = time.monotonic()
        url = f"{base_url}{path}"
        if params:
            url += f"?{urlencode(params)}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise RuntimeError(f"[Upstox] Network error: {exc}")
        if resp.status_code in (401, 403):
            if attempt <= AUTH_RETRY_ATTEMPTS and self.refresh_access_token():
                return self._request(path, params, attempt + 1)
            raise RuntimeError("[Upstox] Authentication failed (401/403). Re-run the one-time login.")
        if resp.status_code == 429:
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            raise RuntimeError("[Upstox] Rate limited (429). Retry later.")
        if not resp.ok:
            raise RuntimeError(f"[Upstox] HTTP {resp.status_code} {resp.reason}: {resp.text[:300]}")
        return resp.json()

    def _post(self, path: str, json_body: dict[str, Any], attempt: int = 1) -> Any:
        """Rate-limited POST (used by the margin endpoint). Retries once on 401/403."""
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._rate_gap:
                time.sleep(self._rate_gap - elapsed)
            self._last_request_at = time.monotonic()
        url = f"{UPSTOX_BASE_URL}{path}"
        try:
            resp = requests.post(
                url, json=json_body, headers=self._headers(), timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"[Upstox] Network error: {exc}")
        if resp.status_code in (401, 403):
            if attempt <= AUTH_RETRY_ATTEMPTS and self.refresh_access_token():
                return self._post(path, json_body, attempt + 1)
            raise RuntimeError("[Upstox] Authentication failed (401/403). Re-run the one-time login.")
        if resp.status_code == 429:
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            raise RuntimeError("[Upstox] Rate limited (429). Retry later.")
        if not resp.ok:
            raise RuntimeError(f"[Upstox] HTTP {resp.status_code} {resp.reason}: {resp.text[:300]}")
        return resp.json()

    # -- symbol resolution ----------------------------------------------------
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

    # -- public data API ------------------------------------------------------
    def get_expiry_dates(self, symbol: str) -> list[str]:
        key = self.resolve_key(symbol)
        logger.debug("[expiry] %s: resolved key=%s", symbol, key)
        raw = self._request(OPTION_CONTRACT_PATH, {"instrument_key": key})
        payload = raw.get("data")
        if isinstance(payload, list):
            expiries = [c.get("expiry") for c in payload if c.get("expiry")]
        elif isinstance(payload, dict) and isinstance(payload.get("expiry"), list):
            expiries = payload["expiry"]
        else:
            expiries = []
        if not expiries:
            logger.debug(
                "[expiry] %s: NO expiries from %s (status=%s)",
                symbol, key, raw.get("status") if isinstance(raw, dict) else "?",
            )
            _dump_contract_debug(symbol, key, raw)
        else:
            logger.debug("[expiry] %s: %s expiries from %s", symbol, len(expiries), key)
        return sorted({e for e in expiries if e})

    def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> OptionChain:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        lot_size = self.get_lot_size(symbol)
        logger.debug("[chain] %s: key=%s lot_size=%s expiry=%s",
                     symbol, key, lot_size, expiry_date or "nearest")
        if not expiry_date:
            # Resolve the nearest expiry up front; we reuse this list below for
            # `expiryDates`, so only the explicit-expiry path fetches it again.
            expiries = self.get_expiry_dates(symbol)
            if not expiries:
                raise RuntimeError(f"[Upstox] No option expiries found for '{symbol}'.")
            expiry_date = expiries[0]
        else:
            expiries = None  # fetched below only if an explicit expiry was requested

        raw = self._request(OPTION_CHAIN_PATH, {"instrument_key": key, "expiry_date": expiry_date})
        payload = raw.get("data")
        items = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
        underlying = items[0].get("underlying_spot_price", 0) if items else 0

        rows: list[OptionChainRow] = []
        totals = {"ce_oi": 0, "pe_oi": 0, "ce_vol": 0, "pe_vol": 0}
        for item in items:
            strike = item.get("strike_price", 0)
            ce = self._map_leg(item.get("call_options"), "CE", strike, expiry_date, underlying, lot_size)
            pe = self._map_leg(item.get("put_options"), "PE", strike, expiry_date, underlying, lot_size)
            row: OptionChainRow = {"strikePrice": strike, "expiryDate": expiry_date}
            if ce:
                row["CE"] = ce
                totals["ce_oi"] += ce["openInterest"]
                totals["ce_vol"] += ce["totalTradedVolume"]
            if pe:
                row["PE"] = pe
                totals["pe_oi"] += pe["openInterest"]
                totals["pe_vol"] += pe["totalTradedVolume"]
            rows.append(row)
        rows.sort(key=lambda r: r["strikePrice"])
        # Only re-fetch the full expiry list when an explicit expiry was requested
        # (the `if not expiry_date` branch above already resolved it).
        if expiries is None:
            expiries = self.get_expiry_dates(symbol)
        return {
            "symbol": symbol,
            "underlyingValue": underlying,
            "expiryDate": expiry_date,
            "expiryDates": expiries,
            "strikePrices": [r["strikePrice"] for r in rows],
            "rows": rows,
            "timestamp": now_iso(),
            "totalCEOpenInterest": totals["ce_oi"],
            "totalPEOpenInterest": totals["pe_oi"],
            "totalCEVolume": totals["ce_vol"],
            "totalPEVolume": totals["pe_vol"],
        }

    def _map_leg(
        self,
        leg: Optional[dict[str, Any]],
        otype: str,
        strike: float,
        expiry: str,
        underlying: float,
        lot_size: int,
    ) -> Optional[OptionLeg]:
        if not leg:
            return None
        md = leg.get("market_data", {}) or {}
        g = leg.get("option_greeks", {}) or {}
        ltp = md.get("ltp", 0) or 0
        prev_close = md.get("close_price", 0) or 0
        change = ltp - prev_close if prev_close > 0 else 0
        p_change = (change / prev_close * 100) if (prev_close > 0 and ltp > 0) else 0
        oi = md.get("oi", 0) or 0
        prev_oi = md.get("prev_oi", 0) or 0
        oi_change = oi - prev_oi
        oi_change_pct = (oi_change / prev_oi * 100) if prev_oi > 0 else 0
        volume_shares = md.get("volume", 0) or 0
        volume_contracts = round(volume_shares / lot_size) if lot_size > 0 else 0
        return {
            "strikePrice": strike,
            "expiryDate": expiry,
            "optionType": otype,
            "lastPrice": ltp,
            "change": change,
            "pChange": p_change,
            "openInterest": oi,
            "changeinOpenInterest": oi_change,
            "totalTradedVolume": volume_contracts,
            "impliedVolatility": g.get("iv", 0) or 0,
            "delta": g.get("delta"),
            "gamma": g.get("gamma"),
            "theta": g.get("theta"),
            "vega": g.get("vega"),
            "bidQty": md.get("bid_qty", 0) or 0,
            "bidPrice": md.get("bid_price", 0) or 0,
            "askQty": md.get("ask_qty", 0) or 0,
            "askPrice": md.get("ask_price", 0) or 0,
            "underlyingValue": underlying,
            "oiChangePct": oi_change_pct,
            "buildTag": classify_buildup(oi_change, change),
        }

    def get_spot_price(self, symbol: str) -> float:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request(
            MARKET_QUOTE_LTP_PATH, {"instrument_key": key}, base_url=UPSTOX_V3_BASE_URL
        )
        # The V3 LTP response shape is unstable across instruments (indices in
        # particular may omit `last_price` or key the entry differently), so
        # extract defensively and fall back to the full-quote endpoint, which
        # the ticker already uses successfully for indices.
        quote = _extract_quote_entry(raw, key)
        last = None
        if isinstance(quote, dict):
            last = _to_float(quote.get("last_price") or quote.get("lastPrice") or quote.get("ltp"))
        if isinstance(last, (int, float)) and last > 0:
            return float(last)
        try:
            q = self.get_full_quote(symbol)
            last = _to_float(q.get("last_price"))
            if isinstance(last, (int, float)) and last > 0:
                return float(last)
        except Exception:
            pass
        raise RuntimeError(f"[Upstox] No LTP returned for '{key}'.")

    # -- futures, depth, margin, market info ---------------------------------
    def get_futures_chain(self, symbol: str, expiry_date: Optional[str] = None) -> FuturesChain:
        """All futures contracts for `symbol` across expiries, with live quotes.

        The option/contract endpoint only returns CE/PE, so futures are sourced
        from the instruments/search endpoint filtered to the FUT segment, then a
        batched full-quote call fetches live prices/OI. Returns an empty legs list
        if no futures are found for the symbol.
        """
        self.ensure_initialized()
        raw = self._request(INSTRUMENTS_SEARCH_PATH, {
            "query": symbol,
            "segments": "FUT",
            "records": "30",
        })
        data = raw.get("data") if isinstance(raw, dict) else raw
        contracts = data if isinstance(data, list) else []
        futures = [c for c in contracts if str(c.get("instrument_type", "")).upper().startswith("FUT")]
        if expiry_date:
            futures = [c for c in futures if c.get("expiry") == expiry_date]
        keys = [c.get("instrument_key") for c in futures if c.get("instrument_key")]
        quotes: dict[str, Any] = {}
        if keys:
            raw_q = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": ",".join(keys)})
            data_q = raw_q.get("data") if isinstance(raw_q, dict) else None
            if isinstance(data_q, dict):
                for k, v in data_q.items():
                    if isinstance(v, dict):
                        quotes[k] = v
        legs: list[FuturesLeg] = []
        for c in futures:
            k = c.get("instrument_key")
            q = quotes.get(k, {})
            ltp = _to_float(q.get("last_price") or q.get("lastPrice")) or 0
            prev = _to_float(q.get("prev_close") or (q.get("ohlc", {}) or {}).get("close")) or 0
            change = ltp - prev if prev > 0 else 0
            pchg = (change / prev * 100) if prev > 0 else 0
            legs.append({
                "instrumentKey": k,
                "expiryDate": c.get("expiry"),
                "strikePrice": _to_float(c.get("strike_price")) or 0,
                "lastPrice": ltp,
                "change": change,
                "pChange": pchg,
                "openInterest": int(_to_float(q.get("oi") or q.get("open_interest")) or 0),
                "volume": int(_to_float(q.get("volume") or q.get("total_traded_volume")) or 0),
                "lotSize": int(_to_float(c.get("lot_size")) or 0),
            })
        legs.sort(key=lambda l: (l["expiryDate"] or "", l["strikePrice"]))
        expiries = sorted({l["expiryDate"] for l in legs if l["expiryDate"]})
        try:
            underlying = self.get_spot_price(symbol)
        except Exception:
            underlying = 0
        return {
            "symbol": symbol,
            "underlyingValue": underlying,
            "expiryDates": expiries,
            "legs": legs,
            "timestamp": now_iso(),
        }

    def get_market_depth(self, symbol: str) -> MarketDepth:
        """Top-of-book order book (5 bid + 5 ask levels) for `symbol`."""
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": key})
        entry = _extract_quote_entry(raw, key) or {}
        depth = entry.get("depth") or {}

        def _map_side(side: Any) -> list[DepthLevel]:
            out: list[DepthLevel] = []
            for lvl in (side or []):
                if isinstance(lvl, dict):
                    out.append({
                        "quantity": int(_to_float(lvl.get("quantity")) or 0),
                        "price": _to_float(lvl.get("price")) or 0,
                        "orders": int(_to_float(lvl.get("orders") or lvl.get("order_count")) or 0),
                    })
            return out

        return {
            "symbol": symbol,
            "instrumentKey": key,
            "lastPrice": _to_float(entry.get("last_price")) or 0,
            "totalBuyQuantity": int(_to_float(entry.get("total_buy_quantity")) or 0),
            "totalSellQuantity": int(_to_float(entry.get("total_sell_quantity")) or 0),
            "buy": _map_side(depth.get("buy")),
            "sell": _map_side(depth.get("sell")),
            "timestamp": now_iso(),
        }

    def get_margin(self, instruments: list[dict[str, Any]]) -> Margin:
        """Required margin for a basket of instruments (POST /charges/margin).

        `instruments` is a list of {instrument_key, quantity, transaction_type,
        product, price?} dicts (max 20). Returns required/final margin plus a
        per-instrument breakdown.
        """
        self.ensure_initialized()
        raw = self._post(MARGIN_PATH, {"instruments": instruments})
        data = raw.get("data") or {}
        items: list[MarginItem] = []
        for m in data.get("margins", []) or []:
            items.append({
                "spanMargin": _to_float(m.get("span_margin")) or 0,
                "exposureMargin": _to_float(m.get("exposure_margin")) or 0,
                "equityMargin": _to_float(m.get("equity_margin")) or 0,
                "netBuyPremium": _to_float(m.get("net_buy_premium")) or 0,
                "additionalMargin": _to_float(m.get("additional_margin")) or 0,
                "totalMargin": _to_float(m.get("total_margin")) or 0,
                "tenderMargin": _to_float(m.get("tender_margin")) or 0,
            })
        return {
            "requiredMargin": _to_float(data.get("required_margin")) or 0,
            "finalMargin": _to_float(data.get("final_margin")) or 0,
            "margins": items,
        }

    def _market_info(self, path: str, params: dict[str, str]) -> Any:
        """Forward a Market Information request and return its `data` payload."""
        self.ensure_initialized()
        raw = self._request(path, params)
        return raw.get("data") if isinstance(raw, dict) else raw

    def get_pcr(
        self, symbol: str, expiry: str, date: str, bucket_interval: int = 60
    ) -> Any:
        """Put-Call Ratio for an underlying on a given expiry/date (Upstox MI API)."""
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_PCR_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
            "bucket_interval": str(bucket_interval),
        })

    def get_max_pain(
        self, symbol: str, expiry: str, date: str, bucket_interval: int = 60
    ) -> Any:
        """Max Pain strike for an underlying on a given expiry/date (Upstox MI API)."""
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_MAX_PAIN_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
            "bucket_interval": str(bucket_interval),
        })

    def get_oi(self, symbol: str, expiry: str, date: str) -> Any:
        """Open Interest across all strikes for an underlying (Upstox MI API)."""
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_OI_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
        })

    def get_change_oi(self, symbol: str, expiry: str, date: str, interval: int = 1) -> Any:
        """Change in Open Interest per strike over `interval` days (Upstox MI API).

        `interval` is the number of days to look back (the Upstox param is named
        `interval`, not `days`).
        """
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_CHANGE_OI_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
            "interval": str(interval),
        })

    def get_fii(self, data_type: str = "NSE_FO|INDEX_FUTURES", interval: str = "1D") -> Any:
        """Foreign Institutional Investor activity (Upstox MI API).

        `data_type` is a segment such as 'NSE_FO|INDEX_FUTURES' or
        'NSE_FO|STOCK_FUTURES'; `interval` is '1D' or '1M' (NOT 'daily').
        """
        return self._market_info(MARKET_FII_PATH, {
            "data_type": data_type,
            "interval": interval,
        })

    def get_dii(self, data_type: str = "NSE_EQ|CASH", interval: str = "1D") -> Any:
        """Domestic Institutional Investor activity (Upstox MI API).

        `data_type` is a segment such as 'NSE_EQ|CASH' or 'BSE_EQ|CASH';
        `interval` is '1D' or '1M' (NOT 'daily').
        """
        return self._market_info(MARKET_DII_PATH, {
            "data_type": data_type,
            "interval": interval,
        })

    def get_market_status(self, exchange: str = "NSE") -> MarketStatus:
        """Trading status for an exchange (e.g. NSE, BSE, NSE_FO)."""
        self.ensure_initialized()
        raw = self._request(f"{MARKET_STATUS_PATH}/{exchange}")
        data = raw.get("data") if isinstance(raw, dict) else {}
        cas = data.get("cas_eligible_status") or {}
        return {
            "exchange": data.get("exchange", exchange),
            "status": data.get("status"),
            "lastUpdated": data.get("last_updated"),
            "casStatus": cas.get("status"),
            "casLastUpdated": cas.get("last_updated"),
        }

    def get_market_holidays(self, date: Optional[str] = None) -> list[MarketHoliday]:
        """Trading holidays. `date` (yyyy-mm-dd) is optional; omit for the full list."""
        self.ensure_initialized()
        path = MARKET_HOLIDAYS_PATH
        if date:
            path = f"{MARKET_HOLIDAYS_PATH}/{date}"
        raw = self._request(path)
        data = raw.get("data") if isinstance(raw, dict) else raw
        return data if isinstance(data, list) else []

    def get_market_timings(self, date: str) -> Any:
        """Market session timings for a given date (yyyy-mm-dd) — required path param."""
        self.ensure_initialized()
        raw = self._request(f"{MARKET_TIMINGS_PATH}/{date}")
        return raw.get("data") if isinstance(raw, dict) else raw

    def get_instruments(self, query: str, exchange: str = "NSE") -> list[Instrument]:
        """Search tradable instruments by name/symbol."""
        self.ensure_initialized()
        raw = self._request(INSTRUMENTS_SEARCH_PATH, {"query": query, "exchanges": exchange})
        data = raw.get("data") if isinstance(raw, dict) else raw
        return data if isinstance(data, list) else []

    # --- Fundamentals ----------------------------------------------------------
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

    # --- Market quotes ---------------------------------------------------------
    def get_full_quote(self, symbol: str) -> dict[str, float]:
        """Return last price, net change, and percent change for `symbol`.

        Powers the top ticker bar. Uses Upstox's full market-quote endpoint so we
        get `net_change` (vs previous close) directly; percent change is derived
        from it when missing. `symbol` may be an index alias (e.g. NIFTY, INDIAVIX).
        """
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": key})
        entry = _extract_quote_entry(raw, key)
        norm = _normalize_quote_entry(entry)
        if norm is None:
            # Diagnostic: capture the raw payload so we can see the real shape.
            _dump_fullquote_debug(symbol, key, raw)
            raise RuntimeError(f"[Upstox] No quote returned for '{key}'.")
        return norm

    def get_full_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Batched full quotes for the ticker bar - one Upstox call for many symbols.

        The full market-quote endpoint accepts up to 500 comma-separated keys, so
        the ticker fetches everything in a single request instead of one per symbol.
        Returns a dict keyed by the original symbol; a symbol with no/invalid quote
        gets {"error": ...} so one bad symbol can't fail the whole batch.
        """
        self.ensure_initialized()
        key_for: dict[str, str] = {}
        keys: list[str] = []
        for sym in symbols:
            k = self.resolve_key(sym)
            key_for[sym] = k
            keys.append(k)
        raw = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": ",".join(keys)})
        data = raw.get("data") if isinstance(raw, dict) else None
        entries = (
            list(data.values())
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        # Index entries by the fields Upstox may use to identify them, so each symbol
        # maps to its OWN quote. We deliberately avoid the lenient "first object with
        # a price" fallback (used by _extract_quote_entry for single calls) because in
        # a batched response that would grab a neighbouring symbol's data.
        by_token: dict[str, dict] = {}
        by_symbol: dict[str, dict] = {}
        for val in entries:
            if isinstance(val, dict):
                if val.get("instrument_token"):
                    by_token[val["instrument_token"].lower()] = val
                if val.get("symbol"):
                    by_symbol[val["symbol"].lower()] = val
        out: dict[str, dict] = {}
        matched_any = False
        for sym in symbols:
            k = key_for[sym]
            entry = (
                by_token.get(k.lower())
                or by_symbol.get(sym.lower())
                or (data.get(k) if isinstance(data, dict) else None)
                or by_token.get(quote(k, safe="").lower())
            )
            norm = _normalize_quote_entry(entry)
            if norm is not None:
                matched_any = True
            out[sym] = norm if norm is not None else {"error": f"No quote for {sym}"}
        if not matched_any and entries:
            # Diagnostic: capture the raw payload so we can see the real shape.
            _dump_fullquote_debug(",".join(symbols), ",".join(keys), raw)
        return out

    def get_historical_data(self, symbol: str, interval: str = "day", days: int = 60) -> list[Candle]:
        """Fetch OHLC candles for `symbol` from Upstox and return typed Candle list.

        Uses the v2 historical-candle endpoint. Index symbols resolve via INDEX_KEYS
        (verified) or, when unknown, the official Instrument Search API; anything else
        is treated as an equity (NSE_EQ|SYMBOL). `time` is normalised to
        the shape lightweight-charts wants (UNIX seconds for intraday, 'yyyy-mm-dd' for
        daily). Returns [] if no candles are available.
        """
        self.ensure_initialized()
        # Upstox only serves intraday candles (1minute/30minute) for a limited
        # recent window, so cap the look-back to avoid a 400 on long ranges.
        if interval in ("1minute", "30minute") and days > 30:
            days = 30
        key = self.resolve_key(symbol)
        to_date = date.today().isoformat()
        from_date = (date.today() - timedelta(days=days)).isoformat()
        # The key (e.g. "NSE_INDEX|Nifty 50") sits in the URL PATH, so its pipe
        # and space must be percent-encoded - otherwise Upstox rejects it as an
        # "Invalid Instrument key". Query-param calls encode automatically; this one does not.
        path = f"{HISTORICAL_CANDLE_PATH}/{quote(key, safe='')}/{interval}/{to_date}/{from_date}"
        raw = self._request(path)
        payload = raw.get("data") or {}
        rows = payload.get("candles") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []
        candles: list[Candle] = []
        for row in rows:
            # Upstox candle = [epoch_ms, open, high, low, close, volume, (oi)]
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                continue
            ts_ms, o, h, l, c, v = row[0], row[1], row[2], row[3], row[4], row[5]
            candles.append({
                "time": _normalise_candle_time(ts_ms),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            })
        candles.sort(key=lambda c: c["time"])
        return candles


def _normalise_candle_time(ts: object) -> "int | str":
    """Convert an Upstox candle timestamp to the shape lightweight-charts wants.

    Upstox returns two different shapes depending on the interval:
    - intraday (1minute/30minute): epoch milliseconds (int/float)
    - daily/weekly/monthly: an ISO date-time string e.g. '2026-08-11T00:00:00+05:30'
    lightweight-charts wants intraday as a UNIX timestamp in SECONDS and daily data
    as a 'yyyy-mm-dd' business-day string (its recommended daily format, which also
    avoids any timezone off-by-one). Mixed/unknown shapes raise.
    """
    if isinstance(ts, (int, float)):
        value = float(ts)
        if value > 1e12:  # epoch milliseconds -> seconds
            value /= 1000.0
        return int(value)
    if isinstance(ts, str):
        s = ts.strip()
        if "T" in s:  # full ISO date-time -> take the calendar date portion
            return s.split("T", 1)[0]
        return s  # already a 'yyyy-mm-dd' date string
    raise ValueError(f"Unrecognised candle timestamp: {ts!r}")


def json_load(fh) -> dict[str, Any]:
    """Minimal JSON loader returning an empty-ish dict on parse failure."""
    import json

    try:
        return json.load(fh)
    except Exception:
        return {}
