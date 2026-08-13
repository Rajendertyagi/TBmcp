# ADR-002 — Falcon + static HTML/JS dashboard (not NiceGUI/PyWebIO/Flet)

- **Status:** accepted
- **Date:** 2026-08-13

## Context

The dashboard was originally built on **NiceGUI**. The project goal is to ship a
single portable **Nuitka `.exe`**, and NiceGUI bundles a heavy frontend that is
fiddly to freeze. We reviewed lighter web-framework alternatives for the
human-facing dashboard.

## Decision

Use **Falcon** (a zero-dependency WSGI framework, stdlib-only) for the backend,
serving a plain static HTML/JS single-page app (`frontend/`). Charts come from
TradingView's open-source **lightweight-charts** v4, bundled locally.

## Alternatives considered

| Candidate | Verdict |
|---|---|
| **PyWebIO** | ❌ Rejected — last release Apr 2025 (~16 months stale as of Aug 2026); not maintained enough to build on. |
| **Flet** (Flutter-based) | ❌ Rejected for this — actively maintained, but its own Flutter packaging makes Nuitka *no simpler*. |
| **Falcon** + static HTML/JS | ✅ **Chosen** — latest 4.3.1 (Jun 2026), zero external dependencies → cleanest possible Nuitka freeze. |

## Consequences

- The Python side has no extra runtime dependencies beyond `falcon`/`waitress`,
  so the `.exe` freezes trivially (see [packaging/nuitka.md](../packaging/nuitka.md)).
- The frontend is plain ES-module JS with no framework and no build step — the
  whole dashboard is a set of static files.
- Same features as the NiceGUI version, served on `http://127.0.0.1:8888`.
