// Application bootstrap / orchestration only. Registers the pages, wires the
// top-bar buttons, starts the live ticker, and opens the default page. All real
// logic lives in the page modules and shared components below.

import { registerRoute, initRouter, navigate } from "./router.js";
import { renderTicker } from "./components/ticker.js";
import { createHomePage } from "./pages/home.js";
import { createMarketPage } from "./pages/market.js";
import { createVixPage } from "./pages/vix.js";
import { createUpstoxPage } from "./pages/upstox.js";
import { createChartsHome, createChartsPage } from "./pages/charts.js";
import { createToolsPage } from "./pages/tools.js";
import { TICKER_REFRESH_MS } from "./utils/config.js";

// Register every page once. To add a new page: write pages/foo.js exporting
// createFooPage() and add exactly one line here. Nothing else changes.
// Chain/chart pages are hidden from the top tabs: they live under the "Option
// Chain" / "Charts" header links (overview cards). Upstox is reached via the gear.
registerRoute("home", "Home", function () {
  return createHomePage();
}, { showTab: false, group: "chain" });
registerRoute("nifty", "NIFTY", function () {
  return createMarketPage("NIFTY");
}, { showTab: false, group: "chain" });
registerRoute("banknifty", "BANKNIFTY", function () {
  return createMarketPage("BANKNIFTY");
}, { showTab: false, group: "chain" });
registerRoute("sensex", "SENSEX", function () {
  return createMarketPage("SENSEX");
}, { showTab: false, group: "chain" });
registerRoute("vix", "INDIA VIX", function () {
  return createVixPage();
}, { showTab: false, group: "chart" });
registerRoute("upstox", "Upstox", function () {
  return createUpstoxPage();
}, { showTab: false });
registerRoute("charts", "Charts", function () {
  return createChartsHome();
}, { showTab: false, group: "chart" });
registerRoute("chart-nifty", "NIFTY", function () {
  return createChartsPage("NIFTY");
}, { showTab: false, group: "chart" });
registerRoute("chart-banknifty", "BANKNIFTY", function () {
  return createChartsPage("BANKNIFTY");
}, { showTab: false, group: "chart" });
registerRoute("chart-sensex", "SENSEX", function () {
  return createChartsPage("SENSEX");
}, { showTab: false, group: "chart" });
registerRoute("tools", "Tools", function () {
  return createToolsPage();
}, { showTab: true });

function init() {
  var container = document.querySelector(".rtmcp-content");
  var tabs = document.getElementById("navTabs");
  if (!container || !tabs) return;

  initRouter({ container: container, tabs: tabs });

  document.getElementById("homeBtn").addEventListener("click", function () {
    navigate("home");
  });
  document.getElementById("chainLink").addEventListener("click", function () {
    navigate("home");
  });
  document.getElementById("chartsLink").addEventListener("click", function () {
    navigate("charts");
  });
  document.getElementById("gearBtn").addEventListener("click", function () {
    navigate("upstox");
  });

  renderTicker();
  setInterval(renderTicker, TICKER_REFRESH_MS);

  navigate("home");
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
