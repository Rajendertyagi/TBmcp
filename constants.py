"""Static configuration constants for TBMCP.

Every magic value (URLs, timeouts, instrument keys, lot sizes, colours, UI
defaults) lives here so nothing is hardcoded at the point of use. Import these
wherever a value is needed.
"""
from __future__ import annotations

from typing import Final

# --- Upstox v2 REST API ------------------------------------------------------
UPSTOX_BASE_URL: Final[str] = "https://api.upstox.com/v2"
# V3 market-quote endpoints (LTP/OHLC/Greeks) live under /v3.
UPSTOX_V3_BASE_URL: Final[str] = "https://api.upstox.com/v3"
UPSTOX_AUTH_SCOPE: Final[str] = "offline-access"
AUTH_DIALOG_PATH: Final[str] = "/login/authorization/dialog"
TOKEN_ENDPOINT: Final[str] = "/login/authorization/token"
OPTION_CHAIN_PATH: Final[str] = "/option/chain"
OPTION_CONTRACT_PATH: Final[str] = "/option/contract"
MARKET_QUOTE_LTP_PATH: Final[str] = "/market-quote/ltp"
# Full quote (last price + net change + OHLC) used by the top ticker bar.
MARKET_QUOTE_QUOTES_PATH: Final[str] = "/market-quote/quotes"
EQUITY_KEY_PREFIX: Final[str] = "NSE_EQ|"
AUTH_SCHEME: Final[str] = "Bearer"

# --- Networking --------------------------------------------------------------
REQUEST_TIMEOUT_SECONDS: Final[int] = 30
DEFAULT_RATE_GAP_SECONDS: Final[float] = 0.25
RATE_LIMIT_BACKOFF_SECONDS: Final[int] = 1
TOKEN_PROACTIVE_REFRESH_AGE_SECONDS: Final[int] = 23 * 60 * 60
AUTH_RETRY_ATTEMPTS: Final[int] = 1

# --- Symbol -> Upstox instrument key (indices) -------------------------------
INDEX_KEYS: Final[dict[str, str]] = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "NIFTY50": "NSE_INDEX|Nifty 50",
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "BANKNIFTY50": "NSE_INDEX|Nifty Bank",
    "NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "FIN NIFTY": "NSE_INDEX|Nifty Fin Service",
    "SENSEX": "BSE_INDEX|SENSEX",
    # India VIX (volatility index). Must be hard-mapped: the Instrument-Search
    # API misses "INDIAVIX" (no space) vs the real trading symbol "INDIA VIX",
    # so without this the resolver falls back to a bogus NSE_EQ|INDIAVIX key and
    # the quote (ticker + VIX page) comes back empty.
    "INDIAVIX": "NSE_INDEX|India VIX",
    "INDIA VIX": "NSE_INDEX|India VIX",
}

# --- Lot sizes (contracts per lot) for volume(shares) -> volume(contracts) ----
INDEX_LOT_SIZES: Final[dict[str, int]] = {
    "NIFTY": 50,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 75,
    "SENSEX": 10,
}

# --- Buildup classification colours ------------------------------------------
BUILDUP_COLORS: Final[dict[str, str]] = {
    "Long Buildup": "#1b8a3b",
    "Short Buildup": "#c0392b",
    "Long Unwinding": "#e67e22",
    "Short Covering": "#2c6fbb",
    "Neutral": "#7f8c8d",
}
NEUTRAL_BUILDUP: Final[str] = "Neutral"

# --- Gain / loss text colours -----------------------------------------------
GAIN_COLOR: Final[str] = "#1b8a3b"
LOSS_COLOR: Final[str] = "#c0392b"

# --- UI defaults -------------------------------------------------------------
DEFAULT_SYMBOL: Final[str] = "NIFTY"
DEFAULT_UI_HOST: Final[str] = "127.0.0.1"
DEFAULT_UI_PORT: Final[int] = 8888
AUTO_REFRESH_INTERVAL_SECONDS: Final[float] = 30.0

# --- Top ticker bar ----------------------------------------------------------
# Indices shown in the live ticker across the top of every page.
TICKER_SYMBOLS: Final[list[str]] = ["NIFTY", "BANKNIFTY", "INDIAVIX"]
TICKER_REFRESH_SECONDS: Final[float] = 10.0

# --- Page navigation ---------------------------------------------------------
# The three switchable dashboard pages and the symbol each one defaults to.
PAGE_SYMBOLS: Final[dict[str, str]] = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "INDIA VIX": "INDIAVIX",
}
VIX_SYMBOL: Final[str] = "INDIAVIX"
VIX_CHART_DAYS: Final[int] = 180

# --- Price charts (lightweight-charts: free, browser-side, fed by our broker) ---
# We use TradingView's open-source `lightweight-charts` library. Unlike the full
# TradingView widget it has NO data feed of its own, so we supply candles fetched
# from Upstox - which is exactly why it works for NSE indices TradingView blocks
# inside third-party embeds. Version is pinned to v4 (stable `addCandlestickSeries` API).
LWC_CDN_URL: Final[str] = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"
LWC_CHART_HEIGHT: Final[int] = 420
LWC_DEFAULT_COLUMNS: Final[int] = 2
LWC_DEFAULT_SYMBOLS: Final[str] = "NIFTY, BANKNIFTY"
LWC_DEFAULT_INTERVAL: Final[str] = "day"
LWC_DEFAULT_DAYS: Final[int] = 60
# Upstox historical-candle interval values exposed in the dashboard dropdown.
# MUST stay within Upstox's accepted set: 1minute, 30minute, day, week, month.
LWC_INTERVAL_OPTIONS: Final[dict[str, str]] = {
    "day": "Daily",
    "1minute": "1 min",
    "30minute": "30 min",
    "week": "Weekly",
    "month": "Monthly",
}
# Upstox v2 historical-candle endpoint path (rest completed with key/interval/dates).
HISTORICAL_CANDLE_PATH: Final[str] = "/historical-candle"

# --- Upstox credential env-var names (single source of truth) ----------------
UPSTOX_API_KEY_ENV: Final[str] = "UPSTOX_API_KEY"
UPSTOX_API_SECRET_ENV: Final[str] = "UPSTOX_API_SECRET"
UPSTOX_REDIRECT_URI_ENV: Final[str] = "UPSTOX_REDIRECT_URI"
# Default redirect URI for the one-time OAuth login. It MUST match a value registered
# in your Upstox app's settings AND line up with the dashboard port you launch on
# (the dashboard defaults to 8888, hence 8888 here). If you launch on another port or
# your Upstox app uses a different URI, change it in the dashboard's "Redirect URI"
# field (it is saved to the .env).
DEFAULT_UPSTOX_REDIRECT_URI: Final[str] = "http://127.0.0.1:8888/upstox/callback"

# --- Market Information APIs (all under /v2/market) ---------------------------
# Params VERIFIED against Upstox docs:
#   pcr / max-pain / oi:        instrument_key, expiry, date[, bucket_interval]
#   change-oi:                  instrument_key, expiry, date, interval (days count)
#   fii:                        data_type (segment e.g. NSE_FO|INDEX_FUTURES), interval (1D|1M)
#   dii:                        data_type (segment e.g. NSE_EQ|CASH), interval (1D|1M)
#   holidays:                   no exchange param; optional /{date} path
#   timings:                    /{date} path (date required)
#   status:                     /{exchange} path
MARKET_MAX_PAIN_PATH: Final[str] = "/market/max-pain"
MARKET_PCR_PATH: Final[str] = "/market/pcr"
MARKET_OI_PATH: Final[str] = "/market/oi"
MARKET_CHANGE_OI_PATH: Final[str] = "/market/change-oi"
MARKET_FII_PATH: Final[str] = "/market/fii"
MARKET_DII_PATH: Final[str] = "/market/dii"
MARKET_HOLIDAYS_PATH: Final[str] = "/market/holidays"
MARKET_TIMINGS_PATH: Final[str] = "/market/timings"
MARKET_STATUS_PATH: Final[str] = "/market/status"  # appended with /{exchange}

# --- Margin (POST /v2/charges/margin) ----------------------------------------
MARGIN_PATH: Final[str] = "/charges/margin"

# --- Instruments search (GET /v2/instruments/search) --------------------------
INSTRUMENTS_SEARCH_PATH: Final[str] = "/instruments/search"

# --- Fundamentals (GET /v2/fundamentals/:isin/<name>) -------------------------
FUNDAMENTALS_BASE_PATH: Final[str] = "/fundamentals"
FUNDAMENTAL_COMPANY_PROFILE: Final[str] = "/profile"
FUNDAMENTAL_SHARE_HOLDINGS: Final[str] = "/share-holdings"
FUNDAMENTAL_KEY_RATIOS: Final[str] = "/key-ratios"
FUNDAMENTAL_CORPORATE_ACTIONS: Final[str] = "/corporate-actions"
FUNDAMENTAL_COMPETITORS: Final[str] = "/competitors"

# --- News (GET /v2/news?category=instrument_keys&instrument_keys=...) ----------
NEWS_PATH: Final[str] = "/news"

# --- Active data provider (single switch point for future brokers) ------------
PROVIDER_ENV: Final[str] = "TBMCP_PROVIDER"
DEFAULT_PROVIDER: Final[str] = "upstox"
