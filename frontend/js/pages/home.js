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
        '<button class="rtmcp-home-card" data-page="' + r.key + '">' +
        '<span class="rtmcp-home-card-title">' + r.label + "</span>" +
        '<span class="rtmcp-home-card-desc">' + desc + "</span>" +
        '<span class="rtmcp-home-card-go">Open &rarr;</span>' +
        "</button>"
      );
    }).join("");
    return (
      '<div class="rtmcp-home">' +
      '<h1 class="rtmcp-home-title">Option Chain</h1>' +
      '<p class="rtmcp-home-sub">Pick an index to view its option chain.</p>' +
      '<div class="rtmcp-home-grid">' + cards + "</div>" +
      "</div>"
    );
  }

  function mount(container) {
    container.innerHTML = homeHTML();
    container.querySelectorAll(".rtmcp-home-card").forEach(function (btn) {
      btn.addEventListener("click", function () {
        navigate(btn.dataset.page);
      });
    });
  }

  return { mount: mount };
}
