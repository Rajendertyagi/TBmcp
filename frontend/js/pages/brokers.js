// Broker login landing page (opened from the gear icon). Shows one card per
// broker in the same card style as the other overview pages; each card opens
// that broker's dedicated setup/login page.

import { navigate } from "../router.js";
import { api } from "../api.js";
import { el } from "../utils/dom.js";

var BROKERS = [
  { key: "upstox", title: "Upstox", desc: "Primary broker — option chain, quotes, fundamentals, orders." },
  { key: "fyers", title: "FYERS", desc: "Secondary data-only broker — option chain, quotes, depth, history, Greeks." },
];

function cardHtml(b) {
  return (
    '<button class="tbmcp-home-card" data-page="' + b.key + '">' +
    '<span class="tbmcp-home-card-title">' + b.title + "</span>" +
    '<span class="tbmcp-home-card-desc">' + b.desc + "</span>" +
    '<span class="tbmcp-status" id="status-' + b.key + '"></span>' +
    '<span class="tbmcp-home-card-go">Open &rarr;</span>' +
    "</button>"
  );
}

function setStatus(key, connected) {
  var node = el("status-" + key);
  if (!node) return;
  node.textContent = connected ? "Connected" : "Not connected";
  node.style.color = connected ? "var(--success)" : "var(--danger)";
}

export function createBrokersPage() {
  function mount(container) {
    container.innerHTML =
      '<div class="tbmcp-home">' +
      '<h1 class="tbmcp-home-title">Broker Login &amp; Settings</h1>' +
      '<p class="tbmcp-home-sub">Pick a broker to manage its connection.</p>' +
      '<div class="tbmcp-home-grid">' +
      BROKERS.map(cardHtml).join("") +
      "</div>" +
      "</div>";

    container.querySelectorAll(".tbmcp-home-card").forEach(function (btn) {
      btn.addEventListener("click", function () { navigate(btn.dataset.page); });
    });

    api.loginStatus().then(function (res) {
      if (res.ok && res.body) setStatus("upstox", res.body.connected);
    });
    api.fyersLoginStatus().then(function (res) {
      if (res.ok && res.body) setStatus("fyers", res.body.connected);
    });
  }

  return { mount: mount };
}

