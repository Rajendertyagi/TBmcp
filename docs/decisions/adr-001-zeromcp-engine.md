# ADR-001 — ZeroMCP engine as the single MCP server

- **Status:** accepted
- **Date:** 2026-08-13

## Context

The project initially had **two** ways to serve the AI:
1. a small `tools.py` built on the official `mcp` Python SDK (stdio only), and
2. a forked **ZeroMCP** engine — a zero-dependency MCP server framework we
   control.

Two servers meant confusing overlap, duplicated tool definitions, and a
maintenance burden. We needed a single AI-facing server.

## Decision

Use the **forked ZeroMCP engine** as the one and only MCP server. The engine is
vendored as a self-contained project at `zeromcp/` (not pip-installed); the app
adds `zeromcp/src` to `sys.path` at import time in `mcp/server.py`.

## Alternatives considered

- **Official `mcp` SDK (keep `tools.py`)** — rejected: stdio-only at the time,
  not under our control, and keeping two servers violated the one-server goal.
- **Pip-install the fork** — rejected: we want a fully self-contained, auditable
  vendored copy that can grow (HTTP transport, OAuth) without an upstream
  release.

## Consequences

- Single code path for AI tool registration; the 3 original tools were moved
  into `mcp/server.py` and grew to 35.
- We own the engine's maintenance and its sync-with-upstream status.
- Every module registers against one shared `McpServer` (see ADR-005).
