# Frontend Guide

The dashboard is an intentionally **vanilla JavaScript SPA-style application**
— no React, Vue, Angular, or other framework. It is served as static files by
the Falcon backend (see [api/endpoints.md](../api/endpoints.md)); the browser
does all routing and rendering.

## Structure

```
frontend/
├── index.html            # single application shell (see below)
├── style.css             # all styles incl. bundled web-font @font-face rules
├── vendor/
│   └── lightweight-charts.js   # classic global script (v4, local)
└── js/
    ├── app.js            # bootstrap only: registers pages, wires top bar, starts ticker
    ├── router.js         # client-side routing / nav tabs
    ├── api.js            # the ONLY module that talks to the backend
    ├── state.js          # tiny cross-cutting app state (currentRoute)
    ├── pages/            # one module per page
    ├── components/       # reusable UI pieces
    └── utils/            # generic helpers (dom, format, config)
```

## The shell (`index.html`)

`index.html` is the only HTML file. It contains the top bar (home icon, live
ticker, nav tabs, "Option Chain" / "Charts" links, settings gear) and an empty
`<main class="rtmcp-content">` where pages are mounted. It loads the chart
library as a classic script **before** the ES-module entry point
(`<script type="module" src="/static/js/app.js">`).

## Router (`js/router.js`)

Pages register themselves with `registerRoute(key, label, factory, opts)`.
The router:

- builds the nav tabs from the registry (tabs are `showTab: true` routes),
- lazily mounts each page into its own `<section>` on first visit, then
  shows/hides it (so a page keeps running its auto-refresh timers in the
  background),
- groups routes (`group: "chain"`, `group: "chart"`) so overview pages can build
  navigation cards without hardcoding the page list (`listRoutes(group)`).

**Adding a page = one `registerRoute()` line in `app.js`** plus a
`pages/foo.js` module exporting `createFooPage()`. Nothing else changes.

## Pages (`js/pages/`)

Each page module exports a `createXPage()` factory returning `{ mount, onShow?,
refresh? }`.

| Module | Route(s) | Purpose |
|---|---|---|
| `home.js` | `home` | Overview cards linking to the chain/chart pages. |
| `market.js` | `nifty`, `banknifty`, `sensex` | Option-chain table + stats per index (reused factory). |
| `vix.js` | `vix` | India VIX quote + chart. |
| `charts.js` | `charts`, `chart-nifty`, `chart-banknifty`, `chart-sensex` | Chart builder (lightweight-charts). |
| `tools.js` | `tools` | Runs every tool once via `/api/test-all` and shows results. |
| `upstox.js` | `upstox` | Settings + one-click login (reached via the gear icon). |

## Components (`js/components/`)

Reusable UI: `ticker.js` (top ticker bar), `chart.js` (chart wrapper),
`controls.js` (page control bars), `error.js` (error display).

## Communication (`js/api.js`)

`api.js` is the **only** module that calls `fetch()`. It wraps every request in
`request(path, opts)` which returns `{ ok, status, body }` so pages check both
HTTP status and the body's own `{ error: ... }` uniformly. Pages never hardcode
endpoint URLs.

## Utils (`js/utils/`)

- `dom.js` — DOM helpers.
- `format.js` — number formatting.
- `config.js` — client-side constants (refresh intervals).

## Rules

1. **No framework.** Do not introduce React/Vue/Angular/Next.js without explicit
   approval.
2. **`app.js` stays small.** Bootstrap/orchestration only; pages go in `pages/`,
   reusable UI in `components/`, API calls in `api.js`, generic helpers in
   `utils/`. Never dump unrelated code into `app.js`.
3. **Keep it vanilla and static.** The whole frontend must freeze into the
   Nuitka `.exe` as plain files (see [../packaging/nuitka.md](../packaging/nuitka.md)).
