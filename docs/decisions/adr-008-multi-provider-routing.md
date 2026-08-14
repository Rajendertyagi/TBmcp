# ADR-008 — Multi-Provider Routing (FYERS as a secondary data provider)

- **Status:** accepted
- **Date:** 2026-08-14

## Context

TBMCP reads all market data through one `DataProvider` (today: Upstox). We want
to add **FYERS** as a second, **data-only** source — option chain, quotes, depth,
history and option Greeks — without touching the 42 MCP tools, the dashboard, or
the analytics. The broker must be swappable/stackable behind the same protocol.

Two design questions had to be settled:

1. **How is a symbol assigned to a broker?** Mixing two brokers' numbers for the
   *same* symbol (e.g. Upstox OI vs FYERS OI in one chain) is wrong. So routing
   is **per-symbol sticky**: once a symbol is served by a broker, it stays there.
2. **How is FYERS introduced without destabilising the default (Upstox) path?**
   FYERS is a *secondary* — used when Upstox is down or doesn't serve a method —
   and is **opt-in** via env flags, never on by default.

## Decision

- **`providers/fyers.py`** — a self-contained `FyersClient` satisfying the
  `DataProvider` protocol. It implements the data methods (option chain with
  built-in Greeks, quotes, depth, history) **and** derives the F&O analytics
  (PCR, max-pain, OI, change-OI) from its own option chain via the shared
  `analytics` layer, plus exchange market status from FYERS's `marketStatus`
  endpoint (see the addendum below). Methods it still cannot serve (futures
  chain, margin, FII/DII, holidays, timings, instruments, fundamentals, news,
  user-auth) raise `UnsupportedByProvider` so the router can fall back.
- **`providers/affinity.py`** — `AffinityRouter` fronts ≥2 active providers. It
  pins each symbol to the first healthy provider that serves the method
  (primary = Upstox first), fails over on error, and marks a failing provider
  "down" briefly (circuit breaker). `resolve_key` is special-cased to always
  prefer the primary's key format (the dashboard batch expects Upstox keys) and
  never raises.
- **`providers/__init__.py`** — env-driven registry. `TBMCP_PROVIDER=upstox|fyers`
  forces one provider (legacy mode, keeps the "unknown provider raises" contract);
  when unset, the active set comes from `UPSTOX_ENABLED` (default **on**) and
  `FYERS_ENABLED` + credentials. One active → that provider; ≥2 → `AffinityRouter`.
- **No `BaseProvider` / no inheritance.** FYERS is a copy-paste of the
  `example_provider.py` template, kept fully separate so removing it is a one-line
  registry delete (or `FYERS_ENABLED=false`).
- **`requests`-only.** The official `fyers-apiv3` SDK was dropped: its pinned
  `aiohttp==3.9.3` fails to build on Python 3.13 without the MSVC toolchain.
- **Auth = daily.** FYERS tokens expire end of trading day; the refresh token is
  unreliable post-SEBI Apr-2026, so the dependable path is the daily TOTP login
  helper `python -m providers.fyers_login`. Token cached in `.fyers-token.json`
  (gitignored). FYERS reads its own `FYERS_*` env from the portable `.env`;
  `config.py` is intentionally untouched.
- **Affinity is in-memory only** (per session). Sharing it between the AI and the
  dashboard (so both see identical broker assignments) is deferred to Phase 2.

## Alternatives considered

- **Per-method stickiness** (`method:symbol` as the affinity key) — rejected: a
  symbol's chain, quotes and Greeks would then land on different brokers,
  re-introducing split numbers. Per-symbol is the consistency-safe choice.
- **FYERS as primary by default** — rejected: Upstox is the full-feature,
  already-working provider; FYERS is a resilience/secondary layer and must not
  change first-run behaviour or break the `test_default_provider_is_upstox` test.
- **Keep the `fyers-apiv3` SDK** — rejected: it does not install on Python 3.13
  in this environment (MSVC build failure). `requests` covers every endpoint.

## Consequences

- Adding/removing a broker is a registry edit plus (for removal) deleting one
  module — no tool, route, or analytics change.
- The 42-tool contract and the dashboard are unchanged; they only see
  `DataProvider`.
- A symbol's data is internally consistent (one broker) even when two are active.
- FYERS is opt-in; the default experience is unchanged Upstox.
- Phase 2 can add cross-consumer affinity sharing without altering the router's
  external contract.

## Addendum (2026-08-14) — FYERS scope extended to F&O analytics

Initial scope limited FYERS to the raw data methods; PCR/max-pain/OI/change-OI
and market status fell back to Upstox. In practice FYERS's option chain carries
everything needed to compute those analytics, and the shared analytics layer is
broker-agnostic by design, so `FyersClient` now serves them itself:

- `get_pcr` / `get_max_pain` — delegated to `analytics.compute_pcr` /
  `analytics.compute_max_pain` over the FYERS chain.
- `get_oi` / `get_change_oi` — computed from FYERS chain rows.
- `get_market_status` — parsed from FYERS's `/marketStatus` endpoint.

Benefits: fewer fallbacks to Upstox, and FYERS data stays internally consistent
per symbol (analytics derive from the same chain the router pinned). Risk: the
response-shape assumptions (spot entry in the chain, `ltpch/ltpchp/bid/ask`,
`d[].v` quotes, `marketStatus` list) are encoded in unit tests and are validated
against the real API before release.
