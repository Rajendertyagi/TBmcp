"""Provider boundary: the factory switch point and the DataProvider contract."""
from __future__ import annotations

from providers import create_provider
from providers.base import DataProvider
from providers.upstox import UpstoxClient
from config import Settings

from tests.integration.conftest import FakeProvider

PROTOCOL_METHODS = [
    "get_option_chain", "get_expiry_dates", "get_spot_price", "get_full_quote",
    "get_full_quotes", "get_historical_data", "get_futures_chain",
    "get_market_depth", "get_margin", "get_pcr", "get_max_pain", "get_oi",
    "get_change_oi", "get_fii", "get_dii", "get_market_status",
    "get_market_holidays", "get_market_timings", "get_instruments",
    "build_login_url", "exchange_code_for_token",
]


class TestCreateProvider:
    def test_default_provider_is_upstox(self, monkeypatch):
        for var in ("UPSTOX_API_KEY", "UPSTOX_API_SECRET", "UPSTOX_ACCESS_TOKEN",
                    "UPSTOX_REDIRECT_URI", "RTMCP_PROVIDER"):
            monkeypatch.delenv(var, raising=False)
        client = create_provider(Settings())
        assert isinstance(client, UpstoxClient)

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("RTMCP_PROVIDER", "bogus-broker")
        try:
            create_provider(Settings())
        except ValueError as exc:
            assert "bogus-broker" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown provider")


class TestDataProviderProtocol:
    def test_protocol_has_21_methods(self):
        methods = [m for m in dir(DataProvider) if not m.startswith("_")]
        assert sorted(methods) == sorted(PROTOCOL_METHODS)
        assert len(methods) == 21

    def test_fake_provider_conforms_to_protocol(self):
        # Structural conformance: the test double must implement every method
        # the app can call, so boundaries tested against it are representative.
        fake = FakeProvider()
        for name in PROTOCOL_METHODS:
            assert callable(getattr(fake, name)), f"FakeProvider missing {name}"
