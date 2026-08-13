"""Data contracts (typed shapes) for RTMCP.

These TypedDicts describe the option-chain data returned by the Upstox client.
Using them gives strong typing end-to-end (no loose `dict`/`Any` in domain code)
while remaining plain dicts at runtime, so `json.dumps` works unchanged.
"""
from __future__ import annotations

from typing import Optional, TypedDict


class OptionLeg(TypedDict):
    """One side (call or put) of a single strike in the option chain."""

    strikePrice: float
    expiryDate: str
    optionType: str
    lastPrice: float
    change: float
    pChange: float
    openInterest: int
    changeinOpenInterest: int
    totalTradedVolume: int
    impliedVolatility: float
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    bidQty: int
    bidPrice: float
    askQty: int
    askPrice: float
    underlyingValue: float
    oiChangePct: float
    buildTag: str


class OptionChainRow(TypedDict, total=False):
    """One strike row: a call leg (CE), a put leg (PE), or both."""

    strikePrice: float
    expiryDate: str
    CE: Optional[OptionLeg]
    PE: Optional[OptionLeg]


class OptionChain(TypedDict):
    """The full option chain for one symbol/expiry."""

    symbol: str
    underlyingValue: float
    expiryDate: str
    expiryDates: list[str]
    strikePrices: list[float]
    rows: list[OptionChainRow]
    timestamp: str
    totalCEOpenInterest: int
    totalPEOpenInterest: int
    totalCEVolume: int
    totalPEVolume: int


class Candle(TypedDict):
    """One OHLC bar.

    `time` is the bar timestamp in the shape lightweight-charts expects:
    - intraday (1minute/30minute): UNIX timestamp in SECONDS (int)
    - daily/weekly/monthly: a 'yyyy-mm-dd' business-day string
    Upstox returns intraday as epoch-ms (number) and daily as an ISO date-time
    string, so the client normalises both before this shape is built.
    """

    time: int | str
    open: float
    high: float
    low: float
    close: float
    volume: float


# --- Futures chain -----------------------------------------------------------
class FuturesLeg(TypedDict):
    """One futures contract row in a futures chain."""

    instrumentKey: str
    expiryDate: str
    strikePrice: float
    lastPrice: float
    change: float
    pChange: float
    openInterest: int
    volume: int
    lotSize: int


class FuturesChain(TypedDict):
    """All futures contracts for one underlying across expiries."""

    symbol: str
    underlyingValue: float
    expiryDates: list[str]
    legs: list[FuturesLeg]
    timestamp: str


# --- Market depth ------------------------------------------------------------
class DepthLevel(TypedDict):
    """One price level in the order book (bid or ask)."""

    quantity: int
    price: float
    orders: int


class MarketDepth(TypedDict):
    """Top-of-book order book for a single instrument."""

    symbol: str
    instrumentKey: str
    lastPrice: float
    totalBuyQuantity: int
    totalSellQuantity: int
    buy: list[DepthLevel]
    sell: list[DepthLevel]
    timestamp: str


# --- Margin ------------------------------------------------------------------
class MarginItem(TypedDict):
    """Per-instrument margin breakdown from the margin engine."""

    spanMargin: float
    exposureMargin: float
    equityMargin: float
    netBuyPremium: float
    additionalMargin: float
    totalMargin: float
    tenderMargin: float


class Margin(TypedDict):
    """Required margin for a basket of instruments."""

    requiredMargin: float
    finalMargin: float
    margins: list[MarginItem]


# --- Market information (raw Upstox responses, passed through) ----------------
class MarketStatus(TypedDict):
    """Exchange trading status."""

    exchange: str
    status: str
    lastUpdated: object
    casStatus: object
    casLastUpdated: object


class MarketHoliday(TypedDict, total=False):
    """A single trading holiday."""

    date: str
    description: str
    trading: bool
    clearing: bool


class Instrument(TypedDict, total=False):
    """A matched instrument from the search endpoint."""

    instrument_key: str
    trading_symbol: str
    name: str
    exchange: str
    instrument_type: str
    segment: str
    lot_size: int


# --- Derived analytics (computed locally over an OptionChain) -----------------
class PcrAnalytics(TypedDict):
    pcr: float
    totalCallOi: int
    totalPutOi: int
    interpretation: str


class MaxPainAnalytics(TypedDict):
    maxPain: float
    underlyingValue: float


class TopOiStrikes(TypedDict):
    topCallOi: list[dict]
    topPutOi: list[dict]


class AtmInfo(TypedDict):
    atmStrike: float
    underlyingValue: float


class IvSkew(TypedDict):
    otmCallAvgIv: float
    otmPutAvgIv: float
    skew: float


class OiBuildup(TypedDict):
    buildupCounts: dict[str, int]
    totalLegs: int


class SupportResistance(TypedDict):
    support: float
    supportOi: int
    resistance: float
    resistanceOi: int


class Straddle(TypedDict):
    atmStrike: float
    straddleCost: float
    upperBreakeven: float
    lowerBreakeven: float


class Gex(TypedDict):
    callGammaExposure: float
    putGammaExposure: float
    netGex: float
    interpretation: str


class FuturesBasis(TypedDict):
    spot: float
    contracts: list[dict]


# --- Strategy pricer output --------------------------------------------------
class StrategyPricing(TypedDict):
    strategy: str
    underlyingValue: float
    atmStrike: float
    netDebit: float
    maxProfit: object
    maxLoss: object
    breakevens: list[float]
    legs: list[dict]


# --- Fundamentals ------------------------------------------------------------
class KeyRatioEntry(TypedDict):
    name: str
    company_value: str
    sector_value: str


class CorporateActionEvent(TypedDict):
    name: str
    value: str


class CorporateAction(TypedDict):
    name: str
    expiry_date: str
    amount: float
    ratio: Optional[str]
    event_details: list[CorporateActionEvent]


class ShareholdingPeriod(TypedDict):
    period: str
    value: float


class ShareholdingCategory(TypedDict):
    category: str
    history: list[ShareholdingPeriod]


class CompetitorProfile(TypedDict):
    instrument_key: str
    company_profile: str
    sector: str
    sector_market_cap_inr: dict
    sector_market_cap_usd: dict


class CompanyProfile(TypedDict):
    company_profile: str
    sector: str
    sector_market_cap_inr: dict
    sector_market_cap_usd: dict


class NewsItem(TypedDict, total=False):
    heading: str
    summary: str
    thumbnail: str
    article_link: str
    published_time: int
