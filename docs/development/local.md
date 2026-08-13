# Local Development

## Requirements

- **Python >= 3.11**
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
| `RTMCP_PROVIDER` | Data provider to use (default `upstox`; the switch point for future brokers) |
| `UPSTOX_RATE_LIMIT_GAP_MS` | Throttle between Upstox calls (default `250`) |

The OAuth token is saved to `.upstox-token.json` in the same folder. Both files
are gitignored — never commit them.

You can also set credentials through the dashboard: the **gear icon → Upstox**
page saves them to `.env` and offers one-click login (no copy-paste), which
bounces the browser through `/upstox/callback`.

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
- A legacy `~/.rtmcp` token location is still honored on read as a fallback.
