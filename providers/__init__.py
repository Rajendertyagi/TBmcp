"""Provider factory: the single switch point for broker selection.

Everything above (MCP tools, dashboard, analytics) consumes providers through
`create_provider`; nothing reaches a concrete broker class directly.

Selection is **env-driven** (not token-presence driven):

- ``TBMCP_PROVIDER=upstox|fyers`` forces a single provider (legacy mode, keeps
  the "unknown provider raises" contract).
- When ``TBMCP_PROVIDER`` is unset, the active set is built from enable flags:
  ``UPSTOX_ENABLED`` (default **on**, so first run and the default test stay
  green) and ``FYERS_ENABLED`` + credentials. One active provider is returned
  directly; two or more are fronted by an :class:`AffinityRouter` that pins each
  symbol to one broker (per-symbol sticky affinity).

Adding a broker = a new module in ``providers/`` + one registry branch here.
"""
from __future__ import annotations

import os

from config import Settings

from .affinity import AffinityRouter
from .base import DataProvider
from .fyers import FyersClient, load_fyers_env
from .upstox import UpstoxClient


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _build_fyers(settings: Settings) -> FyersClient:
    fe = load_fyers_env()
    return FyersClient(
        app_id=fe["app_id"],
        secret=fe["secret"],
        pin=fe["pin"],
        access_token=fe["access_token"],
        redirect_uri=fe["redirect_uri"],
        totp_secret=fe["totp_secret"],
    )


def create_provider(settings: Settings) -> DataProvider:
    """Return the active data provider selected by env flags / TBMCP_PROVIDER."""
    raw = os.environ.get("TBMCP_PROVIDER")
    if raw and raw.strip():
        name = raw.strip().lower()
        if name == "upstox":
            return UpstoxClient(settings)
        if name == "fyers":
            fe = load_fyers_env()
            if not (fe["app_id"] and fe["secret"]):
                raise ValueError(
                    "FYERS provider selected but FYERS_APP_ID/FYERS_SECRET are missing."
                )
            return _build_fyers(settings)
        raise ValueError(
            f"Unknown data provider '{name}'. Supported providers: upstox, fyers."
        )

    # Enable-flag mode (multi-provider capable).
    upstox_on = _env_bool(os.environ.get("UPSTOX_ENABLED"), True)
    fe = load_fyers_env()
    fyers_on = fe["enabled"] and bool(fe["app_id"] and fe["secret"])

    active: dict[str, DataProvider] = {}
    if upstox_on:
        active["upstox"] = UpstoxClient(settings)
    if fyers_on:
        active["fyers"] = _build_fyers(settings)

    if not active:
        raise ValueError(
            "No data provider is enabled. Set UPSTOX_ENABLED=true (default) or "
            "enable FYERS with FYERS_ENABLED=true plus FYERS_APP_ID/FYERS_SECRET."
        )
    if len(active) == 1:
        return next(iter(active.values()))
    return AffinityRouter(active, primary="upstox")


__all__ = ["create_provider", "DataProvider", "UpstoxClient", "FyersClient", "AffinityRouter"]
