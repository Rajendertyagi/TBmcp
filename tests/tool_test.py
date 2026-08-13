"""Standalone CLI test harness for the TBMCP Market-Info / analytics batch.

The actual batch logic now lives in :mod:`tools_runner` (a production module
imported by the WebUI too); this file is a thin CLI wrapper so you can still
run the whole battery from a terminal:

    python tests/tool_test.py NIFTY
"""
from __future__ import annotations

import os
import sys

# Allow running as `python tests/tool_test.py` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tools_runner import run_all_tools


if __name__ == "__main__":
    from config import load_settings
    from providers import create_provider

    sym = sys.argv[1] if len(sys.argv) > 1 else "NIFTY"
    client = create_provider(load_settings())
    client.ensure_initialized()
    out = run_all_tools(client, sym)

    ok = sum(1 for r in out["results"].values() if r.get("ok"))
    tot = len(out["results"])
    print(f"Symbol: {out['symbol']}  Expiry: {out['expiry']}  ({ok}/{tot} ok)\n")
    for name, r in out["results"].items():
        status = "OK " if r.get("ok") else "ERR"
        detail = "" if r.get("ok") else " - " + str(r.get("error", ""))
        print(f"  [{status}] {name}{detail}")
    sys.exit(0 if ok == tot else 1)
