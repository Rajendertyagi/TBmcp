# Flask vs Falcon vs Litestar vs Bottle - Comparison for TBMCP Dashboard

## Quick Stats

| Framework | Size | Stars | License | Async | Template Engine | Dependencies |
|-----------|------|-------|---------|-------|-----------------|--------------|
| **Flask** | 103 KB | ~65k | BSD-3 | ❌ (via extensions) | Jinja2 (built-in) | Werkzeug, Jinja2, Click |
| **Falcon** | 332 KB | 9.8k | Apache-2.0 | ✅ (ASGI) | None (API-only) | None |
| **Litestar** | 581 KB | 8.4k | MIT | ✅ (ASGI) | Jinja2 (optional) | msgspec, pydantic |
| **Bottle** | 103 KB | 8.8k | MIT | ❌ | SimpleTemplate | None |

---

## Code Comparison

### Hello World

**Flask:**
```python
from flask import Flask, render_template, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def get_data():
    return jsonify({"message": "Hello"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8888)
```

**Falcon:**
```python
import falcon

class IndexResource:
    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200
        resp.content_type = "text/html"
        resp.text = open("index.html").read()

class DataResource:
    def on_get(self, req, resp):
        resp.media = {"message": "Hello"}

app = falcon.App()
app.add_route("/", IndexResource())
app.add_route("/api/data", DataResource())
```

**Litestar:**
```python
from litestar import Litestar, get
from litestar.response import Template
from litestar.template.config import TemplateConfig

@get("/", sync_to_thread=False)
async def index() -> Template:
    return Template(template_name="index.html")

@get("/api/data", sync_to_thread=False)
async def get_data() -> dict:
    return {"message": "Hello"}

app = Litestar([index, get_data])
```

**Bottle:**
```python
from bottle import route, run, template, jsonify

@route("/")
def index():
    return template("index")

@route("/api/data")
def get_data():
    return jsonify({"message": "Hello"})

run(host="127.0.0.1", port=8888)
```

---

## For Your Trading Dashboard

| Feature | Flask | Falcon | Litestar | Bottle |
|---------|-------|--------|----------|--------|
| **Web Templates** | ✅ Jinja2 (built-in) | ❌ API-only | ✅ Optional | ✅ SimpleTemplate |
| **Static Files** | ✅ | ❌ (use server) | ✅ | ✅ |
| **Session/Cookies** | ✅ | ⚠️ Manual | ✅ | ✅ |
| **WebSocket** | ❌ (need extension) | ✅ | ✅ | ❌ |
| **OAuth Flow** | ✅ Easy | ⚠️ Manual | ✅ | ⚠️ Manual |
| **Auto-reload** | ✅ `debug=True` | ❌ | ❌ | ✅ `auto_reload` |
| **Nuitka Compatible** | ✅ | ✅ | ⚠️ Complex | ✅ |
| **Learning Curve** | Low | Medium | High | Low |

---

## My Recommendation

### **Flask** - Best Choice for Your Use Case

**Why:**
1. **Template support** - You need to serve HTML pages with tbmcp.css
2. **Simple** - Minimal code to serve static files + render templates
3. **Self-contained** - No extra dependencies beyond Flask itself
4. **Nuitka friendly** - No complex typing or plugins
5. **Proven** - Most Python web framework, tons of examples

**Minimal Flask implementation:**
```python
from flask import Flask, render_template, jsonify, request
import os

app = Flask(__name__, static_folder="static", template_folder="templates")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chain")
def get_chain():
    symbol = request.args.get("symbol", "NIFTY")
    expiry = request.args.get("expiry")
    # Call existing client.py logic
    chain = client.get_option_chain(symbol, expiry)
    return jsonify(chain.to_dict())

@app.route("/api/quote")
def get_quote():
    symbols = request.args.get("symbols", "NIFTY,BANKNIFTY").split(",")
    # Return formatted ticker data
    ...

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8888, debug=True)
```

---

### When to Consider Others

| Choose | When |
|--------|------|
| **Falcon** | You only need API endpoints (no HTML pages) |
| **Litestar** | You want strong typing, auto-OpenAPI docs |
| **Bottle** | You want single-file deployment, no pip install |

---

## Migration Effort Estimate

| Task | Flask | Falcon | Litestar |
|------|-------|--------|----------|
| Server setup | 30 min | 1 hour | 2 hours |
| Template rendering | 15 min | ❌ Not possible | 30 min |
| API endpoints | 1 hour | 30 min | 1 hour |
| **Total** | **~2 hours** | **~1.5 hours** | **~3 hours** |

---

## Success Criteria

1. Dashboard loads at `http://127.0.0.1:8888/`
2. Option chain displays with existing tbmcp.css
3. Auto-refresh works via JavaScript fetch
4. Charts render (lightweight-charts)
5. Upstox login flow completes
6. Package reduced from 20MB to ~200KB

**Recommendation: Start with Flask.** Simplest path to working dashboard.
