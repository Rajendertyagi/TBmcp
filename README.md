# TBMCP

TBMCP is a personal Indian stock-market application with two consumers sharing
one data layer:

- **An AI assistant** — an MCP server exposing **42 tools** (raw market data,
  fundamentals / news / option Greeks, derived F&O analytics and strategy
  pricers) over stdio.
- **A human** — a web dashboard (Falcon + static HTML/JS) on
  `http://127.0.0.1:8888`.

Both read live data from the **Upstox** broker through a single provider
abstraction, so the AI view and the human view never disagree.

## Quick start

Requires **Python >= 3.11** (pinned to 3.13 via `.python-version`) and **uv**.

```bash
uv sync                # create .venv and install falcon, waitress, requests
python main.py         # run BOTH MCP server + web UI (default)
python main.py mcp     # MCP server (stdio) only — for AI clients
python main.py ui      # web dashboard only — for humans
```

## Credentials

Set `UPSTOX_API_KEY` / `UPSTOX_API_SECRET` / `UPSTOX_REDIRECT_URI` in a `.env`
file next to the app (or via the dashboard's gear-icon settings page). The OAuth
token is saved to `.upstox-token.json`. Both files are gitignored — never
commit them.

## Documentation

- [`AGENTS.md`](AGENTS.md) — onboarding map for humans and AI agents: how the
  project is laid out and the rules that govern changes.
- [`docs/README.md`](docs/README.md) — full documentation index.
