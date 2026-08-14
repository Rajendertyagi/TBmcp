"""FYERS settings + login HTTP endpoints (mirrors ``auth.py`` for Upstox).

``FyersSettingsResource`` persists FYERS credentials to the portable ``.env`` and
flips ``FYERS_ENABLED=true`` so the provider becomes active. The login resources
drive both flows the FYERS adapter supports:

- **OAuth code flow** (``/api/fyers-login-url`` -> browser -> ``/fyers/callback``)
  — the direct analogue of Upstox's one-click login.
- **Daily TOTP auto-login** (``/api/fyers-totp-login``) — server-side, no browser
  copy-paste; the dependable path now that FYERS refresh tokens are unreliable.

All share the ``_json`` / ``_safe`` / ``rebuild_client`` / ``_log`` helpers from
:mod:`api.app`. The login endpoints build a dedicated :class:`FyersClient` from
the FYERS env (independent of the active provider / router) so they work whether
FYERS is the primary, secondary, or behind the affinity router.
"""
from __future__ import annotations

import html
import os

import falcon

from config import write_fyers_env
from constants import DEFAULT_FYERS_REDIRECT_URI
from providers.fyers import FyersClient, FYERS_TOKEN_FILE, load_fyers_env

from ..app import _json, _safe, rebuild_client, _log


def _fyers_client() -> FyersClient:
    """A FyersClient built straight from the FYERS env (for login purposes)."""
    env = load_fyers_env()
    return FyersClient(
        app_id=env["app_id"],
        secret=env["secret"],
        pin=env["pin"],
        access_token=env["access_token"],
        redirect_uri=env["redirect_uri"],
        totp_secret=env["totp_secret"],
    )


class FyersSettingsResource:
    def on_get(self, req, resp):
        env = load_fyers_env()
        _json(resp, {"app_id": env["app_id"], "redirect_uri": env["redirect_uri"]})

    def on_post(self, req, resp):
        body = req.media or {}
        app_id = (body.get("app_id") or "").strip()
        secret = (body.get("secret") or "").strip()
        pin = (body.get("pin") or "").strip()
        totp = (body.get("totp_secret") or "").strip()
        redirect = (body.get("redirect_uri") or "").strip() or DEFAULT_FYERS_REDIRECT_URI
        if not app_id or not secret:
            _json(resp, {"error": "app_id and secret are required"}, falcon.HTTP_400)
            return
        try:
            write_fyers_env(app_id, secret, pin, totp, redirect, enabled=True)
        except OSError as exc:
            _json(resp, {"error": f"Save failed: {exc}"}, falcon.HTTP_500)
            return
        rebuild_client()
        _json(resp, {"ok": True})


class FyersLoginUrlResource:
    def on_get(self, req, resp):
        key = (req.get_param("key") or "").strip()
        # Always fall back to the registered redirect URI. It must match the one
        # FYERS bounces the browser back to (/fyers/callback) so the one-click
        # login works and FYERS accepts the exchange.
        redirect = (req.get_param("redirect") or "").strip() or DEFAULT_FYERS_REDIRECT_URI
        if not key:
            _json(resp, {"error": "missing key"}, falcon.HTTP_400)
            return
        try:
            url = FyersClient.build_login_url(key, redirect)
        except Exception as exc:  # noqa: BLE001
            _json(resp, {"error": str(exc)}, falcon.HTTP_500)
            return
        _json(resp, {"url": url})


class FyersLoginResource:
    def on_post(self, req, resp):
        body = req.media or {}
        code = (body.get("code") or "").strip()
        redirect = (body.get("redirect_uri") or "").strip()
        if not code:
            _json(resp, {"error": "missing code"}, falcon.HTTP_400)
            return
        result = _safe(_fyers_client().exchange_code_for_token, code, redirect)
        if isinstance(result, dict) and "error" in result:
            _json(resp, result)
            return
        rebuild_client()
        _json(resp, {"ok": True})


class FyersTotpLoginResource:
    """Server-side daily TOTP login (no browser). Needs FYERS_TOTP_SECRET + PIN."""

    def on_post(self, req, resp):
        try:
            token = _fyers_client().login_with_totp()
        except Exception as exc:  # noqa: BLE001 - surface the real reason to the owner
            _json(resp, {"error": str(exc)}, falcon.HTTP_500)
            return
        rebuild_client()
        _json(resp, {"ok": True, "token_len": len(token or "")})


class FyersCallbackResource:
    """OAuth redirect target that finishes the FYERS login automatically.

    FYERS bounces the browser here with ``?auth_code=...`` after the owner
    authorizes the app. We grab the code, swap it for a token, and show a friendly
    page — so the owner never has to copy-paste the code by hand. Because the
    WebUI already runs on the same host:port registered as the redirect URI, no
    extra server or port is needed.
    """

    def on_get(self, req, resp):
        code = (req.get_param("auth_code") or req.get_param("code") or "").strip()
        upstream_error = (req.get_param("error") or "").strip()
        if upstream_error:
            self._render(
                resp, False,
                "FYERS returned an error: " + upstream_error +
                ". Please retry the login from the app.",
            )
            return
        if not code:
            self._render(
                resp, False,
                "No authorization code was returned. Click &quot;Get Login Link&quot; again "
                "from the app and approve the login at FYERS.",
            )
            return
        try:
            _fyers_client().exchange_code_for_token(code, DEFAULT_FYERS_REDIRECT_URI)
        except Exception as exc:  # noqa: BLE001 - surface the real reason to the owner
            _log.error("FYERS token exchange via callback failed: %s", exc)
            self._render(resp, False, "Login failed: " + str(exc))
            return
        rebuild_client()
        # Success: bounce back into the SPA (it reloads and shows the connected state).
        resp.status = falcon.HTTP_303
        resp.location = "/"
        resp.content_type = "text/html"
        resp.text = (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta http-equiv='refresh' content='3;url=/'>"
            "<title>FYERS login successful</title></head>"
            "<body style='font-family:system-ui,sans-serif;text-align:center;"
            "padding-top:4rem'>"
            "<h2>\u2705 Login successful</h2>"
            "<p>You can close this tab and return to the app. Redirecting you there…</p>"
            "</body></html>"
        )

    @staticmethod
    def _render(resp, ok: bool, message: str) -> None:
        resp.content_type = "text/html"
        resp.status = falcon.HTTP_200
        icon = "\u2705" if ok else "\u26a0\ufe0f"
        resp.text = (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<title>FYERS login</title></head>"
            "<body style='font-family:system-ui,sans-serif;text-align:center;"
            "padding-top:4rem'>"
            f"<h2>{icon}</h2><p>{html.escape(message)}</p>"
            "<p><a href='/'>Return to the app</a></p>"
            "</body></html>"
        )


class FyersLoginStatusResource:
    """Report whether a saved FYERS token exists, so the UI can show Connected."""

    def on_get(self, req, resp):
        connected = os.path.exists(FYERS_TOKEN_FILE)
        _json(resp, {"connected": connected})

