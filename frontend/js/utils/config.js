// Shared frontend configuration. Mirrors the relevant Python constants so the
// two sides stay in sync without hard-coding magic numbers in every page.

export const TICKER_REFRESH_MS = 10000;
export const AUTO_REFRESH_MS = 30000;
export const LWC_CHART_HEIGHT = 420;
export const HISTORY_DAYS = 60;
export const VIX_HISTORY_DAYS = 180;

// Chart interval options offered in the dropdown(s).
export const INTERVALS = {
  day: "Daily",
  "1minute": "1 min",
  "30minute": "30 min",
  week: "Weekly",
  month: "Monthly",
};

// Indices offered in the symbol dropdown (those with an option chain on Upstox).
export const MAJOR_INDICES = ["NIFTY", "BANKNIFTY", "SENSEX"];
