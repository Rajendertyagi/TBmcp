# Plan: Replace NiceGUI with Flask + Vanilla JS

## Objective
Replace NiceGUI (20.3 MB) with Flask (103 KB) + vanilla JavaScript for the TBMCP trading dashboard. Keep all existing business logic, rendering, and CSS intact.

## Current NiceGUI Usage Analysis

| NiceGUI Feature | Lines Used | Replacement |
|-----------------|------------|-------------|
| `ui.add_head_html()` | 2 | Jinja2 `{% include %}` |
| `ui.row()` | 8 | `<div class="row">` |
| `ui.tabs()` / `ui.tab_panels` | 3 | Bootstrap/nav tabs |
| `ui.html()` | 15 | Direct HTML strings |
| `ui.label()` | 20 | `<span>` / `<div>` |
| `ui.input()` | 8 | `<input>` elements |
| `ui.select()` | 4 | `<select>` dropdowns |
| `ui.button()` | 10 | `<button>` with onclick |
| `ui.checkbox()` | 1 | `<input type="checkbox">` |
| `ui.timer()` | 6 | `setInterval()` + fetch |
| `ui.card()` | 4 | `<div class="card">` |
| `ui.run_javascript()` | 3 | Direct JS in templates |
| `ui.icon()` | 2 | Font Awesome / SVG |

**Total NiceGUI API calls: ~78** → All replaceable with vanilla HTML/JS

## Proposed Architecture

```
tbmcp-py/
├── main.py              # UNCHANGED (arg parsing, entry point)
├── server.py            # NEW: Flask app with all routes
├── templates/
│   └── index.html       # NEW: Main dashboard HTML
├── static/
│   └── js/
│       └── dashboard.js # NEW: Frontend logic (fetch, timers, charts)
├── render.py            # UNCHANGED
├── charts.py            # UNCHANGED  
├── constants.py         # UNCHANGED
├── client.py            # UNCHANGED
├── providers.py         # UNCHANGED
├── config.py            # UNCHANGED
├── buildup.py           # UNCHANGED
├── models.py            # UNCHANGED
├── tbmcp.css            # UNCHANGED (keep existing 1493 lines)
└── pyproject.toml       # Update: remove nicegui, add flask
```

## Implementation Steps

### Step 1: Create Flask Server (server.py)

Routes:
```python
@app.route('/')                          # Main dashboard page
@app.route('/api/chain')                 # Option chain data (JSON)
@app.route('/api/quote')                 # Live quotes for tickers (JSON)
@app.route('/api/historical')            # Historical candles (JSON)
@app.route('/api/expiries')              # Expiry dates for symbol (JSON)
@app.route('/api/save-creds', methods=['POST'])  # Save Upstox credentials
@app.route('/api/login-url')             # Generate OAuth login URL (JSON)
@app.route('/upstox/callback')           # OAuth callback handler
```

Key functions:
- `get_option_chain(symbol, expiry)` → JSON response
- `get_quotes(symbols)` → JSON response with last_price, net_change, p_change
- `get_historical(symbol, interval, days)` → JSON response with candles
- `save_credentials(key, secret, redirect)` → writes .env file
- `build_login_url(key, redirect)` → returns OAuth URL

### Step 2: Create HTML Template (templates/index.html)

Structure:
```html
<!DOCTYPE html>
<html>
<head>
    <title>TBMCP - Market Dashboard</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/tbmcp.css') }}">
    <!-- Include tbmcp.css directly or inline it -->
</head>
<body>
    <!-- Top Bar -->
    <div class="tbmcp-topbar">
        <div class="tbmcp-ticker">...</div>
        <nav class="tbmcp-tabs">...</nav>
    </div>
    
    <!-- Tab Panels -->
    <div id="tab-content">
        <!-- NIFTY Page -->
        <div id="page-nifty" class="tbmcp-page">...</div>
        
        <!-- BANKNIFTY Page -->
        <div id="page-banknifty" class="tbmcp-page">...</div>
        
        <!-- INDIA VIX Page -->
        <div id="page-vix" class="tbmcp-page">...</div>
        
        <!-- Upstox Setup Page -->
        <div id="page-upstox" class="tbmcp-page">...</div>
    </div>
    
    <script src="{{ url_for('static', filename='js/dashboard.js') }}"></script>
</body>
</html>
```

### Step 3: Create JavaScript (static/js/dashboard.js)

Features:
```javascript
// Auto-refresh timers (replaces ui.timer)
let tickerInterval = setInterval(fetchTickers, 10000);
let chainInterval = setInterval(fetchChain, 30000);

// Fetch API calls
async function fetchChain(symbol, expiry) {
    const resp = await fetch(`/api/chain?symbol=${symbol}&expiry=${expiry}`);
    const data = await resp.json();
    document.getElementById('chain-table').innerHTML = data.html;
}

async function fetchTickers() {
    const resp = await fetch('/api/quote?symbols=NIFTY,BANKNIFTY');
    updateTickerUI(resp.data);
}

// Chart rendering (reuse existing charts.py logic)
function renderChart(chartId, candles) {
    // Call build_chart_js() equivalent in JS
    // Or use endpoint /api/chart-js?chart_id=...
}

// Tab switching
function switchTab(tabName) {
    document.querySelectorAll('.tbmcp-page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${tabName.toLowerCase()}`).classList.add('active');
}
```

### Step 4: Update pyproject.toml

```toml
dependencies = [
    "mcp",
    "flask",           # Replace nicegui
    "requests",
    "pandas",
]
```

### Step 5: Update main.py

```python
def run_ui(host: str, port: int, reload: bool = False) -> None:
    from server import app
    app.run(host=host, port=port, debug=reload)
```

## Key Considerations

### Real-time Updates
- Use `setInterval()` in JS instead of NiceGUI's `ui.timer()`
- Poll API every 10-30 seconds (configurable)
- Show loading spinner during fetches

### Chart Rendering
- Keep using lightweight-charts via CDN (already working)
- Move `build_chart_js()` logic to server endpoint or inline in template
- Alternative: Create `/api/chart-js` endpoint that returns JS string

### CSS Compatibility
- **tbmcp.css stays unchanged** - all class names remain valid
- Only need to ensure HTML structure matches CSS selectors
- May need minor adjustments for tab/panel structure

### State Management
- Store selected symbol/expiry in JS variables
- Pass state via URL params or localStorage
- Credentials stored in .env (existing mechanism)

## Migration Checklist

- [ ] Create `server.py` with Flask app
- [ ] Implement all API endpoints
- [ ] Create `templates/index.html` with tab structure
- [ ] Create `static/js/dashboard.js` with fetch logic
- [ ] Test option chain loading
- [ ] Test ticker updates
- [ ] Test chart rendering
- [ ] Test Upstox login flow
- [ ] Verify CSS compatibility
- [ ] Update pyproject.toml
- [ ] Update main.py
- [ ] Test with Nuitka compilation

## Estimated Effort

| Task | Time |
|------|------|
| server.py | 2-3 hours |
| index.html template | 1-2 hours |
| dashboard.js | 2-3 hours |
| Testing & debugging | 2-3 hours |
| **Total** | **7-11 hours** |

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CSS class conflicts | Low | Keep tbmcp.css unchanged |
| Timer precision issues | Low | Use requestAnimationFrame for smooth updates |
| CORS issues | Low | Same-origin Flask server |
| Nuitka compatibility | Medium | Test early, use standard Flask patterns |

## Success Criteria

1. Dashboard loads at `http://127.0.0.1:8888/`
2. Option chain displays correctly with existing CSS
3. Auto-refresh works (tickers every 10s, chain every 30s)
4. Charts render with lightweight-charts
5. Upstox login flow completes successfully
6. Package size reduced from 20MB to ~150MB (Flask + deps)
7. Compiles with Nuitka without WebSocket issues
