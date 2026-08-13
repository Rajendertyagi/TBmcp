// Reusable form controls shared by pages (stat cards + dropdown option builders).

import { INTERVALS, MAJOR_INDICES } from "../utils/config.js";

export function statCard(label, id) {
  return (
    '<div class="tbmcp-stat-card">' +
    '<div class="tbmcp-stat-label">' + label + "</div>" +
    '<div class="tbmcp-stat-value" id="' + id + '">---</div></div>'
  );
}

export function statChip(label, id) {
  return (
    '<div class="tbmcp-stat-chip">' +
    '<span class="tbmcp-stat-chip-label">' + label + "</span>" +
    '<span class="tbmcp-stat-chip-value" id="' + id + '">---</span></div>'
  );
}

export function indicesOptions(selected) {
  return MAJOR_INDICES.map(function (s) {
    var sel = s === selected ? " selected" : "";
    return '<option value="' + s + '"' + sel + ">" + s + "</option>";
  }).join("");
}

export function intervalOptions(selected) {
  selected = selected || "day";
  return Object.keys(INTERVALS).map(function (k) {
    var sel = k === selected ? " selected" : "";
    return '<option value="' + k + '"' + sel + ">" + INTERVALS[k] + "</option>";
  }).join("");
}

export function columnsOptions(selected) {
  selected = selected || 2;
  return [1, 2, 3, 4].map(function (n) {
    var sel = n === selected ? " selected" : "";
    return '<option value="' + n + '"' + sel + ">" + n + " column" + (n > 1 ? "s" : "") + "</option>";
  }).join("");
}
