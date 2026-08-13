"""HTTP resources (Falcon) for the human dashboard — tbmcp.

Split by responsibility into focused modules (``market``, ``fundamentals``,
``auth``, ``tools``); this package file re-exports every Resource class so
``api.app`` and the tests keep importing from ``api.routes`` unchanged. Each
Resource is a thin endpoint that translates between HTTP and the DataProvider,
sharing the ``_json`` / ``_safe`` / ``get_client`` helpers from ``api.app``.
"""
from __future__ import annotations

from .market import (
    ChainResource,
    ExpiriesResource,
    HistoryResource,
    QuoteResource,
    TickerResource,
    VixResource,
)
from .tools import TestAllResource
from .auth import (
    CallbackResource,
    LoginResource,
    LoginStatusResource,
    LoginUrlResource,
    SettingsResource,
)
from .fundamentals import (
    FundamentalsResource,
    NewsResource,
    OptionGreeksResource,
)

__all__ = [
    'TickerResource',
    'QuoteResource',
    'ChainResource',
    'ExpiriesResource',
    'HistoryResource',
    'VixResource',
    'TestAllResource',
    'SettingsResource',
    'LoginUrlResource',
    'LoginResource',
    'CallbackResource',
    'LoginStatusResource',
    'FundamentalsResource',
    'NewsResource',
    'OptionGreeksResource',
]
