# ADR-005 — MCP Modularization

- **Status:** accepted
- **Date:** 2026-08-13

## Context

The MCP server grew to ~35 tools. If it keeps growing, a single flat
`mcp_server.py` would become one enormous file that is hard to navigate and hard
to change without touching everything.

## Decision

Keep the MCP layer modular by **tool category**, with exactly one shared server
instance:

```
mcp/
├── server.py         # assembly only: builds the shared McpServer, injects the
│                     # client, registers every module's TOOLS
├── market_data.py    # raw market-data tools (get_*)
├── options.py        # chain analytics + strategy pricers (compute_*, price_*)
├── technical.py      # created when the category grows
├── fundamentals.py   # created when the category grows
├── screening.py      # created when the category grows
└── portfolio.py      # created when the category grows
```

Rules:

1. **One shared MCP instance.** Tool modules never construct their own server;
   they expose a `TOOLS` list of plain async functions, and `server.py`
   registers them (`for fn in module.TOOLS: mcp.tool()(fn)`).
2. **Stable tool names.** The registered name is the function's `__name__`.
   Moving a tool between modules must never rename it — existing MCP clients
   must not break from internal refactoring.
3. **Split on category size, not on a whim.** Do not create empty modules just to
   match the tree.
4. **Client injection stays internal.** `server.py` injects the data client per
   module (`module._client = client`), keeping tool modules decoupled from
   provider construction.

## Alternatives considered

- **One flat `mcp_server.py`** — rejected: grows without bound, no ownership
  boundary, harder diffs.
- **One server per module** — rejected: breaks the shared-instance contract and
  tool-name stability.

## Consequences

- Adding a category = new module + one line in `server.py`'s registration loop.
- The inventory can be verified any time:
  `python -c "import mcp.server as s; print(sorted(s.mcp.tools.methods))"`.
- `technical.py`, `fundamentals.py`, `screening.py`, `portfolio.py` do not exist
  yet — per rule 3 they are created only when those categories grow.
