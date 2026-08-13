// Centralized API communication. Every page talks to the Falcon backend through
// this module so the endpoint URLs, error shape, and JSON handling live in ONE
// place. Pages never call fetch() directly.

var enc = encodeURIComponent;

// Low-level request: always returns { ok, status, body } so callers can check
// both HTTP status and the body's own { error: ... } field uniformly.
async function request(path, opts) {
  opts = opts || {};
  try {
    var r = await fetch(path, opts);
    var body = {};
    try {
      body = await r.json();
    } catch (e) {
      // Response had no JSON body; leave body empty.
    }
    return { ok: r.ok, status: r.status, body: body };
  } catch (e) {
    return { ok: false, status: 0, body: { error: String(e) } };
  }
}

export var api = {
  async ticker() {
    return request("/api/ticker");
  },

  async chain(symbol, expiry) {
    var q = expiry
      ? "?symbol=" + enc(symbol) + "&expiry=" + enc(expiry)
      : "?symbol=" + enc(symbol);
    return request("/api/chain" + q);
  },

  async quote(symbol) {
    return request("/api/quote?symbol=" + enc(symbol));
  },

  async expiries(symbol) {
    return request("/api/expiries?symbol=" + enc(symbol));
  },

  async history(symbol, interval, days) {
    return request(
      "/api/history?symbol=" + enc(symbol) +
      "&interval=" + enc(interval) + "&days=" + days
    );
  },

  async vix() {
    return request("/api/vix");
  },

  async testAll(symbol) {
    return request("/api/test-all?symbol=" + enc(symbol || "NIFTY"));
  },

  async getSettings() {
    return request("/api/settings");
  },

  async saveSettings(payload) {
    return request("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async loginUrl(key, redirect) {
    return request("/api/login-url?key=" + enc(key) + "&redirect=" + enc(redirect));
  },

  async login(code, redirect) {
    return request("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code, redirect_uri: redirect }),
    });
  },

  async loginStatus() {
    return request("/api/login-status");
  },

  async fundamentals(symbol, endpoint) {
    var q = "?symbol=" + enc(symbol) + "&endpoint=" + enc(endpoint);
    return request("/api/fundamentals" + q);
  },

  async news(symbol) {
    return request("/api/news?symbol=" + enc(symbol));
  },

  async greeks(symbol, expiry) {
    var q = "?symbol=" + enc(symbol);
    if (expiry) q += "&expiry=" + enc(expiry);
    return request("/api/greeks" + q);
  },
};
