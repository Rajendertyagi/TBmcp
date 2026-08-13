// Number formatting helpers (Indian locale, fixed decimals).

export function fmt(n, d) {
  d = d === undefined ? 2 : d;
  if (n === null || n === undefined || isNaN(n)) return "-";
  return Number(n).toLocaleString("en-IN", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}
