// Tools test page: one click runs every new Market-Info / analytics tool and
// shows each result (pass/fail + raw JSON) so a human can verify them in the
// browser without going through the MCP side.

import { api } from "../api.js";
import { el, escapeHtml } from "../utils/dom.js";

var TOOL_ORDER = [
  // Raw market data (no chain needed)
  "spot_price", "full_quote", "full_quotes", "historical_data",
  "market_depth", "fii", "dii", "market_status", "market_holidays",
  "market_timings", "instruments", "futures_chain", "margin",
  // Expiry-dependent raw tools
  "option_chain", "pcr", "max_pain", "oi", "change_oi",
  // Fundamentals (stock profile / ownership / financials)
  "company_profile", "share_holdings", "key_ratios", "corporate_actions",
  "competitors", "news",
  // Analytics (compute_*)
  "compute_pcr", "compute_max_pain", "compute_top_oi_strikes", "compute_atm",
  "compute_iv_skew", "compute_oi_buildup", "compute_support_resistance",
  "compute_straddle", "compute_gex", "compute_futures_basis",
  // Strategy pricers (price_*)
  "price_long_straddle", "price_long_strangle", "price_bull_call_spread",
  "price_bear_put_spread", "price_iron_condor", "price_long_butterfly",
];

// Common symbols offered as an autocomplete so a typo (e.g. BANKBIFTY) can't
// silently produce empty/skipped results. INDIAVIX is excluded on purpose:
// it's a volatility index with no options/futures of its own, so most tools
// would just skip/empty for it and give a false impression of failure.
// Indices first, then liquid stock F&O underlyings (typed freely too).
var INDEX_SYMBOLS = [
  "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX",
];
var STOCK_SYMBOLS = [
  "RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
  "ITC", "KOTAKBANK", "LT", "AXISBANK", "WIPRO", "MARUTI", "TATAMOTORS",
  "TATASTEEL", "HCLTECH", "SUNPHARMA", "BAJFINANCE", "BAJAJFINSV",
  "ASIANPAINT", "TITAN", "ADANIENT", "ONGC", "NTPC", "POWERGRID",
];
var KNOWN_SYMBOLS = INDEX_SYMBOLS.concat(STOCK_SYMBOLS);

export function createToolsPage() {
  function html() {
    var opts = KNOWN_SYMBOLS.map(function (s) {
      return '<li class="rtmcp-combo-opt" data-sym="' + s + '">' + s + "</li>";
    }).join("");
    return (
      '<div class="rtmcp-controls-bar">' +
      '<div class="rtmcp-combo">' +
      '<input type="text" id="tools-sym" class="rtmcp-input" value="NIFTY" placeholder="Symbol (e.g. NIFTY)" autocomplete="off">' +
      '<ul class="rtmcp-combo-list" id="tools-sym-list">' + opts + "</ul>" +
      "</div>" +
      '<button id="tools-run">Run All Tests</button>' +
      "</div>" +
      '<div class="rtmcp-status" id="tools-status"></div>' +
      '<div class="rtmcp-tools-summary" id="tools-summary"></div>' +
      '<div class="rtmcp-tools-grid" id="tools-results"></div>'
    );
  }

  function renderCard(name, entry) {
    var ok = entry && entry.ok;
    var badge = ok
      ? '<span class="rtmcp-badge ok">OK</span>'
      : '<span class="rtmcp-badge err">ERROR</span>';
    var body;
    if (ok) {
      try {
        body = JSON.stringify(entry.data, null, 2);
      } catch (e) {
        body = String(entry.data);
      }
    } else {
      body = entry && entry.error ? String(entry.error) : "no result";
    }
    return (
      '<div class="rtmcp-tool-card">' +
      '<div class="rtmcp-tool-head"><span class="rtmcp-tool-name">' +
      escapeHtml(name) + "</span>" + badge + "</div>" +
      '<pre class="rtmcp-json">' + escapeHtml(body) + "</pre>" +
      "</div>"
    );
  }

  function openCombo() {
    var input = el("tools-sym");
    var list = el("tools-sym-list");
    input.value = "";
    renderComboOptions("");
    list.classList.add("open");
  }

  function renderComboOptions(filter) {
    var list = el("tools-sym-list");
    var f = (filter || "").trim().toUpperCase();
    var items = list.querySelectorAll(".rtmcp-combo-opt");
    items.forEach(function (li) {
      var show = !f || li.getAttribute("data-sym").indexOf(f) !== -1;
      li.style.display = show ? "" : "none";
    });
  }

  function closeCombo() {
    el("tools-sym-list").classList.remove("open");
  }

  function mount(container) {
    container.innerHTML = html();
    var input = el("tools-sym");
    var list = el("tools-sym-list");

    input.addEventListener("focus", openCombo);
    input.addEventListener("click", openCombo);
    input.addEventListener("input", function () {
      renderComboOptions(input.value);
      list.classList.add("open");
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        if (list.classList.contains("open")) {
          var first = list.querySelector('.rtmcp-combo-opt:not([style*="display: none"])');
          if (first) { input.value = first.getAttribute("data-sym"); closeCombo(); }
        }
        run();
      }
    });
    list.addEventListener("mousedown", function (e) {
      var li = e.target.closest(".rtmcp-combo-opt");
      if (!li) return;
      e.preventDefault();
      input.value = li.getAttribute("data-sym");
      closeCombo();
    });
    input.addEventListener("blur", function () {
      setTimeout(closeCombo, 150);
    });

    el("tools-run").addEventListener("click", run);
  }

  function run() {
    var sym = (el("tools-sym").value || "NIFTY").trim().toUpperCase();
    var status = el("tools-status");
    var summary = el("tools-summary");
    var results = el("tools-results");
    status.textContent = "Running all tools for " + sym + " …";
    status.className = "rtmcp-status";
    summary.textContent = "";
    results.innerHTML = "";
    api.testAll(sym).then(function (res) {
      if (!res.ok || (res.body && res.body.error)) {
        status.textContent = "Request failed: " + ((res.body && res.body.error) || ("HTTP " + res.status));
        status.className = "rtmcp-status err";
        return;
      }
      var b = res.body || {};
      var r = b.results || {};
      var passed = 0, failed = 0;
      TOOL_ORDER.forEach(function (name) {
        if (!(name in r)) return;
        if (r[name].ok) passed++; else failed++;
        results.insertAdjacentHTML("beforeend", renderCard(name, r[name]));
      });
      Object.keys(r).forEach(function (name) {
        if (TOOL_ORDER.indexOf(name) !== -1) return;
        if (r[name].ok) passed++; else failed++;
        results.insertAdjacentHTML("beforeend", renderCard(name, r[name]));
      });
      summary.innerHTML =
        '<span class="rtmcp-pill ok">' + passed + " passed</span>" +
        '<span class="rtmcp-pill err">' + failed + " failed</span>" +
        (b.expiry ? '<span class="rtmcp-pill">expiry ' + escapeHtml(b.expiry) + "</span>" : "") +
        '<span class="rtmcp-pill">date ' + escapeHtml(b.date || "") + "</span>";
      status.textContent = "Done for " + sym + ".";
      status.className = "rtmcp-status ok";
    }).catch(function (e) {
      status.textContent = "Error: " + String(e);
      status.className = "rtmcp-status err";
    });
  }

  return { mount: mount };
}
