# Decisions — Architecture Decision Records

This folder records **decisions that shape the project** in lightweight ADR
(Architecture Decision Record) form. Each file answers: *What did we decide, why,
and what are the consequences?*

## Reading

| ADR | Decision |
|---|---|
| [adr-001-zeromcp-engine.md](adr-001-zeromcp-engine.md) | Use the forked ZeroMCP engine as the single MCP server (retire the official SDK `tools.py`). |
| [adr-002-falcon-dashboard.md](adr-002-falcon-dashboard.md) | Falcon + static HTML/JS instead of NiceGUI / PyWebIO / Flet. |
| [adr-003-data-provider-abstraction.md](adr-003-data-provider-abstraction.md) | All broker access behind a `DataProvider` protocol. |
| [adr-004-file-responsibility.md](adr-004-file-responsibility.md) | Every important file has a clear reason to change; name files for their responsibility. |
| [adr-005-mcp-modularization.md](adr-005-mcp-modularization.md) | One MCP module per tool category, one shared `McpServer`; tool names are a stable contract. |

## Writing new ADRs

Use this template (see [adr-001-zeromcp-engine.md](adr-001-zeromcp-engine.md) as
an example):

```markdown
# ADR-NNN — <Title>

- **Status:** accepted | superseded-by-ADR-NNN | rejected
- **Date:** YYYY-MM-DD

## Context
What problem were we solving, and what were the constraints?

## Decision
What we decided to do.

## Alternatives considered
What we considered and why we did not choose it.

## Consequences
What gets easier / harder because of this decision.
```

Number the next file `adr-006-<topic>.md`. One decision per file; link between
files when one supersedes another.
