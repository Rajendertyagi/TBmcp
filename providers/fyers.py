"""FYERS v3 data client (SECONDARY, data-only broker backend) — tbmcp.

A separate, self-contained adapter behind the same ``DataProvider`` protocol
Upstox satisfies. It is **data-only**: option chain, quotes, depth, history and
option Greeks. Anything FYERS does not serve (margin, fundamentals, market-info
PCR/max-pain/OI/FII-DII, status/holidays/timings, instruments, news, auth user
endpoints) raises :class:`UnsupportedByProvider` so the affinity router can fall
back to another provider for that call.

Transport is plain ``requests`` (the official ``fyers-apiv3`` SDK was dropped:
its pinned ``aiohttp==3.9.3`` fails to build on Python 3.13 without the MSVC
toolchain). Endpoints verified against FYERS v3 docs (data host
``https://api-t1.fyers.in/data``; auth host ``https://api-t1.fyers.in``).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from analytics import classify_buildup
from models import (
    Candle,
    DepthLevel,
    MarketDepth,
    OptionChain,
    OptionChainRow,
    OptionLeg,
)
from providers.exceptions import UnsupportedByProvider

logger = logging.getLogger("providers.fyers")

# --- portable paths (mirror config.py so the folder stays portable) ----------
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FYERS_TOKEN_FILE = os.path.join(_APP_DIR, ".fyers-token.json")
FYERS_ENV_FILE = os.path.join(_APP_DIR, ".env")

# --- FYERS v3 endpoints -------------------------------------------------------
FYERS_DATA_HOST = "https://api-t1.fyers.in/data"
FYERS_AUTH_HOST = "https://api-t1.fyers.in"
GEN_AUTHCODE_PATH = "/api/v3/generate-authcode"
VALIDATE_AUTHCODE_PATH = "/api/v3/validate-authcode"
VALIDATE_REFRESH_PATH = "/api/v3/validate-refresh-token"

# TOTP (daily auto-login) flow hosts — the browser session used to mint an
# auth_code without a manual copy-paste. SEBI Apr-2026 changes made the refresh
# token unreliable, so daily TOTP login is the dependable path.
FYERS_OTP_HOST = "https://api-t2.fyers.in/vagator/v2"
FYERS_TOKEN_V2_PATH = "https://api.fyers.in/api/v2/token"

# --- tuning -------------------------------------------------------------------
PROVIDER_TIMEOUT = int(os.environ.get("FYERS_TIMEOUT", "10"))  # seconds
FYERS_STRIKE_COUNT = int(os.environ.get("FYERS_STRIKE_COUNT", "50"))  # max 50
AUTH_RETRY_ATTEMPTS = 1

# Index symbol -> FYERS underlying symbol (the `-INDEX` form for index options).
FYERS_INDEX_KEYS: dict[str, str] = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "BANKNIFTY50": "NSE:NIFTYBANK-INDEX",
    "NIFTY BANK": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "FIN NIFTY": "NSE:FINNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "INDIAVIX": "NSE:INDIAVIX-INDEX",
    "INDIA VIX": "NSE:INDIAVIX-INDEX",
}


# --- env reader (self-contained; config.py is intentionally untouched) --------
def _read_env_file(path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                data[key.strip()] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return data


def load_fyers_env() -> dict[str, str]:
    """Read FYERS credentials from process env (wins) then the portable .env."""
    merged = {**_read_env_file(FYERS_ENV_FILE), **dict(os.environ)}
    return {
        "app_id": merged.get("FYERS_APP_ID", ""),
        "secret": merged.get("FYERS_SECRET", ""),
        "pin": merged.get("FYERS_PIN", ""),
        "totp_secret": merged.get("FYERS_TOTP_SECRET", ""),
        "redirect_uri": merged.get("FYERS_REDIRECT_URI", ""),
        "access_token": merged.get("FYERS_ACCESS_TOKEN", ""),
        "enabled": merged.get("FYERS_ENABLED", "false").strip().lower()
        in ("1", "true", "yes", "on"),
    }


def _app_id_hash(app_id: str, secret: str) -> str:
    return hashlib.sha256(f"{app_id}:{secret}".encode()).hexdigest()


def _opt_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class FyersClient:
    """Data-only FYERS v3 adapter satisfying the ``DataProvider`` protocol.

    Construct with explicit credentials (the factory reads them from env). Only
    the data methods are implemented; everything else raises
    :class:`UnsupportedByProvider`.
    """

    def __init__(
        self,
        app_id: str = "",
        secret: str = "",
        pin: str = "",
        access_token: str = "",
        redirect_uri: str = "",
        totp_secret: str = "",
    ) -> None:
        self.app_id = app_id
        self.secret = secret
        self.pin = pin
        self.redirect_uri = redirect_uri
        self._access_token = access_token
        self._totp_secret_value = totp_secret
        self._ready = False

    # -- auth helpers ----------------------------------------------------------
    @property
    def access_token(self) -> str:
        return self._access_token

    @access_token.setter
    def access_token(self, value: str) -> None:
        self._access_token = value or ""

    @staticmethod
    def build_login_url(
        api_key: str, redirect_uri: str, code_challenge: Optional[str] = None
    ) -> str:
        """URL the owner opens to perform the one-time FYERS OAuth login."""
        params = {
            "client_id": api_key,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": "tbmcp",
        }
        return f"{FYERS_AUTH_HOST}{GEN_AUTHCODE_PATH}?{urlencode(params)}"

    def exchange_code_for_token(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> str:
        """Exchange an OAuth ``code`` for an access token and persist it."""
        body = {
            "grant_type": "authorization_code",
            "appIdHash": _app_id_hash(self.app_id, self.secret),
            "code": code,
        }
        resp = requests.post(
            f"{FYERS_AUTH_HOST}{VALIDATE_AUTHCODE_PATH}",
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=PROVIDER_TIMEOUT,
        )
        payload = resp.json() if resp.content else {}
        if payload.get("s") != "ok" or not payload.get("access_token"):
            raise RuntimeError(
                f"[FYERS] Token exchange failed ({resp.status_code}): "
                f"{payload.get('message', '')}".strip()
            )
        self._save_token(payload["access_token"], payload.get("refresh_token", ""))
        self._access_token = payload["access_token"]
        self._ready = True
        return payload["access_token"]

    def login_with_totp(self) -> str:
        """Daily auto-login via the TOTP flow (no manual copy-paste).

        Requires ``FYERS_TOTP_SECRET`` and ``FYERS_PIN`` in the environment.
        Mints an auth_code through the browser session, then exchanges it for a
        fresh access token (FYERS tokens expire end of trading day).
        """
        if not (self.app_id and self.secret and self.pin and self._totp_secret()):
            raise RuntimeError(
                "[FYERS] TOTP login needs FYERS_TOTP_SECRET and FYERS_PIN set in .env."
            )
        auth_code = self._mint_auth_code_via_totp()
        return self.exchange_code_for_token(auth_code, self.redirect_uri or "")

    def _totp_secret(self) -> str:
        return self._totp_secret_value or os.environ.get("FYERS_TOTP_SECRET", "")

    def _mint_auth_code_via_totp(self) -> str:
        import base64

        import pyotp  # optional; only needed for TOTP login

        totp = pyotp.TOTP(self._totp_secret()).now()
        username = self.app_id.split("-")[0]
        s = requests.Session()
        s.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0 (TBMCP)"})
        r1 = s.post(
            f"{FYERS_OTP_HOST}/send_login_otp_v2",
            json={"fy_id": base64.b64encode(username.encode()).decode(), "app_id": "2"},
        )
        r1.raise_for_status()
        request_key = r1.json()["request_key"]
        r2 = s.post(f"{FYERS_OTP_HOST}/verify_otp", json={"request_key": request_key, "otp": totp})
        r2.raise_for_status()
        request_key = r2.json()["request_key"]
        r3 = s.post(
            f"{FYERS_OTP_HOST}/verify_pin_v2",
            json={
                "request_key": request_key,
                "identity_type": "pin",
                "identifier": base64.b64encode(self.pin.encode()).decode(),
            },
        )
        r3.raise_for_status()
        bearer = r3.json()["data"]["access_token"]
        r4 = s.post(
            FYERS_TOKEN_V2_PATH,
            headers={"authorization": f"Bearer {bearer}"},
            json={
                "fyers_id": username,
                "app_id": self.app_id[:-4],
                "redirect_uri": self.redirect_uri or "",
                "appType": "100", "code_challenge": "", "state": "tbmcp",
                "scope": "", "nonce": "", "response_type": "code",
                "create_cookie": True,
            },
        )
        r4.raise_for_status()
        from urllib.parse import parse_qs, urlparse

        url = r4.json()["Url"]
        return parse_qs(urlparse(url).query)["auth_code"][0]

    # -- token lifecycle -------------------------------------------------------
    def _save_token(self, access_token: str, refresh_token: str = "") -> None:
        os.makedirs(_APP_DIR, exist_ok=True)
        existing_refresh = ""
        if os.path.exists(FYERS_TOKEN_FILE):
            try:
                with open(FYERS_TOKEN_FILE, "r", encoding="utf-8") as fh:
                    existing_refresh = json.load(fh).get("refresh_token", "")
            except Exception:
                pass
        with open(FYERS_TOKEN_FILE, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token or existing_refresh,
                    "savedAt": datetime.now(timezone.utc).isoformat(),
                },
                fh,
                indent=2,
            )

    def _load_token(self) -> None:
        if os.path.exists(FYERS_TOKEN_FILE):
            try:
                with open(FYERS_TOKEN_FILE, "r", encoding="utf-8") as fh:
                    self._access_token = json.load(fh).get("access_token", "")
            except Exception:
                pass

    def initialize(self) -> None:
        if not self._access_token:
            self._load_token()
        if not self._access_token:
            raise RuntimeError(
                "[FYERS] Access token missing. Run the login helper:\n"
                "  python -m providers.fyers_login\n"
                "or set FYERS_ACCESS_TOKEN in your .env."
            )
        self._ready = True

    def ensure_initialized(self) -> None:
        if not self._ready:
            self.initialize()

    # -- transport -------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"{self.app_id}:{self._access_token}",
            "Accept": "application/json",
        }

    def _request(self, path: str, params: Optional[dict[str, str]] = None, attempt: int = 1) -> Any:
        self.ensure_initialized()
        url = f"{FYERS_DATA_HOST}{path}"
        if params:
            url += f"?{urlencode(params)}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=PROVIDER_TIMEOUT)
        except requests.RequestException as exc:
            raise RuntimeError(f"[FYERS] Network error: {exc}")
        if resp.status_code in (401, 403):
            if attempt <= AUTH_RETRY_ATTEMPTS and self._refresh():
                return self._request(path, params, attempt + 1)
            raise RuntimeError("[FYERS] Authentication failed (401/403). Re-run login.")
        if not resp.ok:
            raise RuntimeError(f"[FYERS] HTTP {resp.status_code} {resp.reason}: {resp.text[:300]}")
        return resp.json()

    def _refresh(self) -> bool:
        """Best-effort refresh using the stored refresh token (may be unreliable)."""
        if not os.path.exists(FYERS_TOKEN_FILE):
            return False
        try:
            with open(FYERS_TOKEN_FILE, "r", encoding="utf-8") as fh:
                refresh = json.load(fh).get("refresh_token")
        except Exception:
            return False
        if not refresh:
            return False
        body = {
            "grant_type": "refresh_token",
            "appIdHash": _app_id_hash(self.app_id, self.secret),
            "refresh_token": refresh,
        }
        if self.pin:
            body["pin"] = self.pin
        try:
            resp = requests.post(
                f"{FYERS_AUTH_HOST}{VALIDATE_REFRESH_PATH}",
                json=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=PROVIDER_TIMEOUT,
            )
            payload = resp.json() if resp.content else {}
        except requests.RequestException:
            return False
        if payload.get("s") != "ok" or not payload.get("access_token"):
            return False
        self._save_token(payload["access_token"], refresh)
        self._access_token = payload["access_token"]
        return True

    # -- symbol resolution -----------------------------------------------------
    def resolve_key(self, symbol: str) -> str:
        """FYERS symbol form, e.g. ``NSE:NIFTY50-INDEX`` for indices."""
        upper = symbol.strip().upper()
        if upper in FYERS_INDEX_KEYS:
            return FYERS_INDEX_KEYS[upper]
        return f"NSE:{upper}-EQ"

    # -- data: option chain ----------------------------------------------------
    def get_expiry_dates(self, symbol: str) -> list[str]:
        key = self.resolve_key(symbol)
        raw = self._request("/options-chain-v3", {"symbol": key, "strikecount": "1"})
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        return sorted(self._extract_expiries(data))

    def _extract_expiries(self, data: dict) -> list[str]:
        out: list[str] = []
        expiry_data = data.get("expiryData") if isinstance(data, dict) else None
        if isinstance(expiry_data, list):
            for ts in expiry_data:
                if isinstance(ts, (int, float)) and ts > 0:
                    out.append(datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"))
        if not out and isinstance(data, dict):
            for row in data.get("optionsChain", []) or []:
                ts = row.get("expiry") or row.get("expiryDate")
                if isinstance(ts, (int, float)) and ts > 0:
                    out.append(datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"))
        return list(dict.fromkeys(out))

    def get_option_chain(
        self, symbol: str, expiry_date: Optional[str] = None
    ) -> OptionChain:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        if not expiry_date:
            expiries = self.get_expiry_dates(symbol)
            if not expiries:
                raise RuntimeError(f"[FYERS] No option expiries found for '{symbol}'.")
            expiry_date = expiries[0]
        expiry_epoch = int(datetime.strptime(expiry_date, "%Y-%m-%d").timestamp())
        raw = self._request("/options-chain-v3", {
            "symbol": key,
            "strikecount": str(FYERS_STRIKE_COUNT),
            "timestamp": str(expiry_epoch),
            "greeks": "1",
        })
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        rows, underlying, totals = self._parse_chain_rows(data, expiry_date)
        all_expiries = self._extract_expiries(data) or [expiry_date]
        return {
            "symbol": symbol,
            "underlyingValue": underlying,
            "expiryDate": expiry_date,
            "expiryDates": sorted(all_expiries),
            "strikePrices": [r["strikePrice"] for r in rows],
            "rows": rows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "totalCEOpenInterest": totals["ce_oi"],
            "totalPEOpenInterest": totals["pe_oi"],
            "totalCEVolume": totals["ce_vol"],
            "totalPEVolume": totals["pe_vol"],
        }

    def _parse_chain_rows(self, data: dict, expiry_date: str):
        rows: list[OptionChainRow] = []
        totals = {"ce_oi": 0, "pe_oi": 0, "ce_vol": 0, "pe_vol": 0}
        underlying = float(data.get("underlyingValue") or data.get("spot_price") or 0)
        chain = data.get("optionsChain") if isinstance(data, dict) else None
        if not isinstance(chain, list):
            return rows, underlying, totals
        by_strike: dict[float, OptionChainRow] = {}
        for item in chain:
            if not isinstance(item, dict):
                continue
            strike = float(item.get("strike_price") or 0)
            otype = str(item.get("option_type") or item.get("optionType") or "").upper()
            if otype not in ("CE", "PE") or strike <= 0:
                continue
            leg = self._map_leg(item, strike, expiry_date, underlying)
            if leg is None:
                continue
            row = by_strike.get(strike)
            if row is None:
                row = {"strikePrice": strike, "expiryDate": expiry_date}
                by_strike[strike] = row
            row[otype] = leg
            if otype == "CE":
                totals["ce_oi"] += leg["openInterest"]
                totals["ce_vol"] += leg["totalTradedVolume"]
            else:
                totals["pe_oi"] += leg["openInterest"]
                totals["pe_vol"] += leg["totalTradedVolume"]
        rows = [by_strike[s] for s in sorted(by_strike)]
        if underlying == 0 and rows:
            underlying = float(rows[len(rows) // 2].get("CE", {}).get("underlyingValue", 0) or 0)
        return rows, underlying, totals

    def _map_leg(self, item: dict, strike: float, expiry: str, underlying: float) -> Optional[OptionLeg]:
        ltp = float(item.get("ltp") or 0)
        oi = int(float(item.get("oi") or 0))
        prev_oi = int(float(item.get("prev_oi") or item.get("prevOi") or 0))
        oi_change = oi - prev_oi
        volume = int(float(item.get("volume") or 0))
        change = float(item.get("ch") or 0)
        g = item.get("greeks") if isinstance(item.get("greeks"), dict) else {}
        iv = float(g.get("iv") or item.get("iv") or 0)
        return {
            "strikePrice": strike,
            "expiryDate": expiry,
            "optionType": str(item.get("option_type") or "CE").upper(),
            "lastPrice": ltp,
            "change": change,
            "pChange": float(item.get("chp") or 0),
            "openInterest": oi,
            "changeinOpenInterest": oi_change,
            "totalTradedVolume": volume,
            "impliedVolatility": iv,
            "delta": _opt_float(g.get("delta")),
            "gamma": _opt_float(g.get("gamma")),
            "theta": _opt_float(g.get("theta")),
            "vega": _opt_float(g.get("vega")),
            "bidQty": int(float(item.get("bid_qty") or item.get("bidQty") or 0)),
            "bidPrice": float(item.get("bid_price") or item.get("bidPrice") or 0),
            "askQty": int(float(item.get("ask_qty") or item.get("askQty") or 0)),
            "askPrice": float(item.get("ask_price") or item.get("askPrice") or 0),
            "underlyingValue": underlying,
            "oiChangePct": (oi_change / prev_oi * 100) if prev_oi > 0 else 0.0,
            "buildTag": classify_buildup(oi_change, change),
        }

    # -- data: quotes ----------------------------------------------------------
    def _quote_entry(self, raw: Any, key: str) -> Optional[dict[str, float]]:
        if not isinstance(raw, dict):
            return None
        data = raw.get("data", raw)
        entry = None
        if isinstance(data, dict):
            entry = data.get(key) or (list(data.values())[0] if data else None)
        elif isinstance(data, list) and data:
            entry = data[0]
        if not isinstance(entry, dict):
            return None
        ltp = _opt_float(entry.get("ltp"))
        if ltp is None:
            ltp = _opt_float(entry.get("last_price"))
        if ltp is None:
            return None
        return {
            "last_price": ltp,
            "net_change": _opt_float(entry.get("ch")) or 0.0,
            "p_change": _opt_float(entry.get("chp")) or 0.0,
        }

    def get_full_quote(self, symbol: str) -> dict[str, float]:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request("/quotes", {"symbols": key})
        entry = self._quote_entry(raw, key)
        if entry is None:
            raise RuntimeError(f"[FYERS] No quote returned for '{key}'.")
        return entry

    def get_full_quotes(self, symbols: list[str]) -> dict[str, dict]:
        self.ensure_initialized()
        key_for: dict[str, str] = {}
        keys: list[str] = []
        for sym in symbols:
            k = self.resolve_key(sym)
            key_for[sym] = k
            keys.append(k)
        raw = self._request("/quotes", {"symbols": ",".join(keys)})
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        out: dict[str, dict] = {}
        for sym in symbols:
            k = key_for[sym]
            entry = None
            if isinstance(data, dict):
                entry = data.get(k)
            norm = self._quote_entry({"data": entry} if entry else {}, k) if entry else None
            out[sym] = norm if norm is not None else {"error": f"No quote for {sym}"}
        return out

    def get_spot_price(self, symbol: str) -> float:
        q = self.get_full_quote(symbol)
        price = _opt_float(q.get("last_price"))
        if price is None or price <= 0:
            raise RuntimeError(f"[FYERS] No LTP returned for '{symbol}'.")
        return float(price)

    # -- data: market depth ----------------------------------------------------
    def get_market_depth(self, symbol: str) -> MarketDepth:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request("/depth", {"symbol": key, "ohlcv_flag": "1"})
        data = raw.get("data", raw) if isinstance(raw, dict) else {}

        def _map_side(side: Any) -> list[DepthLevel]:
            out: list[DepthLevel] = []
            for lvl in (side or []):
                if isinstance(lvl, dict):
                    out.append({
                        "quantity": int(float(lvl.get("volume") or lvl.get("qty") or 0)),
                        "price": float(lvl.get("price") or 0),
                        "orders": int(float(lvl.get("ord") or lvl.get("orders") or 0)),
                    })
            return out

        return {
            "symbol": symbol,
            "instrumentKey": key,
            "lastPrice": float(data.get("ltp") or 0),
            "totalBuyQuantity": int(float(data.get("totalbuyqty") or 0)),
            "totalSellQuantity": int(float(data.get("totalsellqty") or 0)),
            "buy": _map_side(data.get("bids")),
            "sell": _map_side(data.get("asks")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -- data: historical candles ----------------------------------------------
    _RESOLUTION_MAP = {
        "1minute": "1", "5minute": "5", "15minute": "15",
        "30minute": "30", "60minute": "60", "day": "D", "week": "W", "month": "M",
    }

    def get_historical_data(
        self, symbol: str, interval: str = "day", days: int = 60
    ) -> list[Candle]:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        resolution = self._RESOLUTION_MAP.get(interval, "D")
        to_ts = int(datetime.now().timestamp())
        from_ts = to_ts - days * 86400
        raw = self._request("/history", {
            "symbol": key,
            "resolution": resolution,
            "date_format": "0",
            "range_from": str(from_ts),
            "range_to": str(to_ts),
            "oi_flag": "1",
        })
        data = raw.get("data") if isinstance(raw, dict) else None
        rows = data.get("candles") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return []
        candles: list[Candle] = []
        is_daily = resolution in ("D", "W", "M")
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 5:
                continue
            ts, o, h, l, c = row[0], row[1], row[2], row[3], row[4]
            v = row[5] if len(row) > 5 else 0
            time_val: Any = ts
            if is_daily:
                time_val = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
            candles.append({
                "time": time_val,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            })
        candles.sort(key=lambda c: c["time"])
        return candles

    # -- data: option greeks ---------------------------------------------------
    def get_option_greeks_for_symbol(
        self, symbol: str, expiry_date: Optional[str] = None
    ) -> dict:
        self.ensure_initialized()
        chain = self.get_option_chain(symbol, expiry_date)
        out: dict[str, dict] = {}
        for row in chain.get("rows", []):
            for side in ("CE", "PE"):
                leg = row.get(side)
                if not leg:
                    continue
                opt_symbol = f"{self.resolve_key(symbol).split(':')[-1]}{int(row['strikePrice'])}{side}"
                out[opt_symbol] = {
                    "iv": leg.get("impliedVolatility", 0),
                    "delta": leg.get("delta"),
                    "gamma": leg.get("gamma"),
                    "theta": leg.get("theta"),
                    "vega": leg.get("vega"),
                }
        return out

    def get_option_greeks(self, instrument_keys: list[str]) -> dict:
        self.ensure_initialized()
        if not instrument_keys:
            return {}
        raw = self._request("/quotes", {"symbols": ",".join(instrument_keys)})
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        out: dict[str, dict] = {}
        entries = data.values() if isinstance(data, dict) else (
            data if isinstance(data, list) else [])
        for key, entry in (data.items() if isinstance(data, dict) else []):
            if not isinstance(entry, dict):
                continue
            g = entry.get("greeks") if isinstance(entry.get("greeks"), dict) else {}
            out[key] = {
                "iv": float(g.get("iv") or entry.get("iv") or 0),
                "delta": _opt_float(g.get("delta")),
                "gamma": _opt_float(g.get("gamma")),
                "theta": _opt_float(g.get("theta")),
                "vega": _opt_float(g.get("vega")),
            }
        return out

    # -- unsupported (data-only): raise so the router can fall back ------------
    def _unsupported(self, name: str, *args, **kwargs):
        raise UnsupportedByProvider("fyers", name)

    def get_futures_chain(self, symbol: str, expiry_date: Optional[str] = None):
        return self._unsupported("get_futures_chain")

    def get_margin(self, instruments: list[dict]):
        return self._unsupported("get_margin")

    def get_pcr(self, symbol, expiry, date, bucket_interval=60):
        return self._unsupported("get_pcr")

    def get_max_pain(self, symbol, expiry, date, bucket_interval=60):
        return self._unsupported("get_max_pain")

    def get_oi(self, symbol, expiry, date):
        return self._unsupported("get_oi")

    def get_change_oi(self, symbol, expiry, date, interval=1):
        return self._unsupported("get_change_oi")

    def get_fii(self, data_type="NSE_FO|INDEX_FUTURES", interval="1D"):
        return self._unsupported("get_fii")

    def get_dii(self, data_type="NSE_EQ|CASH", interval="1D"):
        return self._unsupported("get_dii")

    def get_market_status(self, exchange="NSE"):
        return self._unsupported("get_market_status")

    def get_market_holidays(self, date: Optional[str] = None):
        return self._unsupported("get_market_holidays")

    def get_market_timings(self, date: str):
        return self._unsupported("get_market_timings")

    def get_instruments(self, query: str, exchange: str = "NSE"):
        return self._unsupported("get_instruments")

    def get_company_profile(self, isin: str):
        return self._unsupported("get_company_profile")

    def get_share_holdings(self, isin: str):
        return self._unsupported("get_share_holdings")

    def get_key_ratios(self, isin: str):
        return self._unsupported("get_key_ratios")

    def get_corporate_actions(self, isin: str):
        return self._unsupported("get_corporate_actions")

    def get_competitors(self, isin: str):
        return self._unsupported("get_competitors")

    def get_news(self, instrument_keys: list[str]):
        return self._unsupported("get_news")


__all__ = ["FyersClient", "load_fyers_env", "FYERS_TOKEN_FILE"]

