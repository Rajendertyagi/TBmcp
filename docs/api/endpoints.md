# API — HTTP Endpoints

The human dashboard is a Falcon app (`api/app.py`) with one Resource class per
endpoint (`api/routes/`). All JSON responses are served by the dashboard; the
frontend talks to these endpoints through `frontend/js/api.js`.

Base URL: `http://127.0.0.1:8888` (default; `--host`/`--port` override).

## Static & index

| Method | Path | Description |
|---|---|---|
| GET | `/` | Serves `frontend/index.html` (the SPA shell). |
| GET | `/static/*` | Static files from `frontend/` (JS modules, CSS, fonts, bundled lightweight-charts). |

## Market data

| Method | Path | Params | Response |
|---|---|---|---|
| GET | `/api/ticker` | — | Array of full quotes for the ticker symbols (`NIFTY`, `BANKNIFTY`, `INDIAVIX`), one object per symbol (with `symbol` set). Errors are returned per-symbol as `{"symbol", "error"}`. |
| GET | `/api/quote` | `symbol` (required) | Full quote object for one symbol. Missing symbol → 400 `{"error": "missing symbol"}`. |
| GET | `/api/chain` | `symbol` (required), `expiry` (optional) | Rendered chain: `{html, css, stats: {spot, pcr, ceOi, peOi}, expiryDates, expiryDate, timestamp}`. |
| GET | `/api/expiries` | `symbol` (required) | `{"expiries": [...]}` expiry dates for a symbol. |
| GET | `/api/history` | `symbol` (required), `interval` (default `day`), `days` (default `60`) | `{"candles": [...]}` historical candles. |
| GET | `/api/vix` | — | Full quote for the India VIX index. |
| GET | `/api/test-all` | `symbol` (default `NIFTY`) | Runs every tool once; returns the full batch from `services.tools_runner.run_all_tools`. |
| GET | `/api/fundamentals` | `symbol` (required), `endpoint` (required: `company_profile` \| `share_holdings` \| `key_ratios` \| `corporate_actions` \| `competitors`) | Single fundamentals endpoint for a stock by ISIN. Missing params → 400. |
| GET | `/api/news` | `symbol` (required) | News articles for a symbol (past 7 days). |
| GET | `/api/greeks` | `symbol` (required), `expiry` (optional) | Live option Greeks (IV, delta, gamma, theta, vega) for all strikes in the chain. |

## Settings & Upstox login

| Method | Path | Params / body | Response |
|---|---|---|---|
| GET | `/api/settings` | — | `{"api_key", "redirect_uri"}`. |
| POST | `/api/settings` | JSON `{"api_key", "api_secret", "redirect_uri"}` | `{"ok": true}`; recreates the client from new credentials. Missing key/secret → 400. |
| GET | `/api/login-url` | `key` (required), `redirect` (optional, falls back to `DEFAULT_UPSTOX_REDIRECT_URI`) | `{"url": <Upstox authorization URL>}`. |
| POST | `/api/login` | JSON `{"code", "redirect_uri"}` | `{"ok": true}` after exchanging the auth code for a token; recreates the client. |
| GET | `/api/login-status` | — | `{"connected": true/false}` — whether a saved Upstox token exists (never exposes the token itself). |
| GET | `/upstox/callback` | `code` (Upstox redirects here after the owner authorizes), `error` | Finishes the OAuth login automatically and redirects back to `/` with a success page. |

## FYERS settings & login

FYERS is a **data-only secondary provider**. Its dashboard login mirrors Upstox's
but supports two flows: the OAuth code flow (one-click, like Upstox) and a
**daily TOTP auto-login** (server-side, no browser) — the dependable path now
that FYERS refresh tokens are unreliable. Saving credentials also flips
`FYERS_ENABLED=true` so the provider becomes active.

| Method | Path | Params / body | Response |
|---|---|---|---|
| GET | `/api/fyers-settings` | — | `{"app_id", "redirect_uri"}` (secret/pin/totp never leave the server). |
| POST | `/api/fyers-settings` | JSON `{"app_id", "secret", "pin", "totp_secret", "redirect_uri"}` | `{"ok": true}`; persists creds and enables FYERS. Missing app_id/secret → 400. |
| GET | `/api/fyers-login-url` | `key` (required), `redirect` (optional, falls back to `DEFAULT_FYERS_REDIRECT_URI`) | `{"url": <FYERS authorization URL>}`. |
| POST | `/api/fyers-login` | JSON `{"code", "redirect_uri"}` | `{"ok": true}` after exchanging the auth code for a token; recreates the client. |
| POST | `/api/fyers-totp-login` | — (body ignored) | `{"ok": true, "token_len": N}` after the server-side daily TOTP login; recreates the client. Needs `FYERS_TOTP_SECRET` + `FYERS_PIN` in saved settings. |
| GET | `/api/fyers-login-status` | — | `{"connected": true/false}` — whether a saved FYERS token exists. |
| GET | `/fyers/callback` | `auth_code` (FYERS redirects here after the owner authorizes), `error` | Finishes the OAuth login automatically and redirects back to `/` with a success page. |

## Response conventions

- Client calls are wrapped by `_safe()`: a failure returns `{"error": "..."}`
  with HTTP 200 rather than raising, so the UI always receives JSON.
- Query params are optional unless marked required; missing required params
  return `400 {"error": "..."}`.
- The frontend's only entry point to this API is `frontend/js/api.js` — pages
  never call `fetch()` directly.
