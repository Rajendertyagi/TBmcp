# ADR-004 — File Responsibility Rule

- **Status:** accepted
- **Date:** 2026-08-13

## Context

Generic file names (`helpers.py`, `misc.py`, `common.py`, `utils2.py`, ...) hide
multiple unrelated responsibilities and give future changes no obvious home.
Without a rule, files degrade into dumping grounds.

## Decision

Every important file must have a **clear reason to change**, and the name must
describe the file's responsibility. Test before naming: *"Why would someone edit
this file?"* — if the honest answer lists several unrelated reasons, split it.

Signals:

1. **One verb per file** — a file does one job ("render the chain table", "run
   every tool", "adapt Upstox to the protocol").
2. **The name survives a rename test** — `upstox.py` stays correct if the broker
   is swapped; `misc.py` is wrong no matter what it contains.
3. **No siblings by qualification** — `utils2.py`, `extra.py`, `helpers_final.py`
   are symptoms of a file outgrowing its name; split the file, don't suffix the
   name.

## Alternatives considered

- **No rule, ad-hoc naming** — rejected: exactly the drift this rule prevents.
- **One file per function** — rejected: overkill; the rule is about
  responsibilities, not granularity.

## Consequences

- New files are easy to place: the name tells you where a feature belongs.
- Reviews flag generic names and files whose name no longer matches content.
- The codebase was audited and already complies after the package restructure
  (see [architecture.md](../architecture.md) for the layout).
