"""Settings + Upstox OAuth login HTTP endpoints.

SettingsResource persists credentials to the local ``.env``; the login resources
drive the one-click OAuth flow (login URL -> code exchange -> callback redirect).
All share the ``_json`` / ``_safe`` / ``get_client`` / ``rebuild_client`` / ``_log``
helpers from :mod:`api.app`.
"""
from __future__ import annotations

import os

import falcon

from config import load_settings, write_env_file, resolve_token_read_path
from constants import DEFAULT_UPSTOX_REDIRECT_URI

from ..app import _json, _safe, get_client, rebuild_client, _log


class SettingsResource:
    def on_get(self, req, resp):
        s = load_settings()
        _json(resp, {"api_key": s.api_key, "redirect_uri": s.redirect_uri})

    def on_post(self, req, resp):
        body = req.media or {}
        key = (body.get("api_key") or "").strip()
        secret = (body.get("api_secret") or "").strip()
        redirect = (body.get("redirect_uri") or "").strip()
        if not key or not secret:
            _json(resp, {"error": "api_key and api_secret are required"}, falcon.HTTP_400)
            return
        try:
            write_env_file(key, secret, redirect)
        except OSError as exc:
            _json(resp, {"error": f"Save failed: {exc}"}, falcon.HTTP_500)
            return
        rebuild_client()
        _json(resp, {"ok": True})

class LoginUrlResource:
    def on_get(self, req, resp):
        key = (req.get_param("key") or "").strip()
        # Always fall back to the registered redirect URI. It must match the one
        # Upstox bounces the browser back to (/upstox/callback) so the one-click
        # (no-copy-paste) login works and Upstox accepts the exchange.
        redirect = (req.get_param("redirect") or "").strip() or DEFAULT_UPSTOX_REDIRECT_URI
        if not key:
            _json(resp, {"error": "missing key"}, falcon.HTTP_400)
            return
        try:
            url = get_client().build_login_url(key, redirect)
        except Exception as exc:  # noqa: BLE001
            _json(resp, {"error": str(exc)}, falcon.HTTP_500)
            return
        _json(resp, {"url": url})

class LoginResource:
    def on_post(self, req, resp):
        body = req.media or {}
        code = (body.get("code") or "").strip()
        redirect = (body.get("redirect_uri") or "").strip()
        if not code:
            _json(resp, {"error": "missing code"}, falcon.HTTP_400)
            return
        result = _safe(get_client().exchange_code_for_token, code, redirect)
        if isinstance(result, dict) and "error" in result:
            _json(resp, result)
            return
        rebuild_client()
        _json(resp, {"ok": True})

class CallbackResource:
    """OAuth redirect target that finishes the Upstox login automatically.

    Upstox bounces the browser here with ``?code=...`` after the owner authorizes
    the app. We grab the code, swap it for a token, and show a friendly page — so
    the owner never has to copy-paste the code by hand. Because the WebUI already
    runs on the same host:port registered as the redirect URI, no extra server or
    port is needed.
    """

    def on_get(self, req, resp):
        code = (req.get_param("code") or "").strip()
        upstream_error = (req.get_param("error") or "").strip()
        if upstream_error:
            self._render(
                resp, False,
                "Upstox returned an error: " + upstream_error +
                ". Please retry the login from the app.",
            )
            return
        if not code:
            self._render(
                resp, False,
                "No authorization code was returned. Click &quot;Get Login Link&quot; again "
                "from the app and approve the login at Upstox.",
            )
            return
        try:
            get_client().exchange_code_for_token(code, DEFAULT_UPSTOX_REDIRECT_URI)
        except Exception as exc:  # noqa: BLE001 - surface the real reason to the owner
            _log.error("Upstox token exchange via callback failed: %s", exc)
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
            "<title>Upstox login successful</title></head>"
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
            "<title>Upstox login</title></head>"
            "<body style='font-family:system-ui,sans-serif;text-align:center;"
            "padding-top:4rem'>"
            f"<h2>{icon}</h2><p>{message}</p>"
            "<p><a href='/'>Return to the app</a></p>"
            "</body></html>"
        )

class LoginStatusResource:
    """Report whether a saved Upstox token exists, so the UI can show Connected."""

    def on_get(self, req, resp):
        connected = os.path.exists(resolve_token_read_path())
        _json(resp, {"connected": connected})
