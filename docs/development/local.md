# Local Development

## Requirements

- **Python >= 3.11** (the repo pins **3.13** via `.python-version`; CI tests and
  the Nuitka `.exe` build also run on 3.13 — see `.github/workflows/`)
- **uv** (package/venv manager) — install from https://docs.astral.sh/uv/

## Setup

```bash
uv sync            # creates .venv and installs falcon, waitress, requests
```

`uv sync` reads `pyproject.toml` at the repo root. The vendored engine
`zeromcp/` is a separate project with its own lockfile; you do **not** install it
— the app adds `zeromcp/src` to `sys.path` at import time.

## Credentials

TBMCP reads Upstox credentials from a `.env` file **next to the app** (repo root
when running from source; next to the `.exe` when frozen). Process environment
variables override the file.

| Variable | Purpose |
|---|---|
| `UPSTOX_API_KEY` | Upstox API key |
| `UPSTOX_API_SECRET` | Upstox API secret |
| `UPSTOX_REDIRECT_URI` | OAuth redirect URI (default `http://127.0.0.1:8888/upstox/callback`) |
| `TBMCP_PROVIDER` | Force a single data provider: `upstox` (default) or `fyers`. Leave unset to use the multi-provider registry below. |
| `UPSTOX_RATE_LIMIT_GAP_MS` | Throttle between Upstox calls (default `250`) |
| `UPSTOX_ENABLED` | Enable the Upstox provider (default `true`). Set `false` to run FYERS-only. |
| `FYERS_ENABLED` | Enable the FYERS provider (default `false`). Requires the two credentials below. |
| `FYERS_APP_ID` | FYERS app id (e.g. `XXXXXX-100`). |
| `FYERS_SECRET` | FYERS app secret. |
| `FYERS_PIN` | Optional 4-digit FYERS PIN (needed for refresh / TOTP login). |
| `FYERS_TOTP_SECRET` | Optional TOTP secret for the daily auto-login helper. |
| `FYERS_REDIRECT_URI` | OAuth redirect URI for the FYERS login helper. |
| `FYERS_TIMEOUT` | FYERS request timeout in seconds (default `10`). |

The OAuth token is saved to `.upstox-token.json` in the same folder. Both files
are gitignored — never commit them. FYERS caches its token in `.fyers-token.json`
(next to the app), also gitignored.

### FYERS (optional secondary provider)

FYERS is **data-only** (option chain, quotes, depth, history, Greeks) and is
**off by default**. To turn it on, set `FYERS_ENABLED=true` plus `FYERS_APP_ID`
and `FYERS_SECRET` in your `.env`. When both Upstox and FYERS are enabled, each
symbol is pinned to one broker (sticky affinity) so a chain never mixes two
brokers' numbers; FYERS is used as a fallback when Upstox is down.

FYERS access tokens expire at the end of the trading day, so log in each morning:

```bash
python -m providers.fyers_login
```

If `FYERS_TOTP_SECRET` and `FYERS_PIN` are set, this logs in automatically (no
browser). Otherwise it prints an OAuth URL, you log in, and paste the
`auth_code` back. See [decisions/adr-008-multi-provider-routing.md](../decisions/adr-008-multi-provider-routing.md).

You can also set credentials through the dashboard: the **gear icon → Upstox**
page saves them to `.env` and offers one-click login (no copy-paste), which
bounces the browser through `/upstox/callback`.

FYERS has its own dashboard page: the **FYERS** link in the top bar opens the
FYERS setup page. It saves `FYERS_APP_ID`/`FYERS_SECRET`/`FYERS_PIN`/
`FYERS_TOTP_SECRET` to `.env` (and flips `FYERS_ENABLED=true`), and offers two
login paths — **Get Login Link** (OAuth, bounces through `/fyers/callback`,
one-click like Upstox) and **Login with TOTP** (server-side daily auto-login,
no browser, when `FYERS_TOTP_SECRET` + `FYERS_PIN` are saved).

## Running

| Command | What it does |
|---|---|
| `python main.py` | Runs **both** MCP server and web UI (default). |
| `python main.py both` | Same as above, explicitly. |
| `python main.py mcp` | MCP server (stdio) only — for AI clients. |
| `python main.py ui` | Falcon web dashboard only — for humans. |
| `python main.py ui --host 0.0.0.0 --port 9000` | Dashboard on a custom host/port. |
| `python main.py ui --debug` | Dashboard with DEBUG-level logs. |

The dashboard listens on `http://127.0.0.1:8888` by default.

> Note: `--reload` is accepted but ignored by the Falcon server — restart the
> process to pick up changes. Logs go to **stderr** so they never corrupt the
> MCP server's stdout JSON-RPC stream.

## Layout details that matter locally

- `config.py` resolves paths portably: everything lives next to the app so the
  folder is fully portable (copy it anywhere). When frozen, the "app folder" is
  the directory holding the `.exe`.
- A legacy `~/.tbmcp` token location is still honored on read as a fallback.
