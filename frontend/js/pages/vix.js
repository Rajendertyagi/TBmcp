// INDIA VIX page: live VIX quote + its historical chart.

import { api } from "../api.js";
import { fmt } from "../utils/format.js";
import { el } from "../utils/dom.js";
import { intervalOptions } from "../components/controls.js";
import { drawCandles } from "../components/chart.js";
import { LWC_CHART_HEIGHT, VIX_HISTORY_DAYS, TICKER_REFRESH_MS } from "../utils/config.js";

export function createVixPage() {
  function mount(container) {
    container.innerHTML =
      '<div class="tbmcp-vix-hero">' +
      '<span class="tbmcp-vix-title">India VIX</span>' +
      '<span class="tbmcp-vix-value" id="vix-value">---</span>' +
      '<span class="tbmcp-vix-change" id="vix-change"></span>' +
      "</div>" +
      '<div class="flex items-center gap-4" style="margin:12px 0;flex-wrap:wrap;">' +
      '<select id="vixint" class="tbmcp-select">' + intervalOptions("day") + "</select>" +
      '<button id="vixchartbtn">Update Chart</button>' +
      "</div>" +
      '<div id="vixchart" style="width:100%;height:' + (LWC_CHART_HEIGHT + 40) + 'px;"></div>';

    el("vixchartbtn").addEventListener("click", updateVixChart);
    setTimeout(updateVix, 300);
    setTimeout(updateVixChart, 500);
    // Keep the quote live while the app runs (mirrors the original global interval).
    setInterval(updateVix, TICKER_REFRESH_MS);
  }

  function updateVix() {
    api.vix().then(function (res) {
      if (!res.ok || res.body.error) {
        el("vix-value").textContent = "---";
        return;
      }
      var q = res.body;
      el("vix-value").textContent = fmt(q.last_price, 2);
      var up = q.net_change >= 0;
      var color = up ? "#1b8a3b" : "#c0392b";
      var arrow = up ? "▲" : "▼";
      var sign = up ? "+" : "";
      el("vix-change").textContent =
        arrow + " " + sign + fmt(q.net_change, 2) + " (" + sign + fmt(q.p_change, 2) + "%)";
      el("vix-change").style.color = color;
    });
  }

  function updateVixChart() {
    var intSel = el("vixint");
    var interval = intSel ? intSel.value : "day";
    api.history("INDIAVIX", interval, VIX_HISTORY_DAYS).then(function (res) {
      var candles = res.ok && res.body ? res.body.candles || [] : [];
      drawCandles(
        "vixchart",
        candles,
        res.body && res.body.error ? res.body.error : null,
        LWC_CHART_HEIGHT + 40
      );
    });
  }

  function onShow() {
    updateVix();
    updateVixChart();
  }

  function refresh() {
    updateVix();
    updateVixChart();
  }

  return { mount: mount, onShow: onShow, refresh: refresh };
}
