# ADR-003 — DataProvider abstraction

- **Status:** accepted
- **Date:** 2026-08-13

## Context

All market data currently comes from the Upstox broker. If we ever swap or add a
broker/data source, we do not want to touch every MCP tool and every dashboard
page. The tool and UI names are a stable contract and should survive a provider
change.

## Decision

All broker access goes through a **`DataProvider` protocol** (`providers/base.py`,
21 methods). The concrete adapter is `providers/upstox.py` (`UpstoxClient`),
chosen by the `create_provider()` factory in `providers/__init__.py` based on
`TBMCP_PROVIDER` (default `upstox`). A new broker implements the protocol and is
selected via the same factory — nothing else changes.

## Alternatives considered

- **Call the broker directly everywhere** — rejected: any swap would rename
  tools, rewrite routes, and duplicate adapters.
- **Interface without a factory** — rejected: the factory is the single switch
  point; without it nothing selects the adapter.

## Consequences

- Adding a broker = one new module in `providers/` + a factory entry.
- MCP tool names and frontend pages stay identical across brokers.
- The abstraction must not be bypassed "because the current broker is easier to
  call directly" — that is the one hard rule around this boundary.
