// Tiny DOM helpers shared across pages. No framework, no globals leaked to window.

export function el(id) {
  return document.getElementById(id);
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c];
  });
}

// Generic status-line setter. Pass the element id (e.g. "status-NIFTY").
export function setStatusById(id, msg, kind) {
  var s = el(id);
  if (!s) return;
  s.textContent = msg || "";
  s.className = "rtmcp-status " + (kind || "");
}

// Inject the data-driven option-chain colours exactly once for the whole app.
var chainCssInjected = false;
export function injectChainCss(css) {
  if (chainCssInjected) return;
  var st = document.createElement("style");
  st.id = "rtmcp-chain-css";
  st.textContent = css;
  document.head.appendChild(st);
  chainCssInjected = true;
}
