// Landing / index page: a single place that links to every module so the app is
// easy to navigate. Cards are generated from the router's route registry, so
// adding a page in app.js automatically adds a card here.

import { navigate, listRoutes } from "../router.js";

var DESCRIPTIONS = {
  nifty: "NIFTY option chain with OI, Greeks and buildup.",
  banknifty: "BANKNIFTY option chain with OI, Greeks and buildup.",
  sensex: "SENSEX option chain with OI, Greeks and buildup.",
  vix: "India VIX chart and history.",
  upstox: "Upstox API connection and settings.",
};

export function createHomePage() {
  function homeHTML() {
    var links = listRoutes("chain").filter(function (r) {
      return r.key !== "home";
    });
    var cards = links.map(function (r) {
      var desc = DESCRIPTIONS[r.key] || "Open module.";
      return (
        '<button class="tbmcp-home-card" data-page="' + r.key + '">' +
        '<span class="tbmcp-home-card-title">' + r.label + "</span>" +
        '<span class="tbmcp-home-card-desc">' + desc + "</span>" +
        '<span class="tbmcp-home-card-go">Open &rarr;</span>' +
        "</button>"
      );
    }).join("");
    return (
      '<div class="tbmcp-home">' +
      '<h1 class="tbmcp-home-title">Option Chain</h1>' +
      '<p class="tbmcp-home-sub">Pick an index to view its option chain.</p>' +
      '<div class="tbmcp-home-grid">' + cards + "</div>" +
      "</div>"
    );
  }

  function mount(container) {
    container.innerHTML = homeHTML();
    container.querySelectorAll(".tbmcp-home-card").forEach(function (btn) {
      btn.addEventListener("click", function () {
        navigate(btn.dataset.page);
      });
    });
  }

  return { mount: mount };
}
