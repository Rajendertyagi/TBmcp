"""Unit tests for :mod:`config` — .env parsing, settings resolution, credential
file round-trips. Everything is pointed at tmp_path so the real (gitignored)
.env / .upstox-token.json next to the app are never read or written.
"""
from __future__ import annotations

import json

import pytest

import config as config_mod


@pytest.fixture
def portable_env(tmp_path, monkeypatch):
    """Point config at a throwaway .env and chdir away from the repo."""
    env_path = tmp_path / ".env"
    monkeypatch.setattr(config_mod, "PORTABLE_ENV_FILE", str(env_path))
    monkeypatch.setattr(config_mod, "ENV_FILE", str(tmp_path / ".env-fallback"))
    monkeypatch.setattr(config_mod, "TOKEN_FILE", str(tmp_path / ".upstox-token.json"))
    monkeypatch.setattr(config_mod, "LEGACY_HOME_CONFIG_DIR", str(tmp_path / "legacy"))
    monkeypatch.chdir(tmp_path)
    # Deterministic: clear any real Upstox env vars from the environment.
    for var in ("UPSTOX_API_KEY", "UPSTOX_API_SECRET", "UPSTOX_REDIRECT_URI",
                "UPSTOX_ACCESS_TOKEN", "TBMCP_PROVIDER", "UPSTOX_RATE_LIMIT_GAP_MS"):
        monkeypatch.delenv(var, raising=False)
    return env_path


# --- .env file parsing ------------------------------------------------------
class TestReadEnvFile:
    def test_parses_quoted_unquoted_and_comments(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text(
            'UPSTOX_API_KEY="quoted-key"\n'
            "UPSTOX_API_SECRET=plain-secret\n"
            "# a comment\n"
            "\n"
            "NO_EQUALS_LINE\n"
            'REDIRECT="http://x?y=z"\n',
            encoding="utf-8",
        )
        data = config_mod._read_env_file(str(f))
        assert data["UPSTOX_API_KEY"] == "quoted-key"
        assert data["UPSTOX_API_SECRET"] == "plain-secret"
        assert data["REDIRECT"] == "http://x?y=z"
        assert "NO_EQUALS_LINE" not in data

    def test_missing_file_returns_empty(self, tmp_path):
        assert config_mod._read_env_file(str(tmp_path / "nope")) == {}


# --- Settings resolution ----------------------------------------------------
class TestSettings:
    def test_process_env_wins_over_file(self, portable_env, monkeypatch):
        portable_env.write_text('UPSTOX_API_KEY="file-key"\n', encoding="utf-8")
        monkeypatch.setenv("UPSTOX_API_KEY", "env-key")
        s = config_mod.load_settings()
        assert s.api_key == "env-key"

    def test_reads_from_portable_env_file(self, portable_env):
        portable_env.write_text(
            'UPSTOX_API_KEY="k"\nUPSTOX_API_SECRET="s"\nUPSTOX_REDIRECT_URI="http://r"\n',
            encoding="utf-8",
        )
        s = config_mod.load_settings()
        assert (s.api_key, s.api_secret, s.redirect_uri) == ("k", "s", "http://r")

    def test_default_provider_and_rate_gap(self, portable_env):
        s = config_mod.load_settings()
        assert s.provider == "upstox"
        assert s.rate_limit_gap_ms == 250

    def test_provider_and_rate_override_via_env(self, portable_env, monkeypatch):
        monkeypatch.setenv("TBMCP_PROVIDER", "other")
        monkeypatch.setenv("UPSTOX_RATE_LIMIT_GAP_MS", "999")
        s = config_mod.load_settings()
        assert s.provider == "other"
        assert s.rate_limit_gap_ms == 999

    def test_bad_rate_gap_falls_back(self, portable_env, monkeypatch):
        monkeypatch.setenv("UPSTOX_RATE_LIMIT_GAP_MS", "not-a-number")
        assert config_mod.load_settings().rate_limit_gap_ms == 250


# --- write_env_file ---------------------------------------------------------
class TestWriteEnvFile:
    def test_writes_credentials_and_preserves_other_keys(self, portable_env):
        config_mod.write_env_file("key1", "secret1", "http://redirect")
        config_mod.write_env_file("key2", "secret2")  # no redirect arg
        text = portable_env.read_text(encoding="utf-8")
        assert 'UPSTOX_API_KEY="key2"' in text
        assert 'UPSTOX_API_SECRET="secret2"' in text
        assert 'UPSTOX_REDIRECT_URI="http://redirect"' in text  # preserved

    def test_round_trips_through_settings(self, portable_env):
        config_mod.write_env_file("k", "s", "http://r")
        loaded = config_mod.load_settings()
        assert (loaded.api_key, loaded.api_secret, loaded.redirect_uri) == ("k", "s", "http://r")


# --- save_token / resolve_token_read_path -----------------------------------
class TestTokenPersistence:
    def test_save_and_load_round_trip(self, portable_env):
        config_mod.save_token("access-1", "refresh-1")
        data = json.loads(portable_env.parent.joinpath(".upstox-token.json").read_text(encoding="utf-8"))
        assert data["access_token"] == "access-1"
        assert data["refresh_token"] == "refresh-1"
        assert "savedAt" in data

    def test_save_preserves_refresh_token_when_absent(self, portable_env):
        config_mod.save_token("access-1", "refresh-keep")
        config_mod.save_token("access-2")  # no refresh passed
        data = json.loads(portable_env.parent.joinpath(".upstox-token.json").read_text(encoding="utf-8"))
        assert data["access_token"] == "access-2"
        assert data["refresh_token"] == "refresh-keep"

    def test_resolve_prefers_portable_token_file(self, portable_env):
        config_mod.save_token("a", "r")
        assert config_mod.resolve_token_read_path() == str(
            portable_env.parent / ".upstox-token.json"
        )

    def test_resolve_falls_back_to_legacy_home(self, portable_env):
        legacy = portable_env.parent / "legacy"
        legacy.mkdir()
        (legacy / ".upstox-token.json").write_text("{}", encoding="utf-8")
        assert config_mod.resolve_token_read_path() == str(
            legacy / ".upstox-token.json"
        )

    def test_resolve_with_nothing_returns_token_file(self, portable_env):
        assert config_mod.resolve_token_read_path() == str(
            portable_env.parent / ".upstox-token.json"
        )
