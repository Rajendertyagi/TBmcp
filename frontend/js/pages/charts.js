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
        '<button class="rtmcp-home-card" data-page="' + r.key + '">' +
        '<span class="rtmcp-home-card-title">' + r.label + " Chart</span>" +
        '<span class="rtmcp-home-card-desc">Candlestick chart for ' + r.label + ".</span>" +
        '<span class="rtmcp-home-card-go">Open &rarr;</span>' +
        "</button>"
      );
    }).join("");
    return (
      '<div class="rtmcp-home">' +
      '<h1 class="rtmcp-home-title">Charts</h1>' +
      '<p class="rtmcp-home-sub">Pick an index to view its chart.</p>' +
      '<div class="rtmcp-home-grid">' + cards + "</div>" +
      "</div>"
    );
  }

  function mount(container) {
    container.innerHTML = html();
    container.querySelectorAll(".rtmcp-home-card").forEach(function (btn) {
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
      '<div class="rtmcp-chart-page">' +
      '<div class="rtmcp-controls-bar">' +
      '<select id="chartint-' + symbol + '" class="rtmcp-select">' +
      intervalOptions("day") +
      "</select>" +
      "</div>" +
      '<div id="chart-' + symbol + '" class="rtmcp-chart-canvas"></div>' +
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
