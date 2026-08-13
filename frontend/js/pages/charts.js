// Charts section: an overview page (cards linking to each symbol's chart) plus
// a per-symbol candlestick chart page. Mirrors the option-chain structure so the
// two header links behave the same way.

import { navigate, listRoutes } from "../router.js";
import { api } from "../api.js";
import { drawCandles } from "../components/chart.js";
import { intervalOptions } from "../components/controls.js";
import { HISTORY_DAYS, LWC_CHART_HEIGHT } from "../utils/config.js";

// Overview: one card per "chart" route (excluding this overview itself).
export function createChartsHome() {
  function html() {
    var links = listRoutes("chart").filter(function (r) {
      return r.key !== "charts";
    });
    var cards = links.map(function (r) {
      return (
        '<button class="tbmcp-home-card" data-page="' + r.key + '">' +
        '<span class="tbmcp-home-card-title">' + r.label + " Chart</span>" +
        '<span class="tbmcp-home-card-desc">Candlestick chart for ' + r.label + ".</span>" +
        '<span class="tbmcp-home-card-go">Open &rarr;</span>' +
        "</button>"
      );
    }).join("");
    return (
      '<div class="tbmcp-home">' +
      '<h1 class="tbmcp-home-title">Charts</h1>' +
      '<p class="tbmcp-home-sub">Pick an index to view its chart.</p>' +
      '<div class="tbmcp-home-grid">' + cards + "</div>" +
      "</div>"
    );
  }

  function mount(container) {
    container.innerHTML = html();
    container.querySelectorAll(".tbmcp-home-card").forEach(function (btn) {
      btn.addEventListener("click", function () {
        navigate(btn.dataset.page);
      });
    });
  }

  return { mount: mount };
}

// Single-symbol candlestick chart with an interval selector.
export function createChartsPage(symbol) {
  function html() {
    return (
      '<div class="tbmcp-chart-page">' +
      '<div class="tbmcp-controls-bar">' +
      '<select id="chartint-' + symbol + '" class="tbmcp-select">' +
      intervalOptions("day") +
      "</select>" +
      "</div>" +
      '<div id="chart-' + symbol + '" class="tbmcp-chart-canvas"></div>' +
      "</div>"
    );
  }

  function mount(container) {
    container.innerHTML = html();
    var sel = container.querySelector("#chartint-" + symbol);

    function load() {
      var interval = sel.value || "day";
      api.history(symbol, interval, HISTORY_DAYS).then(function (res) {
        var candles = res.ok && res.body ? res.body.candles || [] : [];
        drawCandles(
          "chart-" + symbol,
          candles,
          res.body && res.body.error ? res.body.error : null,
          LWC_CHART_HEIGHT
        );
      });
    }

    sel.addEventListener("change", load);
    load();
  }

  return { mount: mount };
}
