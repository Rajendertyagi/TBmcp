// Centralized client-side routing / navigation.
//
// Pages register themselves with registerRoute(key, label, factory). The router
// builds the nav tabs from that registry and lazily mounts each page into its own
// <section> the first time it is visited (then just shows/hides it afterwards,
// so a page keeps running its auto-refresh timers in the background).
//
// Adding a new page = one registerRoute() call in app.js. Nothing else changes,
// which is what keeps the architecture stable as the app grows to many pages.

import { appState } from "./state.js";

var routeMap = new Map(); // key -> { key, label, factory, page, section, mounted }
var routes = []; // ordered keys (tab order)
var containerEl = null;
var tabsEl = null;

export function registerRoute(key, label, factory, opts) {
  if (routeMap.has(key)) return;
  opts = opts || {};
  routeMap.set(key, {
    key: key,
    label: label,
    factory: factory,
    showTab: opts.showTab !== false,
    group: opts.group || "misc",
    page: null,
    section: null,
    mounted: false,
  });
  routes.push(key);
}

export function initRouter(opts) {
  containerEl = opts.container;
  tabsEl = opts.tabs;
  renderTabs();
  tabsEl.addEventListener("click", function (e) {
    var t = e.target.closest(".rtmcp-tab");
    if (t) navigate(t.dataset.page);
  });
}

function renderTabs() {
  tabsEl.innerHTML = routes.filter(function (k) {
    return routeMap.get(k).showTab;
  }).map(function (k) {
    var r = routeMap.get(k);
    return '<div class="rtmcp-tab" data-page="' + k + '">' + r.label + "</div>";
  }).join("");
}

export function navigate(key) {
  var r = routeMap.get(key);
  if (!r) return;

  // Lazily create the section + instantiate the page module on first visit.
  if (!r.section) {
    var sec = document.createElement("section");
    sec.className = "page";
    sec.id = "page-" + key;
    containerEl.appendChild(sec);
    r.section = sec;
    r.page = r.factory();
  }

  // Show only the active section.
  routeMap.forEach(function (other) {
    if (other.section) other.section.style.display = other.key === key ? "block" : "none";
  });

  // Highlight the active tab.
  tabsEl.querySelectorAll(".rtmcp-tab").forEach(function (t) {
    t.classList.toggle("active", t.dataset.page === key);
  });

  if (!r.mounted) {
    r.page.mount(r.section);
    r.mounted = true;
  }
  appState.currentRoute = key;
  if (typeof r.page.onShow === "function") r.page.onShow();
}

// Re-run the current page's refresh (used after e.g. a successful Upstox login).
export function refreshCurrent() {
  var r = routeMap.get(appState.currentRoute);
  if (r && r.page && typeof r.page.refresh === "function") r.page.refresh();
}

export function current() {
  return appState.currentRoute;
}

// All registered routes as [{ key, label }], in tab order. Pass a group to
// limit to e.g. "chain" or "chart" pages. Used by the overview pages to build
// their navigation cards without hardcoding the page list.
export function listRoutes(group) {
  return routes
    .map(function (k) {
      return routeMap.get(k);
    })
    .filter(function (r) {
      return !group || r.group === group;
    })
    .map(function (r) {
      return { key: r.key, label: r.label };
    });
}
