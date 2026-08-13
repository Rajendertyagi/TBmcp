# Packaging — Nuitka standalone `.exe`

The project goal is to ship as a single portable Windows `.exe` (see
[decisions/adr-002-falcon-dashboard.md](../decisions/adr-002-falcon-dashboard.md)
for why the stack was chosen to make this easy).

## Build command

Run **only in CI / release**, never locally during development:

```bash
python -m nuitka --onefile \
    --include-package=zeromcp \
    --include-data-dir=frontend=frontend \
    --include-package=falcon,waitress,requests main.py
```

## What it produces

- A standalone `rtmcp.exe` containing the Python runtime, the app, the falcon /
  waitress / requests packages, the `zeromcp` engine package, and the
  `frontend/` static files.
- Configuration (`config.py`) is portable by design: when frozen, the "app
  folder" is the directory holding the `.exe`, so `.env` and
  `.upstox-token.json` live **next to the exe** — copy the whole folder anywhere
  and it works, with no dependency on the user's home directory.

## Why the stack makes this trivial

- **Falcon** is zero-dependency (stdlib only).
- **Waitress** is a pure-Python WSGI server (no C extension to freeze).
- The **frontend is static files** — no bundler, no Node, no source maps; the
  `--include-data-dir=frontend=frontend` flag just copies them into the bundle.

## Notes

- `main.py` calls `multiprocessing.freeze_support()` so the `both` mode (which
  spawns the UI process) works inside a frozen binary.
- Keep the include flags in sync with `pyproject.toml`'s dependency list when
  they change.
