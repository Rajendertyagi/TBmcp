"""Provider exceptions shared across broker adapters — tbmcp.

A backend raises :class:`UnsupportedByProvider` for any ``DataProvider`` method
it does not implement (e.g. FYERS is data-only, so it does not serve margin or
fundamentals). The affinity router turns this into a clean "try the next
provider" signal rather than a hard crash.
"""
from __future__ import annotations


class UnsupportedByProvider(Exception):
    """Raised when a concrete backend does not implement a DataProvider method."""

    def __init__(self, provider: str, method: str) -> None:
        self.provider = provider
        self.method = method
        super().__init__(f"[{provider}] does not provide '{method}'.")
