"""Integration tests for the per-symbol sticky-affinity router (offline)."""
from __future__ import annotations

from providers.affinity import AffinityRouter
from providers.exceptions import UnsupportedByProvider


class _Provider:
    def __init__(self, name: str, fail: bool = False, unsupported: set[str] = frozenset()):
        self.name = name
        self.fail = fail
        self.unsupported = set(unsupported)

    def resolve_key(self, symbol: str) -> str:
        return f"{self.name}:{symbol}"

    def get_option_chain(self, symbol, expiry_date=None):
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        if "get_option_chain" in self.unsupported:
            raise UnsupportedByProvider(self.name, "get_option_chain")
        return f"chain:{self.name}"

    def get_margin(self, instruments):
        if "get_margin" in self.unsupported:
            raise UnsupportedByProvider(self.name, "get_margin")
        return f"margin:{self.name}"

    def get_fii(self, *a, **k):
        return f"fii:{self.name}"

    def build_login_url(self, *a, **k):
        return "url"

    def exchange_code_for_token(self, *a, **k):
        return "tok"


class TestAffinityRouter:
    def test_resolve_key_prefers_primary_format(self):
        r = AffinityRouter({"upstox": _Provider("upstox"), "fyers": _Provider("fyers")},
                           primary="upstox")
        assert r.resolve_key("NIFTY") == "upstox:NIFTY"

    def test_symbol_pinned_to_primary_by_default(self):
        r = AffinityRouter({"upstox": _Provider("upstox"), "fyers": _Provider("fyers")},
                           primary="upstox")
        assert r.get_option_chain("NIFTY") == "chain:upstox"
        assert r._affinity == {"NIFTY": "upstox"}

    def test_fallback_to_secondary_when_primary_down(self):
        r = AffinityRouter({"upstox": _Provider("upstox", fail=True),
                            "fyers": _Provider("fyers")}, primary="upstox")
        assert r.get_option_chain("NIFTY") == "chain:fyers"
        assert r._affinity == {"NIFTY": "fyers"}

    def test_unsupported_method_falls_back(self):
        r = AffinityRouter({"upstox": _Provider("upstox"),
                            "fyers": _Provider("fyers", unsupported={"get_margin"})},
                           primary="upstox")
        # margin is not symbol-keyed -> primary (upstox) handles it
        assert r.get_margin([{}]) == "margin:upstox"

    def test_non_symbol_method_uses_primary(self):
        r = AffinityRouter({"upstox": _Provider("upstox"), "fyers": _Provider("fyers")},
                           primary="upstox")
        assert r.get_fii() == "fii:upstox"

    def test_all_providers_down_raises(self):
        r = AffinityRouter({"upstox": _Provider("upstox", fail=True),
                            "fyers": _Provider("fyers", fail=True)}, primary="upstox")
        try:
            r.get_option_chain("NIFTY")
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError when all providers down")
