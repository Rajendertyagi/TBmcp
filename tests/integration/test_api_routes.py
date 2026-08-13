"""Falcon API boundary: every route behaves correctly against the provider
protocol — happy paths, error paths (via _safe), and validation (400s) — with
no network and no credentials.
"""
from __future__ import annotations

import pytest

import api.app as app
from tests.integration.conftest import FakeProvider


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """Point every config path at tmp so no test touches the real .env/token."""
    import config as config_mod

    monkeypatch.setattr(config_mod, "PORTABLE_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setattr(config_mod, "ENV_FILE", str(tmp_path / ".env-fallback"))
    monkeypatch.setattr(config_mod, "TOKEN_FILE", str(tmp_path / ".upstox-token.json"))
    monkeypatch.setattr(config_mod, "LEGACY_HOME_CONFIG_DIR", str(tmp_path / "legacy"))
    for var in ("UPSTOX_API_KEY", "UPSTOX_API_SECRET", "UPSTOX_REDIRECT_URI",
                "UPSTOX_ACCESS_TOKEN", "TBMCP_PROVIDER", "UPSTOX_RATE_LIMIT_GAP_MS"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


class TestStaticAndIndex:
    def test_index_served_as_html(self, api_client):
        resp = api_client.simulate_get("/")
        assert resp.status_code == 200
        assert resp.content_type == "text/html"
        assert len(resp.text) > 0


class TestTickerQuoteChainExpiriesHistoryVix:
    def test_ticker_returns_all_three_symbols(self, api_client):
        resp = api_client.simulate_get("/api/ticker")
        assert resp.status_code == 200
        body = resp.json
        assert [q["symbol"] for q in body] == ["NIFTY", "BANKNIFTY", "INDIAVIX"]
        assert all("last_price" in q for q in body)

    def test_quote_returns_fake_quote(self, api_client):
        resp = api_client.simulate_get("/api/quote", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        assert resp.json["last_price"] == 20000.0

    def test_quote_missing_symbol_is_400(self, api_client):
        assert api_client.simulate_get("/api/quote").status_code == 400

    def test_chain_returns_html_and_stats(self, api_client):
        resp = api_client.simulate_get("/api/chain", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        body = resp.json
        assert "tbmcp-table" in body["html"]
        assert body["stats"]["spot"] == 20000.0
        assert body["stats"]["pcr"] == 1.0
        assert body["expiryDate"] == "2025-01-30"
        assert body["expiryDates"] == ["2025-01-30", "2025-02-27"]

    def test_expiries(self, api_client):
        resp = api_client.simulate_get("/api/expiries", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        assert resp.json["expiries"] == ["2025-01-30", "2025-02-27"]

    def test_history_returns_candles(self, api_client):
        resp = api_client.simulate_get("/api/history", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        candles = resp.json["candles"]
        assert len(candles) == 5
        assert all("close" in c for c in candles)

    def test_vix_returns_quote(self, api_client):
        resp = api_client.simulate_get("/api/vix")
        assert resp.status_code == 200
        assert resp.json["last_price"] == 20000.0


class TestSettings:
    def test_get_returns_key_and_redirect_not_secret(self, api_client, isolated_config):
        resp = api_client.simulate_get("/api/settings")
        assert resp.status_code == 200
        assert "api_key" in resp.json
        assert "redirect_uri" in resp.json
        assert "api_secret" not in resp.json  # the secret never leaves the server

    def test_post_saves_and_acknowledges(self, api_client, isolated_config):
        resp = api_client.simulate_post(
            "/api/settings",
            json={"api_key": "k", "api_secret": "s", "redirect_uri": "http://r"},
        )
        assert resp.status_code == 200
        assert resp.json == {"ok": True}
        saved = isolated_config.joinpath(".env").read_text(encoding="utf-8")
        assert 'UPSTOX_API_KEY="k"' in saved
        assert 'UPSTOX_API_SECRET="s"' in saved

    def test_post_missing_secret_is_400(self, api_client, isolated_config):
        resp = api_client.simulate_post("/api/settings", json={"api_key": "k"})
        assert resp.status_code == 400


class TestLogin:
    def test_login_status_connected(self, api_client, monkeypatch, tmp_path):
        token = tmp_path / "t.json"
        token.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("api.routes.auth.resolve_token_read_path", lambda: str(token))
        assert api_client.simulate_get("/api/login-status").json == {"connected": True}

    def test_login_status_disconnected(self, api_client, monkeypatch, tmp_path):
        missing = tmp_path / "nope.json"
        monkeypatch.setattr("api.routes.auth.resolve_token_read_path", lambda: str(missing))
        assert api_client.simulate_get("/api/login-status").json == {"connected": False}

    def test_login_requires_code(self, api_client):
        resp = api_client.simulate_post("/api/login", json={})
        assert resp.status_code == 400

    def test_login_exchanges_code_and_acknowledges(self, api_client, isolated_config):
        resp = api_client.simulate_post(
            "/api/login", json={"code": "abc", "redirect_uri": "http://r"}
        )
        assert resp.status_code == 200
        assert resp.json == {"ok": True}

    def test_login_url_built_from_key(self, api_client, isolated_config):
        resp = api_client.simulate_get("/api/login-url", params={"key": "k"})
        assert resp.status_code == 200
        assert "client_id=k" in resp.json["url"]


class TestFundamentalsNewsGreeks:
    def test_fundamentals_company_profile(self, api_client):
        resp = api_client.simulate_get(
            "/api/fundamentals", params={"symbol": "RELIANCE", "endpoint": "company_profile"}
        )
        assert resp.status_code == 200
        body = resp.json
        assert body["name"] == "Fake Corp"
        assert body["isin"] == "INE000000000"

    def test_fundamentals_missing_params_is_400(self, api_client):
        assert api_client.simulate_get("/api/fundamentals").status_code == 400
        assert api_client.simulate_get(
            "/api/fundamentals", params={"symbol": "RELIANCE"}
        ).status_code == 400

    def test_fundamentals_unknown_endpoint_is_error_json(self, api_client):
        resp = api_client.simulate_get(
            "/api/fundamentals", params={"symbol": "RELIANCE", "endpoint": "bogus"}
        )
        assert resp.status_code == 200
        assert "unknown fundamentals endpoint" in resp.json["error"]

    def test_news_returns_articles(self, api_client):
        resp = api_client.simulate_get("/api/news", params={"symbol": "RELIANCE"})
        assert resp.status_code == 200
        assert resp.json["articles"][0]["headline"] == "test news"

    def test_news_missing_symbol_is_400(self, api_client):
        assert api_client.simulate_get("/api/news").status_code == 400

    def test_greeks_returns_chain_greeks(self, api_client):
        resp = api_client.simulate_get("/api/greeks", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        assert "NSE_FO:NIFTY2540923000CE" in resp.json

    def test_greeks_with_expiry(self, api_client):
        resp = api_client.simulate_get(
            "/api/greeks", params={"symbol": "NIFTY", "expiry": "2025-01-30"}
        )
        assert resp.status_code == 200
        assert resp.json["NSE_FO:NIFTY2540923000CE"]["iv"] == 20.0

    def test_greeks_missing_symbol_is_400(self, api_client):
        assert api_client.simulate_get("/api/greeks").status_code == 400


class TestErrorBoundary:
    """When the provider raises, the API must return JSON errors, not 500s."""

    @pytest.fixture
    def failing_api_client(self, monkeypatch):
        fake = FakeProvider(fail=True)
        monkeypatch.setattr(app, "_client", fake)
        from falcon import testing
        return testing.TestClient(app.create_app())

    def test_ticker_surfaces_error_entries(self, failing_api_client):
        resp = failing_api_client.simulate_get("/api/ticker")
        assert resp.status_code == 200  # _safe turns the raise into error JSON
        body = resp.json
        assert all("error" in q for q in body)
        assert "upstream failure" in body[0]["error"]

    def test_chain_surfaces_error_object(self, failing_api_client):
        resp = failing_api_client.simulate_get("/api/chain", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        assert "error" in resp.json
        assert "upstream failure" in resp.json["error"]

    def test_history_returns_empty_candles_on_error(self, failing_api_client):
        resp = failing_api_client.simulate_get("/api/history", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        assert resp.json["candles"] == []

    def test_fundamentals_surfaces_error_json(self, failing_api_client):
        resp = failing_api_client.simulate_get(
            "/api/fundamentals", params={"symbol": "RELIANCE", "endpoint": "company_profile"}
        )
        assert resp.status_code == 200
        assert "upstream failure" in resp.json["error"]

    def test_news_surfaces_error_json(self, failing_api_client):
        resp = failing_api_client.simulate_get("/api/news", params={"symbol": "RELIANCE"})
        assert resp.status_code == 200
        assert "upstream failure" in resp.json["error"]

    def test_greeks_surfaces_error_json(self, failing_api_client):
        resp = failing_api_client.simulate_get("/api/greeks", params={"symbol": "NIFTY"})
        assert resp.status_code == 200
        assert "upstream failure" in resp.json["error"]
