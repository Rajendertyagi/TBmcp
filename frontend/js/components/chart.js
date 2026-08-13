// Candlestick chart wrapper around the bundled lightweight-charts library.
// `LightweightCharts` is a global provided by /static/vendor/lightweight-charts.js
// (loaded as a classic script before the module entry point).

export function drawCandles(cid, candles, error, height) {
  var elc = document.getElementById(cid);
  if (!elc) return;
  if (error) {
    elc.innerHTML = '<div style="color:#c0392b;padding:16px;">Chart error: ' + error + "</div>";
    return;
  }
  if (!candles || !candles.length) {
    elc.innerHTML =
      '<div style="color:#9ca3af;padding:16px;">No historical data available for this symbol.</div>';
    return;
  }
  try {
    var chart = LightweightCharts.createChart(elc, {
      height: height || elc.clientHeight || 420,
      layout: { background: { color: "#0d1117" }, textColor: "#d1d5db" },
      grid: { vertLines: { color: "#1f2937" }, horzLines: { color: "#1f2937" } },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: { borderColor: "#374151" },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });
    var series = chart.addCandlestickSeries({
      upColor: "#1b8a3b",
      downColor: "#c0392b",
      borderVisible: false,
      wickUpColor: "#1b8a3b",
      wickDownColor: "#c0392b",
    });
    series.setData(
      candles.map(function (c) {
        return { time: c.time, open: c.open, high: c.high, low: c.low, close: c.close };
      })
    );
    chart.timeScale().fitContent();
    window.addEventListener("resize", function () {
      chart.applyOptions({ width: elc.clientWidth });
    });
    chart.applyOptions({ width: elc.clientWidth });
  } catch (e) {
    elc.innerHTML = '<div style="color:#c0392b;padding:16px;">Chart error: ' + e.message + "</div>";
  }
}
