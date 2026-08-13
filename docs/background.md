# Why TBMCP exists

This is the history and the reasoning behind the project's decisions. For the
formal decision records see [decisions/](decisions/README.md); for the current
technical design see [architecture.md](architecture.md).

## Where it came from

We originally built **TBMCP** — a TypeScript MCP server forked from
`devag7/Indian-Option-MCP`, later extended with an NSE data kit and Upstox
support. We decided **not to use TBMCP** and retired it. (Its GitHub repo
`github.com/Rajendertyagi/RTMCP` still exists and is pending deletion.)

**TBMCP** is the fresh Python replacement, built for two reasons:
- The **Python + ZeroMCP + Falcon** path is simpler to develop and maintain.
- The AI-facing server is based on the forked **ZeroMCP** engine, which we
  control and which can grow later (it also supports HTTP transport and OAuth).

## The decisions, briefly

Each full decision record (context, options, consequences) lives in
[decisions/](decisions/README.md):

1. **One AI server, not two.** Early on there were two ways to serve the AI — a
   small `tools.py` on the official `mcp` SDK (stdio only) and the forked ZeroMCP
   engine. ZeroMCP won; `tools.py` was retired.
   → [decisions/adr-001-zeromcp-engine.md](decisions/adr-001-zeromcp-engine.md)
2. **Falcon + static HTML/JS over NiceGUI.** The dashboard was originally
   NiceGUI; the goal of a single portable Nuitka `.exe` drove a review. NiceGUI
   bundles a heavy frontend that is fiddly to freeze. PyWebIO was rejected
   (stale, last release Apr 2025) and Flet was rejected (its own Flutter
   packaging makes Nuitka no simpler). **Falcon** won: latest 4.3.1, zero
   external dependencies (stdlib only) → the cleanest possible Nuitka freeze.
   → [decisions/adr-002-falcon-dashboard.md](decisions/adr-002-falcon-dashboard.md)
3. **DataProvider abstraction.** A broker/data source must be able to fit behind
   a stable protocol without MCP tools or frontend pages changing.
   → [decisions/adr-003-data-provider-abstraction.md](decisions/adr-003-data-provider-abstraction.md)
4. **File Responsibility rule.** Every important file has a clear reason to
   change; name files for their responsibility.
   → [decisions/adr-004-file-responsibility.md](decisions/adr-004-file-responsibility.md)
5. **MCP Modularization rule.** One module per tool category, registered against
   a single shared MCP instance; tool names stay stable.
   → [decisions/adr-005-mcp-modularization.md](decisions/adr-005-mcp-modularization.md)
6. **Development Workflow rule.** Every new feature follows a fixed 7-step
   sequence (understand → ownership → modularity → implement → test → document →
   report); major restructuring stops and is reported before proceeding.
   → [decisions/adr-006-development-workflow.md](decisions/adr-006-development-workflow.md)
7. **No-giant-files rule.** Do not let files balloon just because the app grew;
   prefer focused modules and split files that hold many unrelated
   responsibilities.
   → [decisions/adr-007-no-giant-files.md](decisions/adr-007-no-giant-files.md)

## Why this matters

- **One AI server** — no confusing overlap between SDKs.
- **A portable build** — the app can ship as a single `.exe` via Nuitka and be
  copied to any machine (see [packaging/nuitka.md](packaging/nuitka.md)).
- **Maintained dependencies** — stale/unhelpful frameworks were dropped on
  purpose.
