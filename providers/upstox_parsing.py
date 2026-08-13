"""Raw Upstox response parsing + diagnostic dump helpers — tbmcp.

Shared by every Upstox mixin module (connect, resolution, market data,
fundamentals). This module owns the messy job of turning unstructured Upstox
JSON into clean, typed values (and of capturing raw payloads for debugging), so
the client modules stay focused on what each endpoint means.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any
from urllib.parse import quote


def _to_float(value: object) -> float | None:
    """Coerce numeric values; Upstox sometimes returns numbers as strings."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


# Module-level logger. Diagnostics are emitted at DEBUG and stay silent unless the
# embedding app configures logging to show them - so a packaged build never floods.
# Named "providers.upstox" (not this module's name) so log configuration targeting
# the client keeps working after the mixin split.
logger = logging.getLogger("providers.upstox")


# Module-level guard so the one-time diagnostic dump is written only once per run.
_FULLQUOTE_DUMPED = False


def _debug_dir() -> str:
    """Runtime directory for one-off debug dumps (system temp, never the source tree)."""
    d = os.path.join(tempfile.gettempdir(), "tbmcp_debug")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _dump_fullquote_debug(symbol: str, key: str, raw: object) -> None:
    """Write the raw /market-quote/quotes response to a debug file once.

    Lets us see exactly what Upstox returns when quote extraction fails, instead of
    guessing. Written under the system temp dir (``tbmcp_debug/``) so it never lands
    in the source tree or a packaged build. Best-effort only and never raises.
    """
    global _FULLQUOTE_DUMPED
    if _FULLQUOTE_DUMPED:
        return
    _FULLQUOTE_DUMPED = True
    try:
        path = os.path.join(_debug_dir(), "debug_fullquote.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"symbol": symbol, "key": key, "response": raw}, fh, default=str, indent=2)
    except Exception:
        pass


def _dump_search_debug(symbol: str, raw: object) -> None:
    """Write the raw instrument-search response to a debug file (overwrites).

    Lets us see exactly what Upstox returns for a symbol lookup - e.g. whether the
    equity (instrument_type EQ) row is present and what its instrument_key is - so
    we stop guessing why resolution fails. Written under the system temp dir.
    Best-effort, never raises.
    """
    try:
        path = os.path.join(_debug_dir(), "debug_search.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"symbol": symbol, "response": raw}, fh, default=str, indent=2)
    except Exception:
        pass


def _dump_contract_debug(symbol: str, key: str, raw: object) -> None:
    """Write the raw /option/contract response to a debug file when empty.

    Shows what Upstox returns for the resolved key so we can tell a bad key apart
    from a genuinely empty contract list. Written under the system temp dir.
    Best-effort, never raises.
    """
    try:
        path = os.path.join(_debug_dir(), "debug_contract.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"symbol": symbol, "key": key, "response": raw}, fh, default=str, indent=2)
    except Exception:
        pass


def _extract_quote_entry(raw: dict[str, Any], key: str) -> dict[str, Any] | None:
    """Find the quote object inside an Upstox /market-quote/quotes response.

    The endpoint is shape-unstable across keys/versions: `data` may be a dict keyed
    by the decoded instrument key, by the URL-encoded key, or be a list of quotes.
    We try the documented shapes first, then fall back to a structural search for the
    first object that carries a price so we never silently miss a valid quote.
    """
    data = raw.get("data")
    if isinstance(data, dict):
        # 1. exact decoded key, then URL-encoded key
        entry = data.get(key) or data.get(quote(key, safe=""))
        if isinstance(entry, dict):
            return entry
        # 2. a value whose own instrument_key matches
        for value in data.values():
            if isinstance(value, dict) and value.get("instrument_key") == key:
                return value
        # 3. structural fallback: first object that carries a last price
        for value in data.values():
            if isinstance(value, dict) and ("last_price" in value or "lastPrice" in value):
                return value
        # 4. `data` itself is the quote (single-instrument responses sometimes omit the key wrapper)
        if "last_price" in data or "lastPrice" in data:
            return data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and (
                item.get("instrument_key") == key
                or "last_price" in item
                or "lastPrice" in item
            ):
                return item
    return None


def _normalize_quote_entry(entry: dict[str, Any] | None) -> dict[str, float] | None:
    """Turn a raw Upstox quote object into {last_price, net_change, p_change}.

    Returns None when there is no usable price (so callers can flag an error
    instead of surfacing a bogus zero). Accepts Upstox's common field variants.
    """
    if not isinstance(entry, dict):
        return None
    last = _to_float(entry.get("last_price") or entry.get("lastPrice"))
    if last is None or last <= 0:
        return None
    raw_change = _to_float(entry.get("net_change") or entry.get("change"))
    ohlc_raw = entry.get("ohlc") or entry
    ohlc = ohlc_raw if isinstance(ohlc_raw, dict) else {}
    prev_close = (
        _to_float(ohlc.get("close"))
        or _to_float(entry.get("prev_close"))
        or 0.0
    )
    if raw_change is not None:
        net_change = raw_change
    elif prev_close > 0:
        net_change = last - prev_close
    else:
        net_change = 0.0
    p_change = (net_change / prev_close * 100) if (prev_close > 0) else 0.0
    return {
        "last_price": last,
        "net_change": net_change,
        "p_change": p_change,
    }


def _normalise_candle_time(ts: object) -> "int | str":
    """Convert an Upstox candle timestamp to the shape lightweight-charts wants.

    Upstox returns two different shapes depending on the interval:
    - intraday (1minute/30minute): epoch milliseconds (int/float)
    - daily/weekly/monthly: an ISO date-time string e.g. '2026-08-11T00:00:00+05:30'
    lightweight-charts wants intraday as a UNIX timestamp in SECONDS and daily data
    as a 'yyyy-mm-dd' business-day string (its recommended daily format, which also
    avoids any timezone off-by-one). Mixed/unknown shapes raise.
    """
    if isinstance(ts, (int, float)):
        value = float(ts)
        if value > 1e12:  # epoch milliseconds -> seconds
            value /= 1000.0
        return int(value)
    if isinstance(ts, str):
        s = ts.strip()
        if "T" in s:  # full ISO date-time -> take the calendar date portion
            return s.split("T", 1)[0]
        return s  # already a 'yyyy-mm-dd' date string
    raise ValueError(f"Unrecognised candle timestamp: {ts!r}")


def json_load(fh) -> dict[str, Any]:
    """Minimal JSON loader returning an empty-ish dict on parse failure."""
    try:
        return json.load(fh)
    except Exception:
        return {}
