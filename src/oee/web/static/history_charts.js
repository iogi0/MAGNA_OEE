// Grafy Production History (TASK §8.2, §8.3). Čísla z PeriodAnalytics (JSON v stránke) — JS iba kreslí.
(function () {
  "use strict";
  const source = document.getElementById("history-data");
  if (!source || typeof Chart === "undefined") return;
  const data = JSON.parse(source.textContent);

  const css = getComputedStyle(document.documentElement);
  const color = (name, fallback) => (css.getPropertyValue(name) || fallback).trim();
  const muted = color("--pico-muted-color", "#888");
  const good = color("--pico-ins-color", "#2a7");
  const bad = color("--pico-del-color", "#c33");
  const primary = color("--pico-primary", "#1095c1");
  const percent = (share) => (share === null ? null : share * 100); // podiel → % na osi grafu
  const fmt = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });
  Chart.defaults.color = muted;

  // Čiara cieľa OEE cez celú šírku, popis v pravom okraji (rovnako ako Shift Dashboard).
  const refLine = {
    id: "refLine",
    afterDatasetsDraw(chart, _args, opts) {
      if (opts.value === null || opts.value === undefined) return;
      const { ctx, chartArea } = chart;
      const y = chart.scales.y.getPixelForValue(opts.value);
      ctx.save();
      ctx.strokeStyle = bad;
      ctx.setLineDash([6, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();
      ctx.font = "600 11px system-ui, sans-serif";
      ctx.fillStyle = bad;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      opts.label.split("\n").forEach((line, i) => ctx.fillText(line, chartArea.right + 6, y + (i ? 7 : -7)));
      ctx.restore();
    },
  };
  const goalLabel = "OEE goal\n" + fmt.format(percent(data.goal)) + " %";
  const yAxis = { beginAtZero: true, suggestedMax: 100, title: { display: true, text: "%" } };

  const shiftCanvas = document.getElementById("shift-oee-chart");
  if (shiftCanvas) {
    new Chart(shiftCanvas, {
      type: "bar",
      data: {
        labels: data.shifts.map((s) => s.label),
        datasets: [
          {
            data: data.shifts.map((s) => percent(s.oee)),
            backgroundColor: data.shifts.map((s) => (s.status === "below_goal" ? bad : good)),
            borderRadius: 3,
            barPercentage: 0.7,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        layout: { padding: { right: 62 } },
        scales: { y: yAxis },
        onClick: (_event, items) => {
          if (items.length) window.location.href = "/shift/" + data.shifts[items[0].index].shift_id;
        },
        plugins: { legend: { display: false }, refLine: { value: percent(data.goal), label: goalLabel } },
      },
      plugins: [refLine],
    });
  }

  const weekCanvas = document.getElementById("week-trend-chart");
  if (weekCanvas) {
    const series = [
      ["OEE", "oee", primary],
      ["Availability", "availability", good],
      ["Performance", "performance", "#c9a227"],
      ["Quality", "quality", "#9b7ede"],
    ];
    new Chart(weekCanvas, {
      type: "line",
      data: {
        labels: data.weeks.map((w) => w.label),
        datasets: series.map(([label, key, c]) => ({
          label: label,
          data: data.weeks.map((w) => percent(w[key])),
          borderColor: c,
          backgroundColor: c,
          tension: 0.25,
          borderWidth: label === "OEE" ? 3 : 1.5,
        })),
      },
      options: {
        maintainAspectRatio: false,
        layout: { padding: { right: 62 } },
        scales: { y: { suggestedMin: 70, suggestedMax: 100, title: { display: true, text: "%" } } },
        plugins: { refLine: { value: percent(data.goal), label: goalLabel } },
      },
      plugins: [refLine],
    });
  }
})();
