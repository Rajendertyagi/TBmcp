"""Unit tests for the API-layer helpers and pure HTML rendering.

Covers the small helpers in :mod:`api.app` (``_safe`` error boundary, ``_json``
response writer, ``get_client``/``rebuild_client`` lazy client factory) and the
pure rendering module :mod:`api.render` (``render_chain``, ``chain_css``, and
the number/class formatting helpers) — all offline, with no broker.
"""
from __future__ import annotations

import falcon
import pytest

from api import render
from api.app import _json, _safe
from constants import BUILDUP_COLORS

from tests.unit.conftest import make_option_chain


# --- _safe / _json helpers --------------------------------------------------
class TestSafe:
    def test_returns_value_on_success(self):
        assert _safe(lambda: 42) == 42

    def test_returns_error_dict_on_exception(self):
        def boom():
            raise RuntimeError("kaboom")

        assert _safe(boom) == {"error": "kaboom"}

    def test_forwards_arguments(self):
        assert _safe(lambda a, b: a + b, 2, 3) == 5


class _FakeResp:
    """Minimal duck-typed falcon.Response (media + status only)."""

    def __init__(self):
        self.media = None
        self.status = None


class TestJson:
    def test_sets_media_and_default_status(self):
        resp = _FakeResp()
        _json(resp, {"ok": True})
        assert resp.media == {"ok": True}
        assert resp.status == falcon.HTTP_200

    def test_accepts_custom_status(self):
        resp = _FakeResp()
        _json(resp, {"error": "missing"}, falcon.HTTP_400)
        assert resp.media == {"error": "missing"}
        assert resp.status == falcon.HTTP_400


class TestClientFactory:
    def test_get_client_creates_once_and_caches(self, monkeypatch):
        import api.app as app

        stub = object()
        calls = []

        def fake_create(settings):
            calls.append(settings)
            return stub

        monkeypatch.setattr(app, "_client", None)
        monkeypatch.setattr(app, "create_provider", fake_create)
        monkeypatch.setattr(app, "load_settings", lambda: "settings")
        assert app.get_client() is stub
        assert app.get_client() is stub
        assert calls == ["settings"]  # built once, not per request

    def test_get_client_returns_existing_without_rebuilding(self, monkeypatch):
        import api.app as app

        stub = object()
        monkeypatch.setattr(app, "_client", stub)
        monkeypatch.setattr(
            app, "create_provider",
            lambda s: (_ for _ in ()).throw(AssertionError("must not rebuild")),
        )
        assert app.get_client() is stub

    def test_rebuild_client_always_recreates(self, monkeypatch):
        import api.app as app

        old, new = object(), object()
        calls = []

        def fake_create(settings):
            calls.append(settings)
            return new

        monkeypatch.setattr(app, "create_provider", fake_create)
        monkeypatch.setattr(app, "load_settings", lambda: "settings")
        monkeypatch.setattr(app, "_client", old)
        # Rebuild must fetch a fresh client even though one is already cached.
        assert app.rebuild_client() is new
        assert calls == ["settings"]
        assert app.get_client() is new


# --- render._fmt / _change_class -------------------------------------------
class TestFormatting:
    @pytest.mark.parametrize("value,expected", [
        (None, "-"),
        (1234.5, "1,234.50"),
        (20000.0, "20,000.00"),
        (1000, "1,000"),
        ("abc", "abc"),
    ])
    def test_fmt(self, value, expected):
        assert render._fmt(value) == expected

    def test_fmt_decimals(self):
        assert render._fmt(1234.567, 4) == "1,234.5670"

    @pytest.mark.parametrize("value,expected", [
        (1.0, "rtmcp-up"),
        (-1.0, "rtmcp-down"),
        (0.0, "rtmcp-flat"),
    ])
    def test_change_class(self, value, expected):
        assert render._change_class(value) == expected

    def test_pct_cell_marks_positive_change(self):
        cell = render._pct_cell(1.5)
        assert "rtmcp-up" in cell
        assert "1.50%" in cell

    def test_pct_cell_none_is_flat_dash(self):
        cell = render._pct_cell(None)
        assert "rtmcp-flat" in cell
        assert "-%" in cell

    def test_buildup_cell_slugs_the_tag(self):
        cell = render._buildup_cell("Short Buildup")
        assert "rtmcp-build-short-buildup" in cell


# --- render.render_chain ----------------------------------------------------
class TestRenderChain:
    def test_full_chain_has_table_header_and_all_rows(self, chain):
        html = render.render_chain(chain)  # 11 strikes
        assert "rtmcp-table rtmcp-symmetrical" in html
        assert html.count("<tr") == 12  # 1 header + 11 rows
        assert "Strike" in html and "PCR" in html

    def test_strike_and_pcr_are_formatted(self, chain):
        html = render.render_chain(chain)
        assert "20,000" in html                       # ATM strike, grouped
        assert "1.00" in html                         # balanced PCR per row

    def test_buildup_cells_carry_slug_class(self, chain):
        html = render.render_chain(chain)
        assert "rtmcp-build-neutral" in html          # default tag from _leg()

    def test_empty_chain_renders_empty_state(self):
        html = render.render_chain({"rows": []})
        assert "rtmcp-empty-state" in html
        assert "No Data Available" in html

    def test_missing_leg_renders_placeholders(self, chain):
        chain["rows"][0]["CE"] = None
        html = render.render_chain(chain)
        assert "rtmcp-empty" in html


class TestChainCss:
    def test_every_buildup_color_gets_a_rule(self):
        css = render.chain_css()
        for tag in BUILDUP_COLORS:
            slug = tag.strip().lower().replace(" ", "-")
            assert f".rtmcp-build-{slug}" in css

    def test_css_mentions_no_inline_styles(self):
        # The whole point of chain_css: class-driven colours, not inline styles.
        assert "style=" not in render.chain_css()
