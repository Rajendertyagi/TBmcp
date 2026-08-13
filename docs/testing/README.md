# Testing

TBMCP has three test suites: **offline unit tests**, **offline integration
tests** (both run in CI, no network, no credentials), and an **opt-in live
suite** that hits the real Upstox broker.

## Suite layout

| Suite | Where | Requires network / creds | Run with |
|---|---|---|---|
| Unit | `tests/unit/` | No | `python -m pytest tests/unit` |
| Integration | `tests/integration/` | No | `python -m pytest tests/integration` |
| Live (gated) | `tests/live/` | Yes | `TBMCP_RUN_LIVE=1 python -m pytest tests/live -m live` |

`pyproject.toml` sets `testpaths = ["tests/unit", "tests/integration"]`, so a
bare `python -m pytest` runs only the offline suites and never touches the
broker.

## What each suite covers

### `tests/unit/` — pure logic, no I/O

- `test_config.py` — settings precedence (process env over `.env`), portable
  config paths, env-file round-trips.
- `test_models.py` — typed data models (`OptionChain`, `Candle`, ...).
- `test_analytics.py` / `test_buildup.py` / `test_strategy_pricer.py` — the
  shared analytics and strategy pricers (`compute_pcr`, `compute_max_pain`,
  `compute_oi_buildup`, `price_long_straddle`, ...). These are the functions
  both the MCP tools and the Falcon routes call, so a failure here fails both
  consumers.
- `test_mcp_tools.py` — **all 42 MCP tool functions** run against a recording
  stub client: every tool returns parseable JSON, options tools fetch the chain
  and return their signature key, and client arguments are forwarded correctly.
  This is the regression test for the old flat-server shadowing bug where every
  `compute_*` tool raised `TypeError`.
- `test_api_helpers.py` — the `api.app` helpers (`_safe` error boundary,
  `_json` response writer, lazy `get_client`/`rebuild_client`) and the pure
  `api.render` module (`render_chain`, `chain_css`, number/class formatting).

Shared synthetic fixtures live in `tests/unit/conftest.py`
(`make_option_chain`, `chain`).

### `tests/integration/` — the boundaries, with a fake broker

The app talks to the broker only through the `DataProvider` protocol
(`providers/base.py`). Integration tests inject a deterministic in-memory
double — `FakeProvider` in `tests/integration/conftest.py` — and exercise the
real layers above it with zero network:

- `test_provider_factory.py` — `create_provider()` is the single switch point
  (defaults to Upstox, unknown provider raises), and the fake structurally
  conforms to all 30 `DataProvider` methods.
- `test_mcp_server.py` — **the 42 registered MCP tool names are a stable
  contract** (see AGENTS.md §16.1). A refactor that renames a tool fails this
  suite. This replaces the old inline CI inventory check.
- `test_api_routes.py` — every Falcon route through a `TestClient`: happy
  paths, 400s for missing params, settings round-trip, login status, and the
  `_safe` error boundary (upstream failures become JSON error responses, never
  HTTP 500s).
- `test_tools_runner.py` — the shared `run_all_tools()` batch: all-ok, upstream
  failure recorded per tool (never raised), and clean "skipped" entries when no
  option expiry resolves.

### `tests/live/` — opt-in, real broker

Gated with `pytest.mark.live` and skipped unless `TBMCP_RUN_LIVE=1` is set with
valid Upstox credentials:

```bash
$env:TBMCP_RUN_LIVE = "1"
python -m pytest tests/live -m live
```

Never runs in CI.

## Running everything

```bash
# Offline suites (what CI runs)
python -m pytest

# One suite
python -m pytest tests/unit
python -m pytest tests/integration

# Full collection including gated live tests (they will be skipped)
python -m pytest tests
```

## Legacy batch harness

`tests/tool_test.py` remains as a live one-off script for manual broker checks:

```bash
python tests/tool_test.py NIFTY
```

Its batch logic lives in the **production** module
`services/tools_runner.py` (`run_all_tools`), which the WebUI's Tools page also
calls — the app never depends on the `tests/` package to start.

## CI

`.github/workflows/ci.yml` runs, on every push and PR: `compileall` syntax
check, `python main.py --help` smoke, and the offline pytest suites. The
vendored engine ships no CI of its own (GitHub only runs root-level workflows;
the app's tests cover the engine).

## Keeping the 42-tool contract green

After any MCP refactor, the fastest signal is the integration suite:

```bash
python -m pytest tests/integration/test_mcp_server.py
```

or the raw one-liner:

```bash
python -c "import mcp.server as s; print(sorted(s.mcp.tools.methods))"
```
