/* Maintenance KPI Dashboard – UI. All data stays inside this HTML file / browser. */
(function () {
  "use strict";
  const K = window.KPI;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  // ------------------------------------------------------------------ data
  const payload = JSON.parse($("kpi-data").textContent || "null") || {};
  const cfg = payload.config;
  const production = payload.production || {};
  const users = Object.fromEntries(Object.entries(cfg.technician_names || {}).map(([k, v]) => [k.toUpperCase(), v]));
  let files = payload.files || [];
  let byNotification = new Map();
  let noOrder = 0;
  let events = [];

  function addRows(objRows) {
    const r = K.prepareEvents(objRows, cfg);
    r.events.forEach((e) => byNotification.set(String(e.notification), e));
    noOrder += r.noOrder;
    events = [...byNotification.values()];
  }
  if (payload.rows && payload.rows.length) {
    const cols = payload.columns;
    addRows(payload.rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]]))));
  }

  // ------------------------------------------------------------------ filter state
  const state = { from: null, to: null, gran: "day", cats: new Set(cfg.downtime_categories), machine: "" };
  let dataFrom, dataTo;

  function autoGran() {
    const n = K.daysBetween(state.from, state.to).length;
    state.gran = n <= 45 ? "day" : n <= 200 ? "week" : "month";
  }

  function setupFilters() {
    // the file's first calendar day starts the range: calls before 07:00 on that day belong to a production day not in the file
    const firstCal = events.reduce((a, e) => (e.startText < a ? e.startText : a), "9999").slice(0, 10);
    const days = events.map((e) => e.prod_day).filter((d) => d >= firstCal).sort();
    dataFrom = days[0]; dataTo = days[days.length - 1];
    state.from = dataFrom; state.to = dataTo; autoGran();
    ["from", "to"].forEach((id) => { $(id).min = dataFrom; $(id).max = dataTo; });

    const months = [...new Set(days.map((d) => d.slice(0, 7)))];
    const quick = [["All data", dataFrom, dataTo]];
    if (months.length > 1 && months.length <= 24) months.forEach((m) => quick.push([K.niceMonth(m), maxDay(m + "-01", dataFrom), minDay(lastDay(m), dataTo)]));
    if (months.length > 24) [...new Set(months.map((m) => m.slice(0, 4)))].forEach((y) => quick.push([y, maxDay(y + "-01-01", dataFrom), minDay(y + "-12-31", dataTo)]));
    if (K.daysBetween(dataFrom, dataTo).length > 40) quick.push(["Last 30 days", K.addDays(dataTo, -29), dataTo]);
    if (K.daysBetween(dataFrom, dataTo).length > 10) quick.push(["Last 7 days", K.addDays(dataTo, -6), dataTo]);
    $("quick").innerHTML = quick.map(([l, f, t]) => `<button class="chip" data-f="${f}" data-t="${t}">${esc(l)}</button>`).join("");

    const allCats = [...new Set(events.map((e) => e.category))].sort((a, b) => (cfg.downtime_categories.includes(b) - cfg.downtime_categories.includes(a)) || a.localeCompare(b));
    $("cats").innerHTML = allCats.map((c) => `<button class="chip" data-c="${esc(c)}">${esc(c)}</button>`).join("");
    fillMachines();
  }
  const lastDay = (m) => { const [y, mo] = m.split("-").map(Number); return `${m}-${String(new Date(Date.UTC(y, mo, 0)).getUTCDate()).padStart(2, "0")}`; };
  const maxDay = (a, b) => (a > b ? a : b);
  const minDay = (a, b) => (a < b ? a : b);

  function fillMachines() {
    const ms = [...new Set(events.filter((e) => state.cats.has(e.category)).map((e) => e.machine))].sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
    if (state.machine && !ms.includes(state.machine)) state.machine = "";
    $("machine").innerHTML = `<option value="">All machines</option>` + ms.map((m) => `<option ${m === state.machine ? "selected" : ""}>${esc(m)}</option>`).join("");
  }

  function syncControls() {
    $("from").value = state.from; $("to").value = state.to;
    $("quick").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.f === state.from && b.dataset.t === state.to));
    $("gran").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.g === state.gran));
    $("cats").querySelectorAll("button").forEach((b) => b.classList.toggle("on", state.cats.has(b.dataset.c)));
    $("machine").value = state.machine;
  }

  $("quick").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; state.from = b.dataset.f; state.to = b.dataset.t; autoGran(); render(); };
  $("from").onchange = () => { if ($("from").value) { state.from = maxDay($("from").value, dataFrom); if (state.from > state.to) state.to = state.from; render(); } };
  $("to").onchange = () => { if ($("to").value) { state.to = minDay($("to").value, dataTo); if (state.to < state.from) state.from = state.to; render(); } };
  $("gran").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.gran = b.dataset.g; render(); } };
  $("cats").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const c = b.dataset.c;
    if (state.cats.has(c)) { if (state.cats.size > 1) state.cats.delete(c); } else state.cats.add(c);
    fillMachines(); render();
  };
  $("machine").onchange = () => { state.machine = $("machine").value; render(); };
  const drill = (m) => { state.machine = state.machine === m ? "" : m; render(); window.scrollTo({ top: 0, behavior: "smooth" }); };

  // ------------------------------------------------------------------ compute
  function compute(from, to) {
    const ev = events.filter((e) => e.prod_day >= from && e.prod_day <= to && state.cats.has(e.category) && (!state.machine || e.machine === state.machine));
    const daily = K.dailyKpis(ev, K.daysBetween(from, to), cfg, production, !!state.machine);
    const values = K.aggregate(daily, cfg);
    return { ev, daily, values, cards: K.scorecard(values, cfg, to.slice(0, 7)) };
  }

  let view = null;
  function render() {
    syncControls();
    const cur = compute(state.from, state.to);
    const n = K.daysBetween(state.from, state.to).length;
    const pFrom = K.addDays(state.from, -n), pTo = K.addDays(state.from, -1);
    const prev = pFrom >= dataFrom ? compute(pFrom, pTo) : null;
    const R = {
      ...cur, prev,
      buckets: K.buckets(cur.daily, state.gran, cfg),
      machines: K.badMachines(cur.ev), tools: K.badTools(cur.ev), damage: K.pareto(cur.ev, "damage"),
      cause: K.pareto(cur.ev, "cause"), part: K.pareto(cur.ev, "object_part"), shift: K.byShift(cur.ev),
      hours: K.byHour(cur.ev), repeats: K.repeatFailures(cur.ev), techs: K.technicians(cur.ev, users),
      quality: K.dataQuality(events, noOrder, cfg), long: K.longBreakdowns(cur.ev, cfg),
    };
    R.highlights = K.highlights(R.cards, prev && prev.cards, R.machines, R.damage, R.shift, R.ev, R.daily, cfg);
    view = R;
    renderText(R, n);
    drawCharts(R);
  }

  // ------------------------------------------------------------------ text parts
  const STATUS_VAR = { "on target": "--good", close: "--warning", "off target": "--critical", "no data": "--excluded" };
  const STATUS_ICON = { "on target": "✔", close: "▲", "off target": "✖", "no data": "–" };
  const f1 = (v) => (K.isNum(v) ? v.toLocaleString("en", { maximumFractionDigits: 1, minimumFractionDigits: 1 }) : "");
  const f0 = (v) => (K.isNum(v) ? Math.round(v).toLocaleString("en") : "");
  const pct = (v) => (K.isNum(v) ? v.toFixed(0) + "%" : "");

  function table(rows, cols, clickKey) {
    return `<div class="scroll"><table><thead><tr>${cols.map((c) => `<th class="${c.n ? "n" : ""}">${esc(c.h)}</th>`).join("")}</tr></thead><tbody>` +
      (rows.length ? rows.map((r) => `<tr${clickKey ? ` class="click" data-m="${esc(r[clickKey])}"` : ""}>${cols.map((c) => `<td class="${c.n ? "n" : ""}">${esc(c.f ? c.f(r[c.k], r) : r[c.k])}</td>`).join("")}</tr>`).join("")
        : `<tr><td colspan="${cols.length}" class="hint">No data for this selection</td></tr>`) +
      "</tbody></table></div>";
  }
  const SUMMARY_COLS = [
    { h: "Calls", k: "breakdowns", n: 1, f: f0 }, { h: "Downtime h", k: "downtime_h", n: 1, f: f1 },
    { h: "MTTR min", k: "mttr_min", n: 1, f: f1 }, { h: "Avg wait min", k: "avg_waiting_min", n: 1, f: f1 },
    { h: "Avg repair min", k: "avg_repair_min", n: 1, f: f1 }, { h: "Share", k: "share_pct", n: 1, f: pct }];

  function renderText(R, n) {
    const monthOfTarget = K.niceMonth(state.to.slice(0, 7));
    $("periodTitle").textContent = `${K.niceDay(state.from)} – ${K.niceDay(state.to)} (${n} days)` + (state.machine ? ` · machine ${state.machine}` : "");
    $("periodSub").textContent = R.prev ? `compared with ${K.niceDay(K.addDays(state.from, -n))} – ${K.niceDay(K.addDays(state.from, -1))}` : "";

    const kpiCards = R.cards.map((r) => {
      const p = R.prev && R.prev.cards.find((x) => x.kpi === r.kpi);
      return `<div class="card kpi" style="border-top-color:var(${STATUS_VAR[r.status]})">
        <div class="k">${esc(r.kpi)} ${esc(r.name)}</div><div class="v">${K.fmt(r.value, r.unit)}</div>
        <div class="s">Target ${K.fmt(r.target, r.unit)}${K.isNum(r.score) ? " · score " + r.score.toFixed(1) : ""}</div>
        <div class="s"><span class="badge" style="color:var(${STATUS_VAR[r.status]})">${STATUS_ICON[r.status]} ${r.status}</span>${p && K.isNum(p.value) ? " · before " + K.fmt(p.value, r.unit) : ""}</div></div>`;
    }).join("");
    const avg = (k) => (R.ev.length ? K.sum(R.ev.map((e) => e[k])) / R.ev.length : null);
    const tile = (k, v, s) => `<div class="card"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;
    $("cards").innerHTML = kpiCards +
      tile("Breakdown calls", f0(R.values.calls), `${f0(R.values.calls_gt_short)} longer than ${cfg.short_stop_minutes} min`) +
      tile("Downtime hours", f1(R.values.downtime_h), `of ${f0(R.values.working_hours)} working hours`) +
      tile("Avg wait for technician", K.isNum(avg("waiting_min")) ? f1(avg("waiting_min")) + " min" : "–", `repair ${K.isNum(avg("repair_min")) ? f1(avg("repair_min")) : "–"} min`);

    const notes = [];
    const multiMonth = state.from.slice(0, 7) !== state.to.slice(0, 7);
    if (multiMonth) notes.push(`Targets and scores use the targets valid in ${monthOfTarget}. Scores are defined for one month; for longer periods, read them as a guide.`);
    if (!Object.keys(production).length) {
      const p = cfg.production, o = Object.entries(p.weekday_overrides || {}).map(([d, v]) => `${d} ${v.hours ?? p.hours_per_day} h × ${v.machines ?? p.working_machines}`).join(", ");
      notes.push(`Working hours come from config.json: ${p.working_machines} machines × ${p.hours_per_day} h per day${o ? " (" + o + ")" : ""}. For exact values, run with --production days.csv.`);
    }
    if (state.machine) notes.push(`Machine view: Downtime % and MTBF use 1 machine's working hours.`);
    const cats = [...state.cats].join(", ");
    if (cats !== cfg.downtime_categories.join(", ")) notes.push(`Categories changed to: ${cats}. The official KPI uses ${cfg.downtime_categories.join(" + ")}.`);
    $("notes").innerHTML = notes.map((t) => `<p class="hint" style="margin:8px 0 0">${esc(t)}</p>`).join("");

    $("highlights").innerHTML = R.highlights.map(([s, t]) => `<li>${s === "info" ? "" : `<b style="color:var(${STATUS_VAR[s]})">${STATUS_ICON[s]}</b> `}${esc(t)}</li>`).join("") || `<li class="hint">No breakdowns in this selection.</li>`;

    const g = { day: "per day", week: "per week", month: "per month" }[state.gran];
    $("tDtTitle").textContent = `Downtime % ${g} (red = above target${state.gran === "day" ? ", grey = not counted in the KPI" : ""})`;
    $("tMttrTitle").textContent = `MTTR ${g} (min)`;
    $("tMtbfTitle").textContent = `MTBF ${g} (h)`;

    $("tMach").innerHTML = table(R.machines, [{ h: "Machine", k: "machine" }, { h: "Category", k: "category" }, ...SUMMARY_COLS, { h: "Main object part", k: "main_object_part" }], "machine");
    $("tRepeat").innerHTML = table(R.repeats.slice(0, 25), [{ h: "Machine", k: "machine" }, { h: "Object part", k: "object_part" }, { h: "Calls", k: "breakdowns", n: 1, f: f0 }, { h: "Downtime h", k: "downtime_h", n: 1, f: f1 }, { h: "Different days", k: "days", n: 1, f: f0 }], "machine");
    $("tShift").innerHTML = table(R.shift, [{ h: "Shift", k: "key" }, ...SUMMARY_COLS]);
    $("tCause").innerHTML = table(R.cause, [{ h: "Cause", k: "key" }, { h: "Calls", k: "breakdowns", n: 1, f: f0 }, { h: "Downtime h", k: "downtime_h", n: 1, f: f1 }, { h: "Share", k: "share_pct", n: 1, f: pct }, { h: "Cumulative", k: "cum_pct", n: 1, f: pct }]);
    $("tTech").innerHTML = table(R.techs.slice(0, 30), [{ h: "User", k: "key" }, { h: "Name", k: "name" }, { h: "Calls", k: "breakdowns", n: 1, f: f0 }, { h: "Avg wait min", k: "avg_waiting_min", n: 1, f: f1 }, { h: "Avg repair min", k: "avg_repair_min", n: 1, f: f1 }]);
    $("tQuality").innerHTML = table(R.quality, [{ h: "Check", k: "check" }, { h: "Count", k: "count", n: 1, f: f0 }]);
    document.querySelectorAll("tr.click").forEach((tr) => { tr.onclick = () => drill(tr.dataset.m); });

    $("howto").innerHTML = `<h3>How the KPIs are calculated</h3>
      Only SAP notifications with a work order are used. The production day runs ${String(cfg.day_start_hour).padStart(2, "0")}:00 → ${String(cfg.day_start_hour).padStart(2, "0")}:00.
      The category comes from the fault code at the start of the notification description (D = Machine, E = Applicator, F = Seal, N = IT; D on WPA equipment = WPA).<br>
      Per day: Downtime % = breakdown hours ÷ working hours; MTTR = breakdown minutes ÷ calls; MTBF = (working hours − breakdown hours) ÷ calls.<br>
      For a period: the average of the daily values (Downtime % skips ${esc(cfg.downtime_excluded_weekdays.join(", "))}), the same as the old KPI workbook. Scores use its 0–1.5 bands.
      Targets and working hours are set in config.json.`;
  }

  // ------------------------------------------------------------------ charts
  let charts = [];
  function baseOptions(extra) {
    const text2 = css("--text-2"), grid = css("--grid");
    return Object.assign({
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false, labels: { color: text2, boxWidth: 14 } }, tooltip: { padding: 8 } },
      scales: {
        x: { ticks: { color: text2, maxRotation: 0, autoSkip: true }, grid: { display: false }, border: { color: grid } },
        y: { ticks: { color: text2 }, grid: { color: grid }, border: { display: false }, beginAtZero: true },
      },
    }, extra || {});
  }
  const add = (id, config) => charts.push(new Chart($(id), config));
  const targetDs = (vals) => ({ type: "line", label: "Target", data: vals, borderColor: css("--text-2"), borderDash: [5, 4], borderWidth: 1.5,
    pointRadius: 0, pointHitRadius: 0, fill: false, stepped: "middle" });

  function drawCharts(R) {
    charts.forEach((c) => c.destroy()); charts = [];
    const series = css("--series"), critical = css("--critical"), excluded = css("--excluded");
    const B = R.buckets, labels = B.map((b) => b.label);
    const tgt = (k, scale) => B.map((b) => { const t = K.targetFor(cfg.kpis[k], b.month); return K.isNum(t) ? t * scale : null; });
    const tDt = tgt("L-109", 100);
    const bucketTitle = (it) => { const b = B[it[0].dataIndex]; return b.from === b.to ? `${b.from} (${K.weekday(b.from)})${b.excluded ? " – not counted" : ""}` : `${b.from} → ${b.to}`; };

    const o1 = baseOptions(); o1.plugins.legend.display = true;
    o1.plugins.tooltip.callbacks = { title: bucketTitle, label: (it) => `${it.dataset.label}: ${K.isNum(it.parsed.y) ? it.parsed.y.toFixed(2) + "%" : "–"}`,
      afterBody: (it) => { const b = B[it[0].dataIndex]; return `${f0(b.calls)} calls · ${f1(b.downtime_h)} h downtime`; } };
    add("cDt", { type: "bar", options: o1, data: { labels, datasets: [
      { label: "Downtime %", data: B.map((b) => (K.isNum(b["L-109"]) ? b["L-109"] * 100 : null)), borderRadius: 4, borderSkipped: "start", maxBarThickness: 48,
        backgroundColor: B.map((b, i) => (b.excluded ? excluded : K.isNum(b["L-109"]) && b["L-109"] * 100 > tDt[i] ? critical : series)) },
      targetDs(tDt)] } });

    [["cMttr", "L-110", "MTTR min"], ["cMtbf", "L-107", "MTBF h"]].forEach(([id, k, label]) => {
      const o = baseOptions(); o.plugins.legend.display = true;
      o.plugins.tooltip.callbacks = { title: bucketTitle, label: (it) => `${it.dataset.label}: ${K.isNum(it.parsed.y) ? it.parsed.y.toFixed(2) : "–"}` };
      add(id, { type: "line", options: o, data: { labels, datasets: [
        { label, data: B.map((b) => b[k]), borderColor: series, backgroundColor: series, borderWidth: 2, pointRadius: B.length > 60 ? 0 : 4, pointHoverRadius: 6 },
        targetDs(tgt(k, 1))] } });
    });

    const hbar = (id, rows, labelFn, onClick) => {
      const o = baseOptions({ indexAxis: "y" });
      o.interaction = { mode: "nearest", axis: "y", intersect: false };
      o.scales.x.grid = { color: css("--grid") }; o.scales.y.grid = { display: false }; o.scales.y.ticks.autoSkip = false;
      o.plugins.tooltip.callbacks = { label: (it) => { const r = rows[it.dataIndex]; return `${r.downtime_h.toFixed(1)} h · ${r.breakdowns} calls · ${r.share_pct.toFixed(0)}% of downtime`; } };
      if (onClick) { o.onClick = (evt, els, chart) => { const p = chart.getElementsAtEventForMode(evt, "nearest", { axis: "y", intersect: false }, false); if (p.length) onClick(rows[p[0].index]); };
        o.onHover = (evt, els) => { evt.native.target.style.cursor = els.length ? "pointer" : "default"; }; }
      add(id, { type: "bar", options: o, data: { labels: rows.map(labelFn), datasets: [{ label: "Downtime h", data: rows.map((r) => r.downtime_h), backgroundColor: series, borderRadius: 4, borderSkipped: "start", barPercentage: 0.8 }] } });
    };
    hbar("cMach", R.machines, (r) => `${r.machine} (${r.category.replace(" BD", "")})`, (r) => drill(r.machine));
    hbar("cTool", R.tools, (r) => r.key);
    hbar("cDamage", R.damage, (r) => r.key);
    hbar("cPart", R.part, (r) => r.key);

    const order = [...Array(17).keys()].map((i) => i + 7).concat([...Array(7).keys()]);
    const shiftColor = (h) => (h >= 7 && h < 15 ? css("--series-soft") : h >= 15 && h < 23 ? series : css("--series-dark"));
    const ho = baseOptions();
    ho.plugins.tooltip.callbacks = { title: (it) => { const h = order[it[0].dataIndex]; return `${String(h).padStart(2, "0")}:00–${String((h + 1) % 24).padStart(2, "0")}:00`; }, label: (it) => `${it.parsed.y} calls` };
    add("cHour", { type: "bar", options: ho, data: { labels: order.map((h) => String(h).padStart(2, "0")), datasets: [{ label: "Calls", data: order.map((h) => R.hours[h]), backgroundColor: order.map(shiftColor), borderRadius: 4, borderSkipped: "start" }] } });
  }

  // ------------------------------------------------------------------ Excel export of the current view
  function clean(rows, map) {
    return rows.map((r) => { const o = {}; Object.entries(map).forEach(([h, k]) => { const v = typeof k === "function" ? k(r) : r[k]; o[h] = K.isNum(v) ? Math.round(v * 1000) / 1000 : v; }); return o; });
  }
  const SUM = { Calls: "breakdowns", "Downtime h": "downtime_h", "MTTR min": "mttr_min", "Avg wait min": "avg_waiting_min", "Avg repair min": "avg_repair_min", "Share %": "share_pct" };
  $("btnExcel").onclick = () => {
    if (!view) return;
    const R = view, wb = XLSX.utils.book_new();
    const sheet = (name, rows) => {
      const ws = XLSX.utils.json_to_sheet(rows.length ? rows : [{ "(no rows)": "" }]);
      const keys = Object.keys(rows[0] || { x: 1 });
      ws["!cols"] = keys.map((k) => ({ wch: Math.min(45, Math.max(10, k.length + 2, ...rows.slice(0, 200).map((r) => String(r[k] == null ? "" : r[k]).length + 1))) }));
      XLSX.utils.book_append_sheet(wb, ws, name);
    };
    sheet("KPIs", clean(R.cards, { KPI: "kpi", Name: "name", Unit: "unit", Value: "value", Target: "target", Score: "score", Status: "status" })
      .concat([{}, { KPI: "Period", Name: `${state.from} to ${state.to}` }, { KPI: "Machine", Name: state.machine || "all" }, { KPI: "Categories", Name: [...state.cats].join(", ") }]));
    sheet("Trend", clean(R.buckets, { Period: "label", From: "from", To: "to", "Downtime %": "L-109", "MTTR min": "L-110", "MTBF h": "L-107", Calls: "calls", "Downtime h": "downtime_h", "Working h": "working_hours" }));
    sheet("Daily", clean(R.daily, { Date: "date", Day: "weekday", "Working h": "working_hours", Calls: "breakdowns", "Downtime h": "downtime_h", "Downtime %": "downtime_pct", "MTTR min": "mttr_min", "MTBF h": "mtbf_h" }));
    sheet("Bad actor machines", clean(R.machines, { Machine: "machine", Category: "category", ...SUM, "Main object part": "main_object_part" }));
    sheet("Bad actor applicators", clean(R.tools, { "Tool ID": "key", ...SUM }));
    sheet("Repeat failures", clean(R.repeats, { Machine: "machine", "Object part": "object_part", Calls: "breakdowns", "Downtime h": "downtime_h", "Different days": "days" }));
    sheet("Pareto damage", clean(R.damage, { Damage: "key", ...SUM, "Cumulative %": "cum_pct" }));
    sheet("Pareto cause", clean(R.cause, { Cause: "key", ...SUM, "Cumulative %": "cum_pct" }));
    sheet("Pareto object part", clean(R.part, { "Object part": "key", ...SUM, "Cumulative %": "cum_pct" }));
    sheet("Shifts", clean(R.shift, { Shift: "key", ...SUM }));
    sheet("Technicians", clean(R.techs, { User: "key", Name: "name", ...SUM }));
    const EV = { Notification: "notification", Order: "order", "Production day": "prod_day", Shift: "shift", Start: "startText", Machine: "machine", Category: "category",
      "Fault code": "fault_code", "Breakdown min": "breakdown_min", "Waiting min": "waiting_min", "Repair min": "repair_min", Damage: "damage", Cause: "cause",
      "Object part": "object_part", Technician: "technician", "Tool ID": "tool_id", Description: "description" };
    sheet("Long breakdowns", clean(R.long, EV));
    sheet("Events", clean(R.ev, EV));
    XLSX.writeFile(wb, `KPI_${state.from}_to_${state.to}${state.machine ? "_" + state.machine : ""}.xlsx`);
  };
  $("btnPrint").onclick = () => window.print();
  window.addEventListener("beforeprint", () => charts.forEach((c) => c.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (view) drawCharts(view); });

  // ------------------------------------------------------------------ add SAP files in the browser
  function showError(msg) { $("errors").innerHTML = msg ? `<div class="err">${esc(msg)}</div>` : ""; }
  async function addFiles(list) {
    showError("");
    for (const f of list) {
      try {
        const wb = XLSX.read(await f.arrayBuffer(), { type: "array" });
        addRows(XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { raw: true, defval: null }));
        files.push(f.name);
      } catch (err) { showError(`${f.name}: ${err.message}`); }
    }
    start();
  }
  $("btnAdd").onclick = () => $("fileAdd").click();
  $("fileAdd").onchange = (e) => { const l = [...e.target.files]; e.target.value = ""; if (l.length) addFiles(l); };
  const drop = $("empty");
  drop.onclick = () => $("fileAdd").click();
  ["dragenter", "dragover"].forEach((t) => document.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => document.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  document.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) addFiles([...e.dataTransfer.files]); });

  function start() {
    const has = events.length > 0;
    $("empty").classList.toggle("hidden", has);
    $("dash").classList.toggle("hidden", !has);
    $("source").textContent = has
      ? `${events.length.toLocaleString()} breakdown calls · ${K.niceDay(events.reduce((a, e) => (e.startText < a ? e.startText : a), "9999").slice(0, 10))} – ${K.niceDay(events.reduce((a, e) => (e.prod_day > a ? e.prod_day : a), ""))} · from ${files.join(", ")}` +
        (Object.keys(production).length ? " · exact working hours" : " · working hours from config.json")
      : "";
    if (has) { setupFilters(); render(); }
  }
  start();
})();
