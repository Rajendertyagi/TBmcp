"""Test-all batch endpoint for the dashboard Tools page.

Thin wrapper around :func:`tools_runner.run_all_tools` so the Web UI can verify
every endpoint in a single click. The full batch logic lives in ``tools_runner.py``
(a production module, not ``tests/``), so the application never needs the
``tests/`` package to start.
"""
from __future__ import annotations

import falcon

from services.tools_runner import run_all_tools

from ..app import _json, get_client


class TestAllResource:
    """Run every Market-Info / analytics tool once and return all results."""

    def on_get(self, req, resp):
        sym = (req.get_param("symbol") or "NIFTY").strip().upper()
        _json(resp, run_all_tools(get_client(), sym))
