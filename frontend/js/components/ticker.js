// Top-bar live ticker. Reads from /api/ticker and paints the running quotes.

import { api } from "../api.js";
import { fmt } from "../utils/format.js";
import { el } from "../utils/dom.js";

export function renderTicker() {
  api.ticker().then(function (res) {
    var tick = el("ticker");
    if (!tick) return;
    var body = res.body || [];
    if (!res.ok || !body.length) {
      tick.innerHTML = '<span class="rtmcp-ticker-card">No ticker data</span>';
      return;
    }
    tick.innerHTML = body.map(function (q) {
      var up = q.net_change >= 0;
      var color = up ? "#1b8a3b" : "#c0392b";
      var arrow = up ? "▲" : "▼";
      var sign = up ? "+" : "";
      return (
        '<div class="rtmcp-ticker-card">' +
        '<div class="rtmcp-ticker-inner rtmcp-ticker-stack">' +
        '<span class="rtmcp-ticker-name">' + q.symbol + "</span>" +
        '<span class="rtmcp-ticker-line2">' +
        '<span class="rtmcp-ticker-last">' + fmt(q.last_price) + "</span>" +
        '<span class="rtmcp-ticker-chg" style="color:' + color + ';">' +
        arrow + " " + sign + fmt(q.net_change) + " (" + sign + fmt(q.p_change, 2) + "%)</span>" +
        "</span></div></div>"
      );
    }).join("");
  });
}
