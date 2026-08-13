"""Falcon web dashboard - the human-facing side of TBMCP (replaces the old NiceGUI ui.py).

A tiny static single-page app (``frontend/index.html`` + ``frontend/js/app.js``) talks to the
JSON API defined here. Falcon (zero-dependency WSGI framework) routes the requests and
reuses the same ``client`` / ``render`` / ``config`` modules the AI server uses, so the
human view and the AI view never disagree.

Routes are split across two files:
- ``api/app.py`` - WSGI app assembly (this file): helpers, index page, create_app/build_app.
- ``api/routes`` - one Resource class per HTTP endpoint.

Run it with ``python main.py ui`` (which calls :func:`build_app`).
"""
from __future__ import annotations

import logging
import os

import falcon

from config import load_settings
from constants import (
    DEFAULT_UI_HOST,
    DEFAULT_UI_PORT,
)
from providers import create_provider


_HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(_HERE, "..", "frontend")
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")

_log = logging.getLogger(__name__)

# Lazily (re)built so credential changes take effect without a restart.
_client = None


def get_client():
    """Return the active data provider, creating it on first use."""
    global _client
    if _client is None:
        _client = create_provider(load_settings())
    return _client

def rebuild_client():
    """Recreate the provider from the latest settings (after a credential change)."""
    global _client
    _client = create_provider(load_settings())
    return _client

def _json(resp, data, status=falcon.HTTP_200):
    resp.media = data
    resp.status = status

def _safe(fn, *args, **kwargs):
    """Run a client call; return ``{"error": ...}`` instead of raising."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - surface any upstream error to the UI
        return {"error": str(exc)}

class IndexResource:
    def on_get(self, req, resp):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as fh:
                html = fh.read()
        except OSError as exc:
            # Loud failure: surface the absolute path + the underlying error
            # instead of silently serving a "Dashboard not found" placeholder.
            _log.error(
                "Dashboard index file missing or unreadable: %s (%s)",
                os.path.abspath(INDEX_FILE),
                exc,
            )
            raise falcon.HTTPInternalServerError(
                title="Dashboard not found",
                description=(
                    "The dashboard index file could not be loaded: "
                    + os.path.abspath(INDEX_FILE)
                ),
            )
        resp.content_type = "text/html"
        resp.text = html

def create_app() -> falcon.App:
    app = falcon.App()
    # Serve .woff2 with the correct MIME type so browsers accept the bundled
    # web fonts (Falcon's static route keys content-type off this table).
    app.resp_options.static_media_types[".woff2"] = "font/woff2"
    app.add_static_route("/static", STATIC_DIR, downloadable=False)
    app.add_route("/", IndexResource())
    app.add_route("/api/ticker", TickerResource())
    app.add_route("/api/quote", QuoteResource())
    app.add_route("/api/chain", ChainResource())
    app.add_route("/api/expiries", ExpiriesResource())
    app.add_route("/api/history", HistoryResource())
    app.add_route("/api/vix", VixResource())
    app.add_route("/api/test-all", TestAllResource())
    app.add_route("/api/settings", SettingsResource())
    app.add_route("/api/login-url", LoginUrlResource())
    app.add_route("/api/login", LoginResource())
    # One-click (no-copy-paste) login: Upstox redirects the browser here with the code.
    app.add_route("/upstox/callback", CallbackResource())
    # Lets the UI show a "Connected" indicator without exposing the token.
    app.add_route("/api/login-status", LoginStatusResource())
    app.add_route("/api/fundamentals", FundamentalsResource())
    app.add_route("/api/news", NewsResource())
    return app

def build_app(host: str = DEFAULT_UI_HOST, port: int = DEFAULT_UI_PORT, reload: bool = False) -> None:
    """Build the Falcon app and serve it (blocking) on ``host:port``."""
    import waitress

    # Fail loudly at startup if the front-end index is missing, rather than
    # serving a silent "Dashboard not found" page at request time.
    if not os.path.isfile(INDEX_FILE):
        _log.critical(
            "Dashboard index file missing at startup: %s", os.path.abspath(INDEX_FILE)
        )
        raise RuntimeError(
            "Dashboard index file not found: " + os.path.abspath(INDEX_FILE)
        )

    app = create_app()
    url = f"http://{host}:{port}"
    print(f"[RTMCP] Dashboard running at {url}  (Ctrl+C to stop)")
    if reload:
        print("[RTMCP] Note: --reload is ignored by the Falcon server; restart the process to pick up changes.")
    # Bump the thread pool above Waitress's default of 4: the SPA loads many small
    # ES-module files in parallel on each page load, which would otherwise queue.
    waitress.serve(app, host=host, port=port, threads=16)

# Imported last: breaks the app<->routes import cycle (routes import the helpers above).
from .routes import (  # noqa: E402
    CallbackResource,
    ChainResource,
    ExpiriesResource,
    FundamentalsResource,
    HistoryResource,
    LoginResource,
    LoginStatusResource,
    LoginUrlResource,
    NewsResource,
    QuoteResource,
    SettingsResource,
    TestAllResource,
    TickerResource,
    VixResource,
)

__all__ = ["create_app", "build_app"]
