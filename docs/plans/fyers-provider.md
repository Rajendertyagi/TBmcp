# Plan — FYERS as a secondary data provider

**Status:** implemented on branch `feature/fyers-provider` (docs + code + tests).
**Goal:** add FYERS as a data-only second broker behind the existing
`DataProvider` abstraction, using per-symbol sticky-affinity routing, without
changing the 42 MCP tools, the dashboard, or the analytics.

## What changed

| Area | File(s) | Notes |
|---|---|---|
| Exceptions | `providers/exceptions.py` | `UnsupportedByProvider` — a backend signals "I don't serve this". |
| Template | `providers/example_provider.py` | Copy-paste starter for the next broker (separate, not inherited). |
| FYERS client | `providers/fyers.py` | `FyersClient`: data-only, `requests`-only, token lifecycle, per-provider `resolve_key` (`NSE:NIFTY50-INDEX` form). |
| Login helper | `providers/fyers_login.py` | `python -m providers.fyers_login` — daily TOTP auto-login or manual OAuth code exchange. |
| Router | `providers/affinity.py` | `AffinityRouter`: per-symbol pinning, primary-first fallback, circuit breaker, `resolve_key` special-cased to Upstox format. |
| Registry | `providers/__init__.py` | Env-driven: `TBMCP_PROVIDER` (legacy) or `UPSTOX_ENABLED`/`FYERS_ENABLED` + creds. 1 active → that provider; ≥2 → router. |
| Security | `.gitignore` | Added `.fyers-token.json`. |
| Docs | `docs/decisions/adr-008-*.md`, `docs/architecture.md`, `docs/development/local.md`, `docs/testing/README.md`, `docs/packaging/nuitka.md`, `AGENTS.md` §10/§14 | See ADR-008 and the per-doc updates. |

## Key decisions (approved)

- **Per-symbol stickiness** (affinity key = `symbol`), not `method:symbol` — one
  broker per symbol, no split numbers.
- **FYERS is secondary/opt-in.** `UPSTOX_ENABLED` defaults **on** so first run and
  `test_default_provider_is_upstox` stay green; FYERS only activates with
  `FYERS_ENABLED=true` + `FYERS_APP_ID`/`FYERS_SECRET`.
- **No `BaseProvider`** — `example_provider.py` is the template; brokers stay
  separate so removal is a one-line registry delete.
- **`requests`-only** — the `fyers-apiv3` SDK fails to install on Python 3.13
  (pinned `aiohttp==3.9.3` needs the MSVC toolchain).
- **Daily TOTP login** is the reliable auth path (FYERS tokens expire EOD;
  refresh token unreliable post-SEBI Apr-2026). Token in `.fyers-token.json`
  (gitignored). FYERS reads `FYERS_*` from the portable `.env`; `config.py`
  untouched. The auto-login helper (`python -m providers.fyers_login`) needs
  `FYERS_TOTP_SECRET` (the TOTP seed) **and** `FYERS_PIN` (FYERS requires the
  trading PIN after the TOTP step — this matches the verified FYERS v3 flow; the
  earlier contract wording "FYERS_TOTP / no PIN" was wrong and is superseded
  here). `pyotp` is a hard dependency for the TOTP path.
- **Timeout = 10s** (`FYERS_TIMEOUT`), not 3s — avoids falsely marking a healthy
  Upstox down. Circuit breaker + in-memory affinity retained.
- **`resolve_key`** is per-provider; the router's public `resolve_key` returns the
  Upstox format (the dashboard batch expects it) with a FYERS fallback so
  "Test All" never crashes if one broker is down.
- **FYERS scope:** option chain v3 + built-in Greeks, quotes, depth, history,
  greeks, `resolve_key`. NOT futures/margin/PCR/max-pain/OI/FII-DII/status/
  holidays/timings/instruments/fundamentals/news/auth — those raise
  `UnsupportedByProvider` and fall back to another provider.

## Verification

- `pytest` — 267 offline tests pass (252 existing + 15 new:
  `tests/unit/test_fyers.py`, `tests/integration/test_affinity_router.py`).
- `python -m compileall providers tests` — clean.
- `python main.py --help` — works.
- 42 MCP tool names unchanged (`len(s.mcp.tools.methods) == 42`).
- `git status` must not list `.env` / `.fyers-token.json`.

## Remaining / deferred

- **Phase 2:** share the affinity map between the AI server and the dashboard so
  both assign the same broker to a symbol (today affinity is in-memory per
  process).
- Live FYERS data-shape validation against the real API (the parsers are
  defensive; exact field names may need a tweak once tested with a real token).
- Optional `pyotp` dependency for the TOTP auto-login path (imported lazily;
  the manual OAuth flow needs no extra package).
