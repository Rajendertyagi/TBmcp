"""Configuration & portable paths for TBMCP.

Mirrors the portable layout used by the TypeScript version: when frozen into a
single .exe (Nuitka) the config folder is the directory holding the exe, so the
whole app can be copied anywhere. When running from source the config also lives
in the app's own folder (next to this file) so the folder stays fully portable
and there is no dependency on the user's home directory.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from constants import (
    DEFAULT_PROVIDER,
    PROVIDER_ENV,
    UPSTOX_API_KEY_ENV,
    UPSTOX_API_SECRET_ENV,
    UPSTOX_REDIRECT_URI_ENV,
    FYERS_APP_ID_ENV,
    FYERS_SECRET_ENV,
    FYERS_PIN_ENV,
    FYERS_TOTP_SECRET_ENV,
    FYERS_REDIRECT_URI_ENV,
    FYERS_ENABLED_ENV,
)

# Portable layout: ALL config lives in the app's own folder (APP_DIR) so the whole
# folder is portable -- copy it anywhere and it works, with no dependency on the
# user's home directory. Same rule whether frozen (Nuitka onefile, exe is the app
# root) or running from source.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = APP_DIR  # token + .env both live in APP_DIR for portability

TOKEN_FILE = os.path.join(CONFIG_DIR, ".upstox-token.json")
ENV_FILE = os.path.join(CONFIG_DIR, ".env")
LEGACY_HOME_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".tbmcp")

PORTABLE_ENV_FILE = os.path.join(APP_DIR, ".env")


def _read_env_file(path: str) -> dict[str, str]:
    """Tiny .env reader (no external dependency). Process env vars always win."""
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


class Settings:
    """Resolved settings: process env wins over the .env file."""

    def __init__(self) -> None:
        merged = {**_read_env_file(_env_file_path()), **dict(os.environ)}
        self.api_key: str = merged.get(UPSTOX_API_KEY_ENV, "")
        self.api_secret: str = merged.get(UPSTOX_API_SECRET_ENV, "")
        self.access_token: str = merged.get("UPSTOX_ACCESS_TOKEN", "")
        self.redirect_uri: str = merged.get(UPSTOX_REDIRECT_URI_ENV, "")
        self.provider: str = merged.get(PROVIDER_ENV, DEFAULT_PROVIDER).strip().lower()
        try:
            self.rate_limit_gap_ms: int = int(merged.get("UPSTOX_RATE_LIMIT_GAP_MS", "250"))
        except ValueError:
            self.rate_limit_gap_ms = 250


def _env_file_path() -> str:
    """Prefer the portable .env next to the app; fall back to the home config dir."""
    return PORTABLE_ENV_FILE if os.path.exists(PORTABLE_ENV_FILE) else ENV_FILE


def load_settings() -> Settings:
    return Settings()


def write_env_file(api_key: str, api_secret: str, redirect_uri: str = "") -> None:
    """Persist Upstox credentials to the portable .env next to the app.

    Preserves any other keys already present in that .env file.
    """
    os.makedirs(APP_DIR, exist_ok=True)
    data = _read_env_file(PORTABLE_ENV_FILE)
    data[UPSTOX_API_KEY_ENV] = api_key
    data[UPSTOX_API_SECRET_ENV] = api_secret
    if redirect_uri:
        data[UPSTOX_REDIRECT_URI_ENV] = redirect_uri
    try:
        with open(PORTABLE_ENV_FILE, "w", encoding="utf-8") as fh:
            for key, val in data.items():
                fh.write(f'{key}="{val}"\n')
    except OSError as exc:
        raise OSError(f"Could not write credentials to {PORTABLE_ENV_FILE}: {exc}") from exc


def write_fyers_env(
    app_id: str,
    secret: str,
    pin: str = "",
    totp_secret: str = "",
    redirect_uri: str = "",
    enabled: bool = True,
) -> None:
    """Persist FYERS credentials to the portable .env next to the app.

    Preserves any other keys already present in that .env file. Saving credentials
    also flips ``FYERS_ENABLED=true`` so the provider becomes active on the next
    rebuild (the dashboard calls :func:`rebuild_client` after a successful save).
    """
    os.makedirs(APP_DIR, exist_ok=True)
    data = _read_env_file(PORTABLE_ENV_FILE)
    data[FYERS_APP_ID_ENV] = app_id
    data[FYERS_SECRET_ENV] = secret
    if pin:
        data[FYERS_PIN_ENV] = pin
    if totp_secret:
        data[FYERS_TOTP_SECRET_ENV] = totp_secret
    if redirect_uri:
        data[FYERS_REDIRECT_URI_ENV] = redirect_uri
    data[FYERS_ENABLED_ENV] = "true" if enabled else "false"
    try:
        with open(PORTABLE_ENV_FILE, "w", encoding="utf-8") as fh:
            for key, val in data.items():
                fh.write(f'{key}="{val}"\n')
    except OSError as exc:
        raise OSError(f"Could not write FYERS credentials to {PORTABLE_ENV_FILE}: {exc}") from exc


def resolve_token_read_path() -> str:
    """Where to READ the token: portable config dir, then legacy ~/.tbmcp, then cwd."""
    if os.path.exists(TOKEN_FILE):
        return TOKEN_FILE
    legacy = os.path.join(LEGACY_HOME_CONFIG_DIR, ".upstox-token.json")
    if legacy != TOKEN_FILE and os.path.exists(legacy):
        return legacy
    cwd = os.path.join(os.getcwd(), ".upstox-token.json")
    return cwd if (cwd != TOKEN_FILE and os.path.exists(cwd)) else TOKEN_FILE


def save_token(access_token: str, refresh_token: str = "") -> None:
    """Persist the token next to the (portable) config dir, keeping any existing refresh token."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    existing_refresh = ""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
                existing_refresh = json.load(fh).get("refresh_token", "")
        except Exception:
            pass
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "access_token": access_token,
                "refresh_token": refresh_token or existing_refresh,
                "savedAt": datetime.now(timezone.utc).isoformat(),
            },
            fh,
            indent=2,
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(ts: str) -> float:
    """Parse an ISO timestamp (with or without timezone) into unix epoch seconds."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()
