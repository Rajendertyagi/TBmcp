"""Provider factory: the single switch point for broker selection.

Everything above (MCP tools, dashboard, analytics) consumes providers through
`create_provider`; nothing reaches a concrete broker class directly.
"""
from __future__ import annotations

from config import Settings
from constants import DEFAULT_PROVIDER

from .base import DataProvider
from .upstox import UpstoxClient


def create_provider(settings: Settings) -> DataProvider:
    """Return the active data provider selected by the RTMCP_PROVIDER setting.

    This is the ONE switch point for the future: a broker swap is a new class
    plus one branch here, not a rewrite of the tools or the UI.
    """
    name = (getattr(settings, "provider", "") or DEFAULT_PROVIDER).strip().lower()
    if name == "upstox":
        return UpstoxClient(settings)
    raise ValueError(
        f"Unknown data provider '{name}'. Supported providers: upstox."
    )

__all__ = ["create_provider", "DataProvider", "UpstoxClient"]
