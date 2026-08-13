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

## Response conventions

- Client calls are wrapped by `_safe()`: a failure returns `{"error": "..."}`
  with HTTP 200 rather than raising, so the UI always receives JSON.
- Query params are optional unless marked required; missing required params
  return `400 {"error": "..."}`.
- The frontend's only entry point to this API is `frontend/js/api.js` — pages
  never call `fetch()` directly.
