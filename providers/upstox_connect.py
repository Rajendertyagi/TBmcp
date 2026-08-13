"""Upstox connection layer: OAuth login, token lifecycle, rate-limited transport.

Owns the HTTP edge of the Upstox client — the only place `requests` is touched:
auth headers, the rate-limiting lock, token persistence, and the 401-refresh
retry. Composed into :class:`UpstoxClient` alongside the other mixins.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from config import Settings, parse_iso, resolve_token_read_path, save_token
from constants import (
    AUTH_DIALOG_PATH,
    AUTH_RETRY_ATTEMPTS,
    AUTH_SCHEME,
    DEFAULT_RATE_GAP_SECONDS,
    RATE_LIMIT_BACKOFF_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    TOKEN_ENDPOINT,
    TOKEN_PROACTIVE_REFRESH_AGE_SECONDS,
    UPSTOX_AUTH_SCOPE,
    UPSTOX_BASE_URL,
)

from .upstox_parsing import json_load, logger


class UpstoxConnectMixin:
    """Auth, token lifecycle, and rate-limited HTTP transport for Upstox."""

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
