// Friendly error display. Turns a raw upstream error into a calm message and
// renders the "No data" empty state used by the option-chain page.

import { escapeHtml } from "../utils/dom.js";

export function cleanError(msg) {
  if (!msg) return "Unknown error";
  var m = msg.match(/No option expiries found for '([^']+)'/);
  if (m) return "No option-chain data available for " + m[1] + " from Upstox.";
  return msg;
}

// Renders the empty-state panel into `container` and returns the cleaned message
// (so the caller can also show it in a status line).
export function renderError(container, msg) {
  var nice = cleanError(msg);
  if (container) {
    container.innerHTML =
      '<div class="rtmcp-empty-state"><div class="icon">&#128202;</div>' +
      "<h3>No data</h3><p>" + escapeHtml(nice) + "</p></div>";
  }
  return nice;
}
