// Option-chain (market) page. One factory is instantiated per index symbol
// (NIFTY, BANKNIFTY), proving the "reusable page" pattern: add another index and
// you only add one registerRoute() line in app.js.

import { api } from "../api.js";
import { fmt } from "../utils/format.js";
import { el, setStatusById, injectChainCss } from "../utils/dom.js";
import { statCard, statChip, indicesOptions, intervalOptions, columnsOptions } from "../components/controls.js";
import { renderError } from "../components/error.js";
import { drawCandles } from "../components/chart.js";
import { AUTO_REFRESH_MS, LWC_CHART_HEIGHT, HISTORY_DAYS } from "../utils/config.js";

// Wire an always-visible horizontal scrollbar (proxy) under the chain table.
// The .tbmcp-card is the vertical+horizontal scroll container (which keeps the
// sticky header working), but its native horizontal scrollbar is buried at the
// bottom of a tall card. This proxy sits right under the table and stays in sync.
function setupHScroll(container) {
  var card = container.querySelector(".tbmcp-card");
  if (!card) return;
  var old = container.querySelector(".tbmcp-hscroll");
  if (old) old.parentNode.removeChild(old);

  var proxy = document.createElement("div");
  proxy.className = "tbmcp-hscroll";
  var spacer = document.createElement("div");
  proxy.appendChild(spacer);
  card.parentNode.insertBefore(proxy, card.nextSibling);

  var syncing = false;
  function fromCard() {
    if (syncing) return;
    syncing = true;
    proxy.scrollLeft = card.scrollLeft;
    syncing = false;
  }
  function fromProxy() {
    if (syncing) return;
    syncing = true;
    card.scrollLeft = proxy.scrollLeft;
    syncing = false;
  }
  card.addEventListener("scroll", fromCard);
  proxy.addEventListener("scroll", fromProxy);

  function size() {
    spacer.style.width = card.scrollWidth + "px";
    proxy.style.display = card.scrollWidth > card.clientWidth + 2 ? "block" : "none";
  }
  size();
  if (window.ResizeObserver) new ResizeObserver(size).observe(card);
  window.addEventListener("resize", size);
}

export function createMarketPage(symbol) {
  var autoTimer = null;

  function marketPageHTML() {
    var opts = intervalOptions("day");
    var cols = columnsOptions(2);
    return (
      '<div class="tbmcp-controls-bar">' +
      '<select id="sym-' + symbol + '" class="tbmcp-select tbmcp-sel-sym">' +
      indicesOptions(symbol) + "</select>" +
      '<select id="exp-' + symbol + '" class="tbmcp-select"></select>' +
      '<label class="tbmcp-autorefresh">' +
      '<input type="checkbox" id="auto-' + symbol + '"> Auto-refresh (30s)</label>' +
      '<div class="tbmcp-stats-inline">' +
      statChip("Spot", "spot-" + symbol) +
      statChip("PCR", "pcr-" + symbol) +
      statChip("CE OI", "ceoi-" + symbol) +
      statChip("PE OI", "peoi-" + symbol) +
      statChip("Expiry", "expiry-" + symbol) +
      "</div>" +
      "</div>" +
      '<div class="tbmcp-status" id="status-' + symbol + '"></div>' +
      '<div class="tbmcp-chain" id="chain-' + symbol + '"></div>' +
      '<div class="tbmcp-divider"></div>' +
      '<div class="tbmcp-chart-controls">' +
      '<input type="text" id="chartsym-' + symbol + '" class="tbmcp-input tbmcp-in-chart" value="' + symbol +
      '" placeholder="Chart symbols (comma separated)">' +
      '<select id="chartint-' + symbol + '" class="tbmcp-select">' + opts + "</select>" +
      '<select id="chartcols-' + symbol + '" class="tbmcp-select">' + cols + "</select>" +
      '<button id="chartbtn-' + symbol + '">Update Charts</button>' +
      "</div>" +
      '<div class="tbmcp-chart-grid" id="chartgrid-' + symbol + '"></div>'
    );
  }

  function mount(container) {
    container.innerHTML = marketPageHTML();

    // Auto-update when the index or expiry is picked - no Load button needed.
    el("sym-" + symbol).addEventListener("change", loadChain);
    el("exp-" + symbol).addEventListener("change", loadChain);
    el("auto-" + symbol).addEventListener("change", function (e) {
      toggleAuto(e.target.checked);
    });
    el("chartbtn-" + symbol).addEventListener("click", loadCharts);

    // Initial paint shortly after mount.
    setTimeout(function () {
      loadChain();
      loadCharts();
    }, 300);
  }

  function toggleAuto(on) {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
    if (on) autoTimer = setInterval(loadChain, AUTO_REFRESH_MS);
  }

  function loadChain() {
    var symInput = el("sym-" + symbol);
    var expSel = el("exp-" + symbol);
    var sym = (symInput.value || symbol).trim().toUpperCase();
    var expiry = expSel.value || "";
    setStatusById("status-" + symbol, "Loading…", "");
    api.chain(sym, expiry).then(function (res) {
      if (!res.ok || res.body.error) {
        var nice = renderError(el("chain-" + symbol), res.body.error || "HTTP " + res.status);
        setStatusById("status-" + symbol, nice, "err");
        return;
      }
      var b = res.body;
      if (b.css) injectChainCss(b.css);
      var c = el("chain-" + symbol);
      if (c) {
        c.innerHTML = b.html || "";
        setupHScroll(c);
      }
      if (b.stats) {
        el("spot-" + symbol).textContent = fmt(b.stats.spot, 0);
        el("pcr-" + symbol).textContent = fmt(b.stats.pcr, 2);
        el("ceoi-" + symbol).textContent = fmt(b.stats.ceOi, 0);
        el("peoi-" + symbol).textContent = fmt(b.stats.peOi, 0);
      }
      var expVal = el("expiry-" + symbol);
      if (expVal) expVal.textContent = b.expiryDate || "-";
      // Refresh expiry options (keep current selection if present).
      if (b.expiryDates && expSel) {
        var prev = expSel.value;
        expSel.innerHTML = b.expiryDates
          .map(function (e) {
            return '<option value="' + e + '">' + e + "</option>";
          })
          .join("");
        if (prev) expSel.value = prev;
        else if (b.expiryDate) expSel.value = b.expiryDate;
      }
      setStatusById(
        "status-" + symbol,
        b.timestamp ? "Updated " + String(b.timestamp).replace("T", " ").slice(0, 19) : "Updated",
        "ok"
      );
    }).catch(function (e) {
      var nice = renderError(el("chain-" + symbol), String(e));
      setStatusById("status-" + symbol, nice, "err");
    });
  }

  function loadCharts() {
    var box = el("chartsym-" + symbol);
    var intSel = el("chartint-" + symbol);
    var colsSel = el("chartcols-" + symbol);
    var grid = el("chartgrid-" + symbol);
    if (!box || !grid) return;
    var raw = box.value || symbol;
    var symbols = raw.split(",").map(function (s) {
      return s.trim().toUpperCase();
    }).filter(Boolean);
    var cols = parseInt(colsSel.value, 10) || 2;
    var interval = intSel.value || "day";
    grid.innerHTML = "";
    grid.style.display = "grid";
    grid.style.gridTemplateColumns = "repeat(" + cols + ", minmax(0,1fr))";
    grid.style.gap = "12px";
    grid.style.width = "100%";
    symbols.forEach(function (s, i) {
      var cid = "chart_" + symbol + "_" + i;
      var div = document.createElement("div");
      div.id = cid;
      div.style.width = "100%";
      div.style.height = LWC_CHART_HEIGHT + "px";
      grid.appendChild(div);
      api.history(s, interval, HISTORY_DAYS).then(function (res) {
        var candles = res.ok && res.body ? res.body.candles || [] : [];
        drawCandles(
          cid,
          candles,
          res.body && res.body.error ? res.body.error : null,
          LWC_CHART_HEIGHT
        );
      });
    });
  }

  function refresh() {
    loadChain();
    loadCharts();
  }

  return { mount: mount, refresh: refresh };
}
