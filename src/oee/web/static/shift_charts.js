// Grafy Shift Dashboardu (TASK §7 B, C, E). Iba kreslí čísla z /api/shift/{id}/charts — žiadne výpočty KPI.
(function () {
  "use strict";
  const canvas = document.getElementById("waterfall-chart");
  if (!canvas || typeof Chart === "undefined") return;

  const css = getComputedStyle(document.documentElement);
  const color = (name, fallback) => (css.getPropertyValue(name) || fallback).trim();
  const muted = color("--pico-muted-color", "#888");
  const text = color("--pico-color", "#ddd");
  const good = color("--pico-ins-color", "#2a7");
  const bad = color("--pico-del-color", "#c33");
  const primary = color("--pico-primary", "#1095c1");
  const percent = (share) => (share === null ? null : share * 100); // podiel → % na osi grafu
  const fmt = new Intl.NumberFormat("en", { maximumFractionDigits: 1, signDisplay: "auto" });

  // Vodorovná čiara cieľa cez celú šírku grafu (hodnota zo servera, Chart.js ju iba prevedie na pixely).
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
      ctx.setLineDash([]);
      // popis za koncom čiary — v pravom okraji grafu (layout.padding.right), mimo stĺpcov
      ctx.font = "600 11px system-ui, sans-serif";
      ctx.fillStyle = bad;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      opts.label.split("\n").forEach((line, i, lines) => {
        ctx.fillText(line, chartArea.right + 6, y + (i - (lines.length - 1) / 2) * 13);
      });
      ctx.restore();
    },
  };

  // Popis nad stĺpcom: hodnota, ktorú pripravil server (pri waterfalle so znamienkom straty).
  const barLabels = {
    id: "barLabels",
    afterDatasetsDraw(chart, _args, opts) {
      if (!opts.labels) return;
      const { ctx } = chart;
      ctx.save();
      ctx.fillStyle = text;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      chart.getDatasetMeta(0).data.forEach((bar, i) => {
        if (opts.labels[i] !== null) ctx.fillText(opts.labels[i], bar.x, bar.y);
      });
      ctx.restore();
    },
  };

  // Spojnice waterfallu: z konca kroku k začiatku ďalšieho na úrovni, ktorú poslal server (`connect`).
  const connectors = {
    id: "connectors",
    beforeDatasetsDraw(chart, _args, opts) {
      if (!opts.levels) return;
      const { ctx } = chart;
      const bars = chart.getDatasetMeta(0).data;
      ctx.save();
      ctx.strokeStyle = text;
      ctx.globalAlpha = 0.55;
      ctx.lineWidth = 1.5;
      opts.levels.forEach((level, i) => {
        if (level === null || !bars[i + 1]) return;
        const y = chart.scales.y.getPixelForValue(level);
        ctx.beginPath();
        ctx.moveTo(bars[i].x, y);
        ctx.lineTo(bars[i + 1].x, y);
        ctx.stroke();
      });
      ctx.restore();
    },
  };

  const base = { maintainAspectRatio: false, plugins: { legend: { display: false } } };

  fetch(canvas.dataset.url)
    .then((r) => r.json())
    .then((d) => {
      Chart.defaults.color = muted;

      // B · waterfall: plávajúce stĺpce [od, do] a popisy pripravené serverom z kaskády ShiftAnalytics
      const steps = d.waterfall_steps;
      const stepColor = { total: primary, loss: bad, result: good };
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: steps.map((s) => s.label),
          datasets: [
            {
              data: steps.map((s) => s.range),
              backgroundColor: steps.map((s) => stepColor[s.kind]),
              borderRadius: 4,
              borderSkipped: false,
              barPercentage: 0.6,
            },
          ],
        },
        options: Object.assign({}, base, {
          layout: { padding: { top: 18, right: 62 } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "pcs" } } },
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (item) => fmt.format(steps[item.dataIndex].value) + " pcs" } },
            refLine: { value: d.oee_goal_pcs, label: "OEE goal\n" + fmt.format(d.oee_goal_pcs) + " pcs" },
            barLabels: { labels: steps.map((s) => fmt.format(s.value)) },
            connectors: { levels: steps.map((s) => s.connect) },
          },
        }),
        plugins: [connectors, refLine, barLabels],
      });

      // C · hodinový OEE; nevyplnené hodiny = medzera (null), nie 0
      const hourly = d.hourly;
      new Chart(document.getElementById("hourly-chart"), {
        type: "bar",
        data: {
          labels: hourly.map((h) => h.hour_no + " · " + h.slot),
          datasets: [
            {
              data: hourly.map((h) => percent(h.oee)),
              backgroundColor: hourly.map((h) => (h.flags.includes("below_goal") ? bad : good)),
              barPercentage: 0.7,
            },
          ],
        },
        options: Object.assign({}, base, {
          layout: { padding: { top: 18, right: 62 } },
          scales: { y: { beginAtZero: true, suggestedMax: 100, title: { display: true, text: "OEE %" } } },
          plugins: {
            legend: { display: false },
            refLine: { value: percent(d.target_oee), label: "OEE goal\n" + fmt.format(percent(d.target_oee)) + " %" },
            barLabels: { labels: hourly.map((h) => (h.oee === null ? "not submitted" : fmt.format(percent(h.oee)) + " %")) },
            tooltip: {
              callbacks: {
                afterBody: (items) => {
                  const h = hourly[items[0].dataIndex];
                  if (h.produced === null) return "not submitted";
                  return ["Produced " + h.produced + " of target " + fmt.format(h.target_pcs), "Rejects " + h.rejects, "Downtime " + fmt.format(h.downtime_min) + " min"];
                },
              },
            },
          },
        }),
        plugins: [refLine, barLabels],
      });

      // E · Pareto (typ alebo kategória podľa prepínača)
      const paretoCanvas = document.getElementById("pareto-chart");
      const buckets = d.pareto[paretoCanvas.dataset.mode] || d.pareto.type;
      new Chart(paretoCanvas, {
        type: "bar",
        data: {
          labels: buckets.map((b) => b.label),
          datasets: [{ data: buckets.map((b) => b.pcs), backgroundColor: buckets.map((b) => (b.kind === null && !b.category ? muted : primary)), barPercentage: 0.7 }],
        },
        options: Object.assign({}, base, {
          layout: { padding: { top: 18 } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "lost pcs" } } },
          plugins: { legend: { display: false }, barLabels: { labels: buckets.map((b) => fmt.format(b.pcs)) } },
        }),
        plugins: [barLabels],
      });
    })
    .catch(() => {
      for (const id of ["waterfall-chart", "hourly-chart", "pareto-chart"]) {
        const el = document.getElementById(id);
        if (el) el.replaceWith(Object.assign(document.createElement("p"), { textContent: "Chart unavailable." }));
      }
    });
})();
