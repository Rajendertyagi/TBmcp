# ADR-006 — Development Workflow

- **Status:** accepted
- **Date:** 2026-08-13

## Context

Feature work previously drifted into coding before the surrounding architecture,
ownership, and modularity were understood. The repo has strong *structural* rules
(File Responsibility, MCP Modularization, DataProvider boundary) but no *process*
rule: nothing said how a feature gets from an idea to a merged change, so steps
like understanding the existing design, deciding where the change belongs, and
reporting the result were ad-hoc.

## Decision

Every new feature follows a **fixed 7-step sequence**:

1. **Understand** — inspect the relevant source files, architecture, existing
   APIs, existing MCP tools, existing frontend pages, existing services, tests,
   and documentation. Do not immediately start coding.
2. **Identify ownership** — determine the feature, the existing modules
   involved, the new modules required, the existing files that should **not** be
   modified, and the dependencies.
3. **Decide modularity** — decide whether an existing module is appropriate, a
   new module is needed, or an existing module should be split first. **If major
   restructuring is needed, STOP and report it before proceeding.**
4. **Implement** — make the smallest clean change consistent with the
   architecture.
5. **Test** — test the feature and regression-test the affected functionality.
6. **Documentation** — update the relevant documentation if the architecture,
   API, MCP tools, frontend pages, configuration, or behavior changed.
7. **Report** — report: files created, files modified, files removed, tests
   performed, architecture impact, documentation updated, remaining issues.

The full "how to apply" reference (with repo-specific pointers per step) lives at
[`docs/development/workflow.md`](../development/workflow.md).

## Alternatives considered

- **Informal "understand the code first" guidance** — rejected: good intention
  but unverifiable and easily skipped under time pressure.
- **CI-enforced checklist gates** — rejected: the workflow is a discipline, not
  a build check; CI already validates the structural contracts (tool inventory,
  protocol methods, routes).

## Consequences

- Features get an explicit ownership and modularity decision *before* code,
  so changes land in the right layer on the first pass.
- The Step-3 stop gate catches major restructuring early, when it is cheapest
  to discuss.
- The Step-7 report gives every change a stable handoff shape for review and
  for the next session.
- The cost is one short planning pass per feature — paid back by fewer reworks
  and boundary violations.
