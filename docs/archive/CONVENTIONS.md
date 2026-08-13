# TBMCP — Project Conventions

This document records standing rules that apply to all future work in this
repository. Phase 5 established the File Responsibility Rule; Phase 6 added the
MCP Modularization Rule.

## Rule 1 — File Responsibility

Every important file should have a clear reason to change. A file's name must
describe its responsibility — the domain concept or the single job it owns — not
its position in a hierarchy or its age.

### Bad names

Generic, grab-bag names hide multiple unrelated responsibilities and give future
changes no obvious home:

```
helpers.py      # "helping" what? every file helps with something
misc.py         # a junk drawer, not a module
stuff.py        # not a responsibility
common.py       # "common to whom?" — a magnet for everything
new.py          # describes birth order, not duty
extra.py        # same
utils2.py       # names the folder twice and says nothing
```

### Good names

Names that name the domain concept or the single job:

```
option_chain.py
technical_analysis.py
market_data.py
fundamentals.py
screening.py
upstox.py
portfolio.py
```

### Test

Before naming a file, ask: **"Why would someone edit this file?"** If the honest
answer lists several unrelated reasons — or the file is "everything else that
didn't fit" — split it until each piece has one answer.

Three useful signals:

1. **One verb per file.** A file should do one job ("render the chain table",
   "run every tool", "adapt Upstox to the DataProvider protocol").
2. **The name survives a rename test.** `upstox.py` stays correct if the broker
   is swapped (the file owns the Upstox adapter); `misc.py` is wrong no matter
   what it contains.
3. **No siblings by qualification.** `utils2.py`, `extra.py`, `new.py`,
   `helpers_final.py` are all symptoms of a file outgrowing its name — split the
   file instead of suffixing the name.

### Current status (audit, Phase 5)

The repo already complies after the Phase 4 restructure. Named modules describe
responsibility: `analytics/options.py`, `providers/{base,upstox}.py`,
`mcp/{server,market_data,options}.py`, `api/{app,routes,render}.py`,
`services/tools_runner.py`, and frontend `pages/*` / `components/*`.

Noted (accepted) trade-offs:

- `frontend/js/utils/` uses the generic folder name, but each file inside
  (`dom.js`, `format.js`, `config.js`) has a clear sub-responsibility.
- `providers/upstox.py` (~1060 lines) is one file because it is one job — the
  whole Upstox adapter. Size is a smell to watch, but not a responsibility
  violation.
- `models.py` groups several domain models; split if it keeps growing.
- `api/routes/__init__.py` holds all 12 HTTP resources; split per resource when
  it becomes a grab-bag.

### How to apply

- New files: follow the test above before choosing a name.
- Refactors: when a file stops answering "why would someone edit this?" with one
  sentence, split it — do not rename it to `_2` or fold it into `utils.py`.
- Reviews: flag generic names (`helpers`, `misc`, `common`, `utils` as a
  dumping ground) and files whose name no longer matches their content.

## Rule 2 — MCP Modularization

The MCP server currently exposes ~35 tools. If the tool set grows substantially,
do **not** allow one enormous `mcp_server.py`. When a tool category becomes large
enough, give it its own module under `mcp/`:

```
mcp/
├── server.py         # assembly only: builds the shared MCP instance,
│                     # injects the data client, registers every module's tools
├── market_data.py    # raw market-data tools (get_*)
├── options.py        # option-chain analytics / strategy pricers (compute_*, price_*)
├── technical.py      # technical-analysis tools          (created when the category grows)
├── fundamentals.py   # fundamental-analysis tools        (created when the category grows)
├── screening.py      # scrip-screening tools             (created when the category grows)
└── portfolio.py      # holdings/positions/portfolio tools (created when the category grows)
```

### Rules

1. **One shared MCP instance.** `server.py` owns the single `McpServer` (created
   once) and passes it the tools. Tool modules never construct their own server —
   they expose a `TOOLS` list of plain async functions; `server.py` registers
   them (`for fn in module.TOOLS: mcp.tool()(fn)`).
2. **Stable tool names.** The registered tool name is the function's `__name__`.
   Refactoring (moving a tool to a different category module) must never rename a
   tool. Existing MCP clients must not break because of internal refactoring.
3. **Split on category size, not on a whim.** Keep the current modules until a
   category is large enough to justify its own file. Do not create empty modules
   just to match the tree — same spirit as Phase 4's "don't create meaningless
   directories".
4. **Client injection stays internal.** `server.py` injects the data client into
   each module (`module._client = client`) so tool modules stay decoupled from
   provider construction.

### Current status (audit, Phase 6)

Already compliant. `mcp/server.py` (~55 lines) is assembly-only; `market_data.py`
holds 19 raw tools, `options.py` 16 derived/strategy tools, for 35 total.
`technical.py`, `fundamentals.py`, `screening.py`, `portfolio.py` do not exist
yet — per rule 3 they should only be created when those categories grow.

### How to apply

- New tools: add to the module whose category it belongs to; if no module fits,
  that is the signal a new category module is warranted — but only once it has a
  handful of tools, not one.
- Moving tools between modules: keep the function name identical (rule 2).
- Verify after any refactor: tool inventory still reports the same names
  (`python -c "import mcp.server as s; print(sorted(s.mcp.tools.methods))"`).
