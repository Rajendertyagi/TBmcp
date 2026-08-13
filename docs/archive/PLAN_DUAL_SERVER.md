# Plan: Dual HTTP Server + Framework Options for RTMCP

## Current State

| Component | Transport | Port | Implementation |
|-----------|-----------|------|----------------|
| **MCP Server** | stdio | N/A | `mcp.stdio()` in `main.py` |
| **NiceGUI Dashboard** | HTTP | 8888 | `ui.run()` in `ui.py` |

**Issue:** Can only run ONE at a time. `mcp.stdio()` blocks forever.

---

## Option 1: Dual HTTP Server (Keep NiceGUI)

### Architecture
```
python main.py all
│
├── MCP Server (HTTP) ──► Port 8000
│                          /mcp endpoint
│                          /sse endpoint
│
└── NiceGUI Dashboard ──► Port 8888
                           / endpoint
                           Real-time updates
```

### Changes Required

**1. `main.py` - Add `all` command**
```python
def run_all(host: str, mcp_port: int, ui_port: int) -> None:
    """Run both MCP (HTTP) and dashboard simultaneously."""
    from mcp_server import mcp
    from ui import build_app
    
    # Start MCP server in background thread
    mcp.serve(host, mcp_port, background=True)
    
    # Start NiceGUI dashboard (blocks)
    build_app(host, ui_port, reload=False)
```

**2. `mcp_server.py` - No changes needed**
- `zeromcp.McpServer.serve()` already supports HTTP mode
- Runs in background thread by default (`background=True`)

**3. `pyproject.toml` - Add constants**
```python
# constants.py
DEFAULT_MCP_PORT = 8000
DEFAULT_UI_PORT = 8888
```

### Benefits
- ✅ Single process, dual purpose
- ✅ AI clients can connect via HTTP (remote or local)
- ✅ Humans access dashboard separately
- ✅ No Nuitka issues (keep NiceGUI running)

### Drawbacks
- ❌ Still uses NiceGUI (20.3 MB dependency)
- ❌ MCP not accessible via stdio (only HTTP)

---

## Option 2: Replace NiceGUI with Flask (Lighter Weight)

### Architecture
```
python main.py all
│
├── MCP Server (HTTP) ──► Port 8000
│                          /mcp endpoint
│
└── Flask Dashboard ────► Port 8888
                           / endpoint
                           /api/chain
                           /api/quote
```

### Files to Create
```
rtmcp-py/
├── server.py          # NEW: Flask app with routes
├── templates/
│   └── index.html     # NEW: Dashboard HTML (reuse rtmcp.css)
├── static/
│   └── js/
│       └── dashboard.js  # NEW: Frontend fetch logic
├── ui.py              # DEPRECATED: Remove NiceGUI code
├── render.py          # UNCHANGED
├── charts.py          # UNCHANGED
└── rtmcp.css          # UNCHANGED (1493 lines)
```

### Key Routes
```python
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chain")
def api_chain():
    symbol = request.args.get("symbol", "NIFTY")
    chain = client.get_option_chain(symbol)
    html = render_chain(chain)
    return jsonify({"html": html})

@app.route("/api/quote")
def api_quote():
    symbols = request.args.get("symbols", "NIFTY,BANKNIFTY").split(",")
    quotes = [client.get_full_quote(s.strip()) for s in symbols]
    return jsonify({"quotes": quotes})

@app.route("/api/historical")
def api_historical():
    symbol = request.args.get("symbol")
    interval = request.args.get("interval", "day")
    days = int(request.args.get("days", 60))
    candles = client.get_historical_data(symbol, interval, days)
    return jsonify({"candles": candles})
```

### Frontend (JavaScript)
```javascript
// dashboard.js - Replaces NiceGUI timers
setInterval(fetchTickers, 10000);
setInterval(fetchChain, 30000);

async function fetchChain() {
    const resp = await fetch('/api/chain?symbol=NIFTY');
    const data = await resp.json();
    document.getElementById('chain-container').innerHTML = data.html;
}

async function fetchTickers() {
    const resp = await fetch('/api/quote?symbols=NIFTY,BANKNIFTY');
    updateTickerUI(resp.quotes);
}
```

### Benefits
- ✅ Only 103 KB Flask vs 20.3 MB NiceGUI
- ✅ Works with Nuitka compilation
- ✅ Full control over HTML/CSS/JS
- ✅ Proven framework, well-documented

### Drawbacks
- ⚠️ Need to rewrite UI logic (78 NiceGUI calls → vanilla JS)
- ⚠️ Lose auto-reload on code changes
- ⚠️ Need to manage static files manually

---

## Option 3: Keep Current Setup (No Changes)

### Current Commands
```bash
python main.py mcp    # MCP server only (stdio)
python main.py ui     # Dashboard only (NiceGUI)
```

### Pros
- ✅ Works as-is
- ✅ No development needed
- ✅ NiceGUI has built-in auto-refresh

### Cons
- ❌ Can't run both simultaneously
- ❌ Large dependency (NiceGUI 20MB)
- ❌ Hard to compile with Nuitka

---

## Recommended Approach

### Phase 1: Enable Dual HTTP Server (Quick Win)
**Effort:** 30 minutes
**Impact:** AI clients can connect via HTTP

```bash
# Start both servers
python main.py all --mcp-port 8000 --ui-port 8888

# MCP clients connect to
curl http://127.0.0.1:8000/mcp

# Humans open browser
open http://127.0.0.1:8888/
```

### Phase 2: Replace NiceGUI with Flask (Optional)
**Effort:** 2-3 hours
**Impact:** 200x smaller footprint, Nuitka-compatible

---

## Migration Path Options

| Path | Effort | Dependency Size | Nuitka Ready | Dual Server |
|------|--------|-----------------|--------------|-------------|
| **Keep current** | 0 hrs | 20.3 MB | ❌ | ❌ |
| **Dual HTTP (NiceGUI)** | 30 min | 20.3 MB | ❌ | ✅ |
| **Flask + Dual HTTP** | 3 hrs | 150 KB | ✅ | ✅ |

---

## Next Steps

1. **Decide**: Keep NiceGUI or switch to Flask?
2. **If keeping NiceGUI**: Implement Phase 1 (dual HTTP)
3. **If switching to Flask**: Implement Phase 1 + 2 together

**Question for you:**
- Do you want AI clients to connect via HTTP (remote access)?
- Do you want to keep the current NiceGUI dashboard or switch to Flask?
- Do you need Nuitka compilation for distribution?
