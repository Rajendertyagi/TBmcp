"""Live market data from Upstox: chains, quotes, futures, depth, margin, info.

Pure Upstox data fetching — the buildup analytics live in `analytics`, the output
shape in `models`, and this mixin only maps raw responses into those shapes.
Composed into :class:`UpstoxClient` alongside the other mixins.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional
from urllib.parse import quote

from config import now_iso
from constants import (
    HISTORICAL_CANDLE_PATH,
    INSTRUMENTS_SEARCH_PATH,
    MARGIN_PATH,
    MARKET_CHANGE_OI_PATH,
    MARKET_DII_PATH,
    MARKET_FII_PATH,
    MARKET_HOLIDAYS_PATH,
    MARKET_MAX_PAIN_PATH,
    MARKET_OI_PATH,
    MARKET_PCR_PATH,
    MARKET_QUOTE_LTP_PATH,
    MARKET_QUOTE_QUOTES_PATH,
    MARKET_STATUS_PATH,
    MARKET_TIMINGS_PATH,
    OPTION_CHAIN_PATH,
    OPTION_CONTRACT_PATH,
    UPSTOX_BASE_URL,
    UPSTOX_V3_BASE_URL,
)
from analytics import classify_buildup
from models import (
    Candle,
    DepthLevel,
    FuturesChain,
    FuturesLeg,
    Instrument,
    Margin,
    MarginItem,
    MarketDepth,
    MarketHoliday,
    MarketStatus,
    OptionChain,
    OptionChainRow,
    OptionLeg,
)

from .upstox_parsing import (
    _dump_contract_debug,
    _dump_fullquote_debug,
    _extract_quote_entry,
    _normalize_quote_entry,
    _normalise_candle_time,
    _to_float,
    logger,
)


class UpstoxMarketDataMixin:
    """Market data: option/futures chains, quotes, depth, margin, market info."""

    # -- public data API ------------------------------------------------------
    def get_expiry_dates(self, symbol: str) -> list[str]:
        key = self.resolve_key(symbol)
        logger.debug("[expiry] %s: resolved key=%s", symbol, key)
        raw = self._request(OPTION_CONTRACT_PATH, {"instrument_key": key})
        payload = raw.get("data")
        if isinstance(payload, list):
            expiries = [c.get("expiry") for c in payload if c.get("expiry")]
        elif isinstance(payload, dict) and isinstance(payload.get("expiry"), list):
            expiries = payload["expiry"]
        else:
            expiries = []
        if not expiries:
            logger.debug(
                "[expiry] %s: NO expiries from %s (status=%s)",
                symbol, key, raw.get("status") if isinstance(raw, dict) else "?",
            )
            _dump_contract_debug(symbol, key, raw)
        else:
            logger.debug("[expiry] %s: %s expiries from %s", symbol, len(expiries), key)
        return sorted({e for e in expiries if e})

    def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> OptionChain:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        lot_size = self.get_lot_size(symbol)
        logger.debug("[chain] %s: key=%s lot_size=%s expiry=%s",
                     symbol, key, lot_size, expiry_date or "nearest")
        if not expiry_date:
            # Resolve the nearest expiry up front; we reuse this list below for
            # `expiryDates`, so only the explicit-expiry path fetches it again.
            expiries = self.get_expiry_dates(symbol)
            if not expiries:
                raise RuntimeError(f"[Upstox] No option expiries found for '{symbol}'.")
            expiry_date = expiries[0]
        else:
            expiries = None  # fetched below only if an explicit expiry was requested

        raw = self._request(OPTION_CHAIN_PATH, {"instrument_key": key, "expiry_date": expiry_date})
        payload = raw.get("data")
        items = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
        underlying = items[0].get("underlying_spot_price", 0) if items else 0

        rows: list[OptionChainRow] = []
        totals = {"ce_oi": 0, "pe_oi": 0, "ce_vol": 0, "pe_vol": 0}
        for item in items:
            strike = item.get("strike_price", 0)
            ce = self._map_leg(item.get("call_options"), "CE", strike, expiry_date, underlying, lot_size)
            pe = self._map_leg(item.get("put_options"), "PE", strike, expiry_date, underlying, lot_size)
            row: OptionChainRow = {"strikePrice": strike, "expiryDate": expiry_date}
            if ce:
                row["CE"] = ce
                totals["ce_oi"] += ce["openInterest"]
                totals["ce_vol"] += ce["totalTradedVolume"]
            if pe:
                row["PE"] = pe
                totals["pe_oi"] += pe["openInterest"]
                totals["pe_vol"] += pe["totalTradedVolume"]
            rows.append(row)
        rows.sort(key=lambda r: r["strikePrice"])
        # Only re-fetch the full expiry list when an explicit expiry was requested
        # (the `if not expiry_date` branch above already resolved it).
        if expiries is None:
            expiries = self.get_expiry_dates(symbol)
        return {
            "symbol": symbol,
            "underlyingValue": underlying,
            "expiryDate": expiry_date,
            "expiryDates": expiries,
            "strikePrices": [r["strikePrice"] for r in rows],
            "rows": rows,
            "timestamp": now_iso(),
            "totalCEOpenInterest": totals["ce_oi"],
            "totalPEOpenInterest": totals["pe_oi"],
            "totalCEVolume": totals["ce_vol"],
            "totalPEVolume": totals["pe_vol"],
        }

    def _map_leg(
        self,
        leg: Optional[dict[str, Any]],
        otype: str,
        strike: float,
        expiry: str,
        underlying: float,
        lot_size: int,
    ) -> Optional[OptionLeg]:
        if not leg:
            return None
        md = leg.get("market_data", {}) or {}
        g = leg.get("option_greeks", {}) or {}
        ltp = md.get("ltp", 0) or 0
        prev_close = md.get("close_price", 0) or 0
        change = ltp - prev_close if prev_close > 0 else 0
        p_change = (change / prev_close * 100) if (prev_close > 0 and ltp > 0) else 0
        oi = md.get("oi", 0) or 0
        prev_oi = md.get("prev_oi", 0) or 0
        oi_change = oi - prev_oi
        oi_change_pct = (oi_change / prev_oi * 100) if prev_oi > 0 else 0
        volume_shares = md.get("volume", 0) or 0
        volume_contracts = round(volume_shares / lot_size) if lot_size > 0 else 0
        return {
            "strikePrice": strike,
            "expiryDate": expiry,
            "optionType": otype,
            "lastPrice": ltp,
            "change": change,
            "pChange": p_change,
            "openInterest": oi,
            "changeinOpenInterest": oi_change,
            "totalTradedVolume": volume_contracts,
            "impliedVolatility": g.get("iv", 0) or 0,
            "delta": g.get("delta"),
            "gamma": g.get("gamma"),
            "theta": g.get("theta"),
            "vega": g.get("vega"),
            "bidQty": md.get("bid_qty", 0) or 0,
            "bidPrice": md.get("bid_price", 0) or 0,
            "askQty": md.get("ask_qty", 0) or 0,
            "askPrice": md.get("ask_price", 0) or 0,
            "underlyingValue": underlying,
            "oiChangePct": oi_change_pct,
            "buildTag": classify_buildup(oi_change, change),
        }

    def get_spot_price(self, symbol: str) -> float:
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request(
            MARKET_QUOTE_LTP_PATH, {"instrument_key": key}, base_url=UPSTOX_V3_BASE_URL
        )
        # The V3 LTP response shape is unstable across instruments (indices in
        # particular may omit `last_price` or key the entry differently), so
        # extract defensively and fall back to the full-quote endpoint, which
        # the ticker already uses successfully for indices.
        quote = _extract_quote_entry(raw, key)
        last = None
        if isinstance(quote, dict):
            last = _to_float(quote.get("last_price") or quote.get("lastPrice") or quote.get("ltp"))
        if isinstance(last, (int, float)) and last > 0:
            return float(last)
        try:
            q = self.get_full_quote(symbol)
            last = _to_float(q.get("last_price"))
            if isinstance(last, (int, float)) and last > 0:
                return float(last)
        except Exception:
            pass
        raise RuntimeError(f"[Upstox] No LTP returned for '{key}'.")

    # -- futures, depth, margin, market info ---------------------------------
    def get_futures_chain(self, symbol: str, expiry_date: Optional[str] = None) -> FuturesChain:
        """All futures contracts for `symbol` across expiries, with live quotes.

        The option/contract endpoint only returns CE/PE, so futures are sourced
        from the instruments/search endpoint filtered to the FUT segment, then a
        batched full-quote call fetches live prices/OI. Returns an empty legs list
        if no futures are found for the symbol.
        """
        self.ensure_initialized()
        raw = self._request(INSTRUMENTS_SEARCH_PATH, {
            "query": symbol,
            "segments": "FUT",
            "records": "30",
        })
        data = raw.get("data") if isinstance(raw, dict) else raw
        contracts = data if isinstance(data, list) else []
        futures = [c for c in contracts if str(c.get("instrument_type", "")).upper().startswith("FUT")]
        if expiry_date:
            futures = [c for c in futures if c.get("expiry") == expiry_date]
        keys = [c.get("instrument_key") for c in futures if c.get("instrument_key")]
        quotes: dict[str, Any] = {}
        if keys:
            raw_q = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": ",".join(keys)})
            data_q = raw_q.get("data") if isinstance(raw_q, dict) else None
            if isinstance(data_q, dict):
                for k, v in data_q.items():
                    if isinstance(v, dict):
                        quotes[k] = v
        legs: list[FuturesLeg] = []
        for c in futures:
            k = c.get("instrument_key")
            q = quotes.get(k, {})
            ltp = _to_float(q.get("last_price") or q.get("lastPrice")) or 0
            prev = _to_float(q.get("prev_close") or (q.get("ohlc", {}) or {}).get("close")) or 0
            change = ltp - prev if prev > 0 else 0
            pchg = (change / prev * 100) if prev > 0 else 0
            legs.append({
                "instrumentKey": k,
                "expiryDate": c.get("expiry"),
                "strikePrice": _to_float(c.get("strike_price")) or 0,
                "lastPrice": ltp,
                "change": change,
                "pChange": pchg,
                "openInterest": int(_to_float(q.get("oi") or q.get("open_interest")) or 0),
                "volume": int(_to_float(q.get("volume") or q.get("total_traded_volume")) or 0),
                "lotSize": int(_to_float(c.get("lot_size")) or 0),
            })
        legs.sort(key=lambda l: (l["expiryDate"] or "", l["strikePrice"]))
        expiries = sorted({l["expiryDate"] for l in legs if l["expiryDate"]})
        try:
            underlying = self.get_spot_price(symbol)
        except Exception:
            underlying = 0
        return {
            "symbol": symbol,
            "underlyingValue": underlying,
            "expiryDates": expiries,
            "legs": legs,
            "timestamp": now_iso(),
        }

    def get_market_depth(self, symbol: str) -> MarketDepth:
        """Top-of-book order book (5 bid + 5 ask levels) for `symbol`."""
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": key})
        entry = _extract_quote_entry(raw, key) or {}
        depth = entry.get("depth") or {}

        def _map_side(side: Any) -> list[DepthLevel]:
            out: list[DepthLevel] = []
            for lvl in (side or []):
                if isinstance(lvl, dict):
                    out.append({
                        "quantity": int(_to_float(lvl.get("quantity")) or 0),
                        "price": _to_float(lvl.get("price")) or 0,
                        "orders": int(_to_float(lvl.get("orders") or lvl.get("order_count")) or 0),
                    })
            return out

        return {
            "symbol": symbol,
            "instrumentKey": key,
            "lastPrice": _to_float(entry.get("last_price")) or 0,
            "totalBuyQuantity": int(_to_float(entry.get("total_buy_quantity")) or 0),
            "totalSellQuantity": int(_to_float(entry.get("total_sell_quantity")) or 0),
            "buy": _map_side(depth.get("buy")),
            "sell": _map_side(depth.get("sell")),
            "timestamp": now_iso(),
        }

    def get_margin(self, instruments: list[dict[str, Any]]) -> Margin:
        """Required margin for a basket of instruments (POST /charges/margin).

        `instruments` is a list of {instrument_key, quantity, transaction_type,
        product, price?} dicts (max 20). Returns required/final margin plus a
        per-instrument breakdown.
        """
        self.ensure_initialized()
        raw = self._post(MARGIN_PATH, {"instruments": instruments})
        data = raw.get("data") or {}
        items: list[MarginItem] = []
        for m in data.get("margins", []) or []:
            items.append({
                "spanMargin": _to_float(m.get("span_margin")) or 0,
                "exposureMargin": _to_float(m.get("exposure_margin")) or 0,
                "equityMargin": _to_float(m.get("equity_margin")) or 0,
                "netBuyPremium": _to_float(m.get("net_buy_premium")) or 0,
                "additionalMargin": _to_float(m.get("additional_margin")) or 0,
                "totalMargin": _to_float(m.get("total_margin")) or 0,
                "tenderMargin": _to_float(m.get("tender_margin")) or 0,
            })
        return {
            "requiredMargin": _to_float(data.get("required_margin")) or 0,
            "finalMargin": _to_float(data.get("final_margin")) or 0,
            "margins": items,
        }

    def _market_info(self, path: str, params: dict[str, str]) -> Any:
        """Forward a Market Information request and return its `data` payload."""
        self.ensure_initialized()
        raw = self._request(path, params)
        return raw.get("data") if isinstance(raw, dict) else raw

    def get_pcr(
        self, symbol: str, expiry: str, date: str, bucket_interval: int = 60
    ) -> Any:
        """Put-Call Ratio for an underlying on a given expiry/date (Upstox MI API)."""
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_PCR_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
            "bucket_interval": str(bucket_interval),
        })

    def get_max_pain(
        self, symbol: str, expiry: str, date: str, bucket_interval: int = 60
    ) -> Any:
        """Max Pain strike for an underlying on a given expiry/date (Upstox MI API)."""
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_MAX_PAIN_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
            "bucket_interval": str(bucket_interval),
        })

    def get_oi(self, symbol: str, expiry: str, date: str) -> Any:
        """Open Interest across all strikes for an underlying (Upstox MI API)."""
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_OI_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
        })

    def get_change_oi(self, symbol: str, expiry: str, date: str, interval: int = 1) -> Any:
        """Change in Open Interest per strike over `interval` days (Upstox MI API).

        `interval` is the number of days to look back (the Upstox param is named
        `interval`, not `days`).
        """
        key = self.resolve_key(symbol)
        return self._market_info(MARKET_CHANGE_OI_PATH, {
            "instrument_key": key,
            "expiry": expiry,
            "date": date,
            "interval": str(interval),
        })

    def get_fii(self, data_type: str = "NSE_FO|INDEX_FUTURES", interval: str = "1D") -> Any:
        """Foreign Institutional Investor activity (Upstox MI API).

        `data_type` is a segment such as 'NSE_FO|INDEX_FUTURES' or
        'NSE_FO|STOCK_FUTURES'; `interval` is '1D' or '1M' (NOT 'daily').
        """
        return self._market_info(MARKET_FII_PATH, {
            "data_type": data_type,
            "interval": interval,
        })

    def get_dii(self, data_type: str = "NSE_EQ|CASH", interval: str = "1D") -> Any:
        """Domestic Institutional Investor activity (Upstox MI API).

        `data_type` is a segment such as 'NSE_EQ|CASH' or 'BSE_EQ|CASH';
        `interval` is '1D' or '1M' (NOT 'daily').
        """
        return self._market_info(MARKET_DII_PATH, {
            "data_type": data_type,
            "interval": interval,
        })

    def get_market_status(self, exchange: str = "NSE") -> MarketStatus:
        """Trading status for an exchange (e.g. NSE, BSE, NSE_FO)."""
        self.ensure_initialized()
        raw = self._request(f"{MARKET_STATUS_PATH}/{exchange}")
        data = raw.get("data") if isinstance(raw, dict) else {}
        cas = data.get("cas_eligible_status") or {}
        return {
            "exchange": data.get("exchange", exchange),
            "status": data.get("status"),
            "lastUpdated": data.get("last_updated"),
            "casStatus": cas.get("status"),
            "casLastUpdated": cas.get("last_updated"),
        }

    def get_market_holidays(self, date: Optional[str] = None) -> list[MarketHoliday]:
        """Trading holidays. `date` (yyyy-mm-dd) is optional; omit for the full list."""
        self.ensure_initialized()
        path = MARKET_HOLIDAYS_PATH
        if date:
            path = f"{MARKET_HOLIDAYS_PATH}/{date}"
        raw = self._request(path)
        data = raw.get("data") if isinstance(raw, dict) else raw
        return data if isinstance(data, list) else []

    def get_market_timings(self, date: str) -> Any:
        """Market session timings for a given date (yyyy-mm-dd) — required path param."""
        self.ensure_initialized()
        raw = self._request(f"{MARKET_TIMINGS_PATH}/{date}")
        return raw.get("data") if isinstance(raw, dict) else raw

    def get_instruments(self, query: str, exchange: str = "NSE") -> list[Instrument]:
        """Search tradable instruments by name/symbol."""
        self.ensure_initialized()
        raw = self._request(INSTRUMENTS_SEARCH_PATH, {"query": query, "exchanges": exchange})
        data = raw.get("data") if isinstance(raw, dict) else raw
        return data if isinstance(data, list) else []

    # --- Market quotes ---------------------------------------------------------
    def get_full_quote(self, symbol: str) -> dict[str, float]:
        """Return last price, net change, and percent change for `symbol`.

        Powers the top ticker bar. Uses Upstox's full market-quote endpoint so we
        get `net_change` (vs previous close) directly; percent change is derived
        from it when missing. `symbol` may be an index alias (e.g. NIFTY, INDIAVIX).
        """
        self.ensure_initialized()
        key = self.resolve_key(symbol)
        raw = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": key})
        entry = _extract_quote_entry(raw, key)
        norm = _normalize_quote_entry(entry)
        if norm is None:
            # Diagnostic: capture the raw payload so we can see the real shape.
            _dump_fullquote_debug(symbol, key, raw)
            raise RuntimeError(f"[Upstox] No quote returned for '{key}'.")
        return norm

    def get_full_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Batched full quotes for the ticker bar - one Upstox call for many symbols.

        The full market-quote endpoint accepts up to 500 comma-separated keys, so
        the ticker fetches everything in a single request instead of one per symbol.
        Returns a dict keyed by the original symbol; a symbol with no/invalid quote
        gets {"error": ...} so one bad symbol can't fail the whole batch.
        """
        self.ensure_initialized()
        key_for: dict[str, str] = {}
        keys: list[str] = []
        for sym in symbols:
            k = self.resolve_key(sym)
            key_for[sym] = k
            keys.append(k)
        raw = self._request(MARKET_QUOTE_QUOTES_PATH, {"instrument_key": ",".join(keys)})
        data = raw.get("data") if isinstance(raw, dict) else None
        entries = (
            list(data.values())
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        # Index entries by the fields Upstox may use to identify them, so each symbol
        # maps to its OWN quote. We deliberately avoid the lenient "first object with
        # a price" fallback (used by _extract_quote_entry for single calls) because in
        # a batched response that would grab a neighbouring symbol's data.
        by_token: dict[str, dict] = {}
        by_symbol: dict[str, dict] = {}
        for val in entries:
            if isinstance(val, dict):
                if val.get("instrument_token"):
                    by_token[val["instrument_token"].lower()] = val
                if val.get("symbol"):
                    by_symbol[val["symbol"].lower()] = val
        out: dict[str, dict] = {}
        matched_any = False
        for sym in symbols:
            k = key_for[sym]
            entry = (
                by_token.get(k.lower())
                or by_symbol.get(sym.lower())
                or (data.get(k) if isinstance(data, dict) else None)
                or by_token.get(quote(k, safe="").lower())
            )
            norm = _normalize_quote_entry(entry)
            if norm is not None:
                matched_any = True
            out[sym] = norm if norm is not None else {"error": f"No quote for {sym}"}
        if not matched_any and entries:
            # Diagnostic: capture the raw payload so we can see the real shape.
            _dump_fullquote_debug(",".join(symbols), ",".join(keys), raw)
        return out

    def get_historical_data(self, symbol: str, interval: str = "day", days: int = 60) -> list[Candle]:
        """Fetch OHLC candles for `symbol` from Upstox and return typed Candle list.

        Uses the v2 historical-candle endpoint. Index symbols resolve via INDEX_KEYS
        (verified) or, when unknown, the official Instrument Search API; anything else
        is treated as an equity (NSE_EQ|SYMBOL). `time` is normalised to
        the shape lightweight-charts wants (UNIX seconds for intraday, 'yyyy-mm-dd' for
        daily). Returns [] if no candles are available.
        """
        self.ensure_initialized()
        # Upstox only serves intraday candles (1minute/30minute) for a limited
        # recent window, so cap the look-back to avoid a 400 on long ranges.
        if interval in ("1minute", "30minute") and days > 30:
            days = 30
        key = self.resolve_key(symbol)
        to_date = date.today().isoformat()
        from_date = (date.today() - timedelta(days=days)).isoformat()
        # The key (e.g. "NSE_INDEX|Nifty 50") sits in the URL PATH, so its pipe
        # and space must be percent-encoded - otherwise Upstox rejects it as an
        # "Invalid Instrument key". Query-param calls encode automatically; this one does not.
        path = f"{HISTORICAL_CANDLE_PATH}/{quote(key, safe='')}/{interval}/{to_date}/{from_date}"
        raw = self._request(path)
        payload = raw.get("data") or {}
        rows = payload.get("candles") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []
        candles: list[Candle] = []
        for row in rows:
            # Upstox candle = [epoch_ms, open, high, low, close, volume, (oi)]
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                continue
            ts_ms, o, h, l, c, v = row[0], row[1], row[2], row[3], row[4], row[5]
            candles.append({
                "time": _normalise_candle_time(ts_ms),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            })
        candles.sort(key=lambda c: c["time"])
        return candles
