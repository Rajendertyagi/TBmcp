"""Boundary test for the shared "Test All" batch runner
(:func:`services.tools_runner.run_all_tools`) — the same code the WebUI's
Tools page calls. Exercises success, upstream failure, and missing-expiry
skipping against the fake provider.
"""
from __future__ import annotations

from services.tools_runner import run_all_tools

from tests.integration.conftest import FakeProvider

# Happy-path result count: 1 futures_chain + 11 raw tools + option_chain +
# 4 expiry-dependent raw tools + 10 compute_* + 6 price_* + margin +
# 6 fundamentals + option_greeks = 41.
HAPPY_PATH_RESULT_COUNT = 41


class TestRunAllToolsHappyPath:
    def test_every_tool_succeeds(self, fake_provider, monkeypatch):
        monkeypatch.setattr("services.tools_runner.TEST_ALL_GAP_SECONDS", 0.0)
        out = run_all_tools(fake_provider, "NIFTY")
        assert out["symbol"] == "NIFTY"
        assert out["expiry"] == "2025-01-30"
        assert len(out["results"]) == HAPPY_PATH_RESULT_COUNT
        failed = {k: v for k, v in out["results"].items() if not v.get("ok")}
        assert not failed, f"unexpected failures: {failed}"


class TestRunAllToolsUpstreamFailure:
    def test_failures_are_recorded_not_raised(self, monkeypatch):
        monkeypatch.setattr("services.tools_runner.TEST_ALL_GAP_SECONDS", 0.0)
        out = run_all_tools(FakeProvider(fail=True), "NIFTY")
        # The batch must return a dict, never raise.
        assert out["results"]
        raw_failures = [
            v for k, v in out["results"].items()
            if v.get("ok") is False and "error" in v
        ]
        assert raw_failures
        # The upstream failure text is surfaced for the UI.
        assert any("upstream failure" in v.get("error", "") for v in raw_failures)


class TestRunAllToolsNoExpiry:
    def test_expiry_dependent_tools_are_skipped(self, monkeypatch):
        monkeypatch.setattr("services.tools_runner.TEST_ALL_GAP_SECONDS", 0.0)
        out = run_all_tools(FakeProvider(empty_expiries=True), "NIFTY")
        assert out["expiry"] is None
        # Raw tools that need an expiry are skipped with that reason...
        for name in ("option_chain", "pcr", "max_pain", "oi", "change_oi"):
            entry = out["results"][name]
            assert entry["ok"] is False
            assert "no option expiry" in entry["error"]
        # ...while chain-dependent analytics/pricers skip for lack of a chain.
        for name in ("compute_pcr", "price_long_straddle"):
            entry = out["results"][name]
            assert entry["ok"] is False
            assert "no option chain" in entry["error"]
