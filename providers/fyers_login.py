"""CLI helper to log in to FYERS and cache the access token — tbmcp.

Run it as a module so imports resolve against the repo root:

    python -m providers.fyers_login

Behaviour:

1. If ``FYERS_TOTP_SECRET`` and ``FYERS_PIN`` are set in ``.env``, it performs a
   fully automatic daily TOTP login (no browser copy-paste) and writes the token
   to ``.fyers-token.json`` next to the app.
2. Otherwise it prints the one-time OAuth URL, you log in in the browser, copy
   the ``auth_code`` from the redirect, paste it back, and the helper exchanges
   it for a token.

FYERS access tokens expire at the end of the trading day, so re-run this each
morning (or automate step 1 via a scheduled task).
"""
from __future__ import annotations

import os
import sys


def _load_env():
    # Mirror providers.fyers path resolution without importing the heavy client
    # until we need it (keeps the helper fast and import-safe).
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(repo_root, ".env")
    data: dict[str, str] = {}
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                data[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    merged = {**data, **dict(os.environ)}
    return {
        "app_id": merged.get("FYERS_APP_ID", ""),
        "secret": merged.get("FYERS_SECRET", ""),
        "pin": merged.get("FYERS_PIN", ""),
        "totp_secret": merged.get("FYERS_TOTP_SECRET", ""),
        "redirect_uri": merged.get("FYERS_REDIRECT_URI", ""),
    }


def main() -> int:
    env = _load_env()
    if not (env["app_id"] and env["secret"]):
        print("[fyers_login] Set FYERS_APP_ID and FYERS_SECRET in your .env first.")
        return 1

    # Import the client lazily (after the env check above).
    from providers.fyers import FyersClient

    client = FyersClient(
        app_id=env["app_id"],
        secret=env["secret"],
        pin=env["pin"],
        redirect_uri=env["redirect_uri"],
    )

    if env["totp_secret"] and env["pin"]:
        print("[fyers_login] FYERS_TOTP_SECRET + FYERS_PIN found — automatic TOTP login...")
        try:
            token = client.login_with_totp()
            print(f"[fyers_login] OK. Token cached ({len(token)} chars).")
            return 0
        except Exception as exc:  # noqa: BLE001 - surface a clear message
            print(f"[fyers_login] TOTP login failed: {exc}")
            print("[fyers_login] Falling back to the manual OAuth flow below.")

    url = FyersClient.build_login_url(env["app_id"], env["redirect_uri"] or "http://127.0.0.1:8888/upstox/callback")
    print("\n[fyers_login] Open this URL in your browser and log in:\n")
    print("  " + url)
    print("\nAfter login you'll be redirected to your redirect URI with ")
    print("'?auth_code=...' in the address bar. Copy that auth_code and paste it here.\n")
    auth_code = input("auth_code: ").strip()
    if not auth_code:
        print("[fyers_login] No auth_code provided; aborting.")
        return 1
    try:
        token = client.exchange_code_for_token(auth_code, env["redirect_uri"] or "")
        print(f"[fyers_login] OK. Token cached ({len(token)} chars).")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[fyers_login] Token exchange failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
