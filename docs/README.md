# TBMCP — Documentation

**TBMCP** (project name `rtmcp`) is a personal Indian stock-market application: an
**MCP server** that lets AI agents query live market data, plus a **web
dashboard** for a human. Both read the same data from the **Upstox** broker
through one shared data layer.

This folder is organized so a completely new AI coding agent — or a human — can
understand the project without any previous conversation history. Every fact
lives in exactly one document; other documents link to it rather than repeat it.

## Where to start

| You want to... | Read |
|---|---|
| Understand what the product is and who uses it | [product.md](product.md) |
| Understand how the code is organized and the rules for changing it | [architecture.md](architecture.md) |
| Know why decisions were made | [background.md](background.md) and [decisions/](decisions/README.md) |
| List the HTTP endpoints the dashboard uses | [api/endpoints.md](api/endpoints.md) |
| List the MCP tools exposed to AI clients | [mcp/tools.md](mcp/tools.md) |
| Work on the browser frontend | [frontend/guide.md](frontend/guide.md) |
| Set up a local environment and run the app | [development/local.md](development/local.md) |
| Know what tests exist and how to run them | [testing/README.md](testing/README.md) |
| Build a standalone `.exe` with Nuitka | [packaging/nuitka.md](packaging/nuitka.md) |

## Quick orientation

- **AI side:** `python main.py mcp` starts an MCP server (stdio transport) built
  on the forked ZeroMCP engine, exposing 35 tools (raw market data + derived F&O
  analytics). See [mcp/tools.md](mcp/tools.md).
- **Human side:** `python main.py ui` starts a Falcon web server serving a
  static HTML/JS single-page app on `http://127.0.0.1:8888`.
- `python main.py` (or `both`) runs both simultaneously.

## Document map

```
docs/
├── README.md          # you are here — index
├── product.md         # what the product is
├── architecture.md    # how the code is organized + rules
├── background.md      # history and why
├── api/endpoints.md   # HTTP API reference
├── mcp/tools.md       # MCP tool reference
├── frontend/guide.md  # browser frontend
├── development/local.md  # local setup and run
├── testing/README.md  # tests and verification
├── packaging/nuitka.md   # release .exe build
└── decisions/         # architecture decision records (ADRs)
```

Retired working notes and historical plans are preserved under
[archive/](archive/README.md).
