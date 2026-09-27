/* Maintenance KPI engine: turns SAP breakdown rows into KPIs for any date range.
   Same rules as the old KPI workbook. Runs in the browser and in Node (for tests). */
(function (root) {
  "use strict";

  const DAY_MS = 86400000;
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // ------------------------------------------------------------------ helpers
  const isNum = (v) => typeof v === "number" && isFinite(v);
  const norm = (s) => String(s).replace(/\s+/g, " ").trim();
  const pad = (n) => String(n).padStart(2, "0");
  const dayKey = (ms) => { const d = new Date(ms); return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`; };
  const keyMs = (key) => Date.parse(key + "T00:00:00Z");
  const weekday = (key) => WEEKDAYS[new Date(keyMs(key)).getUTCDay()];
  const addDays = (key, n) => dayKey(keyMs(key) + n * DAY_MS);
  const sum = (a) => a.reduce((s, v) => s + v, 0);
  const mean = (a) => (a.length ? sum(a) / a.length : null);
  const meanNonzero = (a) => mean(a.filter((v) => isNum(v) && v !== 0));
  const niceDay = (key) => { const d = new Date(keyMs(key)); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
  const niceMonth = (m) => `${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}`;

  function parseStamp(v) {
    if (isNum(v)) return Math.round((v - 25569) * DAY_MS);  // Excel serial date
    const s = String(v == null ? "" : v).trim();
    let m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})/.exec(s);
    if (m) return Date.UTC(+m[3], +m[2] - 1, +m[1], +m[4], +m[5], +m[6]);
    m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(s);
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) : null;
  }

  function daysBetween(from, to) {
    const out = [];
    for (let d = from; d <= to; d = addDays(d, 1)) out.push(d);
    return out;
  }

  // ------------------------------------------------------------------ targets / scoring
  function targetFor(kc, month) {
    let t = null;
    [...kc.targets].sort((a, b) => a.from.localeCompare(b.from)).forEach((e) => { if (e.from <= month) t = e.target; });
    return t;
  }

  function scoreBands(kc, target) {
    return Array.from({ length: 16 }, (_, i) => {
      const s = i / 10;
      return [s, s <= 1 ? target - kc.step_below * 10 * (1 - s) : target + kc.step_above * 10 * (s - 1)];
    });
  }

  /** Score 0–1.5 exactly like the YEAR sheet of the old workbook. */
  function score(kc, value, target) {
    if (!isNum(value) || value === 0 || !isNum(target)) return null;
    const bands = scoreBands(kc, target);
    if (kc.scoring === "nearest") {
      let best = bands[0];
      bands.forEach((b) => { if (Math.abs(b[1] - value) < Math.abs(best[1] - value)) best = b; });
      return best[0];
    }
    if (kc.scoring === "at_or_below") {
      const ok = bands.filter((b) => b[1] >= value);
      return ok.length ? ok.reduce((a, b) => (b[1] < a[1] ? b : a))[0] : 0;
    }
    if (kc.scoring === "at_or_above") {
      const ok = bands.filter((b) => b[1] <= value);
      return ok.length ? ok.reduce((a, b) => (b[1] > a[1] ? b : a))[0] : 0;
    }
    throw new Error("Unknown scoring " + kc.scoring);
  }

  function statusOf(kc, value, target) {
    if (!isNum(value) || !isNum(target)) return "no data";
    const ok = kc.better === "lower" ? value <= target : value >= target;
    if (ok) return "on target";
    const gap = Math.abs(value - target) / Math.abs(target);
    return gap <= 0.1 ? "close" : "off target";
  }

  // ------------------------------------------------------------------ SAP rows -> events
  const REQUIRED = ["Notification", "Order", "Equipment description", "Description",
    "Notification Start Time/Date Stamp", "Total Breakdown", "Waiting Time", "Intervention Time"];

  function prepareEvents(rows, cfg) {
    const events = [];
    let noOrder = 0;
    if (!rows.length) return { events, noOrder };
    const keys = Object.keys(rows[0]).map(norm);
    const missing = REQUIRED.filter((c) => !keys.includes(c));
    if (missing.length) throw new Error("This does not look like the SAP breakdown export. Missing columns: " + missing.join(", "));

    rows.forEach((raw) => {
      const r = {};
      Object.keys(raw).forEach((k) => { r[norm(k)] = raw[k]; });
      if (r.Order == null || r.Order === "") { noOrder++; return; }
      const start = parseStamp(r["Notification Start Time/Date Stamp"]);
      if (start == null) return;

      const equip = String(r["Equipment description"] == null ? "" : r["Equipment description"]);
      const group = equip.split("-")[1] || "";
      const desc = String(r.Description == null ? "" : r.Description).trim().toUpperCase();
      const codeM = /^([A-Z]\d*)/.exec(desc);
      const code = codeM ? codeM[1] : null;
      const letter = code ? code[0] : null;
      let category = (letter && cfg.fault_code_categories[letter]) || null;
      const ov = (cfg.equipment_group_overrides || {})[group];
      if (ov && letter && ov[letter]) category = ov[letter];

      const t = new Date(start);
      const minutes = t.getUTCHours() * 60 + t.getUTCMinutes() + t.getUTCSeconds() / 60;
      const shift = minutes >= 420 && minutes <= 900 ? "1st" : minutes > 900 && minutes <= 1380 ? "2nd" : "3rd";
      const num = (v) => (v !== null && v !== "" && isNum(Number(v)) ? Number(v) : 0);
      const txt = (v) => (v == null || v === "" ? "(not coded)" : String(v));
      const tool = r["Equipment.1"] != null ? r["Equipment.1"] : r["Equipment_1"];

      events.push({
        notification: r.Notification, order: r.Order, start,
        startText: t.toISOString().slice(0, 19).replace("T", " "),
        prod_day: dayKey(start - cfg.day_start_hour * 3600000), shift, hour: t.getUTCHours(),
        group, machine: equip.replace(/^[^-]+-[^-]+-/, ""),
        tool_id: tool == null || tool === "" ? null : String(Math.round(Number(tool))),
        fault_code: code, category: category || "Unclassified",
        breakdown_min: num(r["Total Breakdown"]), waiting_min: num(r["Waiting Time"]), repair_min: num(r["Intervention Time"]),
        technician: r["WO Confirmation Creator Stamp"] == null ? "?" : String(r["WO Confirmation Creator Stamp"]).toUpperCase(),
        damage: txt(r["DamageCode Short text"]), cause: txt(r["Cause short text"]), object_part: txt(r["Object Parts short text"]),
        description: r.Description == null ? "" : String(r.Description),
      });
    });
    return { events, noOrder };
  }

  // ------------------------------------------------------------------ working hours
  /** Working hours of one day: from the production file if given, else from config defaults. */
  function workingHours(day, cfg, production, singleMachine) {
    const p = production && production[day];
    let hours, machines;
    if (p) { hours = p[0]; machines = p[1]; }
    else {
      const d = cfg.production, o = (d.weekday_overrides || {})[weekday(day)] || {};
      hours = isNum(o.hours) ? o.hours : d.hours_per_day;
      machines = isNum(o.machines) ? o.machines : d.working_machines;
    }
    if (singleMachine) machines = 1;
    return isNum(hours) && isNum(machines) && hours * machines > 0 ? hours * machines : null;
  }

  // ------------------------------------------------------------------ KPIs
  /** One row per production day. `events` are already filtered to what counts as downtime. */
  function dailyKpis(events, days, cfg, production, singleMachine) {
    const byDay = {};
    events.forEach((e) => { (byDay[e.prod_day] = byDay[e.prod_day] || []).push(e); });
    return days.map((d) => {
      const ev = byDay[d] || [];
      const wh = workingHours(d, cfg, production, singleMachine);
      const dt = sum(ev.map((e) => e.breakdown_min)) / 60;
      const n = ev.length;
      return {
        date: d, weekday: weekday(d), working_hours: wh, breakdowns: n,
        breakdowns_gt_short: ev.filter((e) => e.breakdown_min > cfg.short_stop_minutes).length,
        downtime_h: dt,
        waiting_min_avg: mean(ev.map((e) => e.waiting_min)), repair_min_avg: mean(ev.map((e) => e.repair_min)),
        downtime_pct: wh ? dt / wh : null,
        mttr_min: n ? (dt * 60) / n : null,
        mtbf_h: n && wh ? (wh - dt) / n : null,
      };
    });
  }

  /** KPI values over a set of daily rows: average of the daily values (Downtime % skips Fridays). */
  function aggregate(daily, cfg) {
    const counted = daily.filter((d) => !cfg.downtime_excluded_weekdays.includes(d.weekday));
    return {
      "L-109": meanNonzero(counted.map((d) => d.downtime_pct)),
      "L-110": meanNonzero(daily.map((d) => d.mttr_min)),
      "L-107": meanNonzero(daily.map((d) => d.mtbf_h)),
      calls: sum(daily.map((d) => d.breakdowns)),
      calls_gt_short: sum(daily.map((d) => d.breakdowns_gt_short)),
      downtime_h: sum(daily.map((d) => d.downtime_h)),
      working_hours: sum(daily.map((d) => d.working_hours || 0)),
    };
  }

  function scorecard(values, cfg, month) {
    return Object.entries(cfg.kpis).map(([id, kc]) => {
      const value = isNum(values[id]) ? values[id] : null;
      const target = targetFor(kc, month);
      return { kpi: id, name: kc.name, unit: kc.unit, better: kc.better, value, target,
        score: score(kc, value, target), status: statusOf(kc, value, target) };
    });
  }

  function mondayOf(day) { const w = new Date(keyMs(day)).getUTCDay(); return addDays(day, -((w + 6) % 7)); }

  /** Group daily rows into day / week (Mon–Sun) / month buckets for the trend charts. */
  function buckets(daily, gran, cfg) {
    const keyOf = gran === "month" ? (d) => d.date.slice(0, 7) : gran === "week" ? (d) => mondayOf(d.date) : (d) => d.date;
    const groups = new Map();
    daily.forEach((d) => { const k = keyOf(d); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(d); });
    return [...groups.entries()].map(([k, rows]) => {
      const a = aggregate(rows, cfg);
      const label = gran === "month" ? niceMonth(k) : gran === "week" ? `Wk ${niceDay(rows[0].date).split(" ").slice(0, 2).join(" ")}` : k.slice(8) + " " + MONTHS[+k.slice(5, 7) - 1];
      const excluded = gran === "day" && cfg.downtime_excluded_weekdays.includes(rows[0].weekday);
      return { key: k, label, from: rows[0].date, to: rows[rows.length - 1].date, month: rows[rows.length - 1].date.slice(0, 7), excluded, ...a };
    });
  }

  // ------------------------------------------------------------------ analysis
  function summary(events, keyFn) {
    const groups = new Map();
    events.forEach((e) => { const k = keyFn(e); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(e); });
    const rows = [...groups.entries()].map(([key, ev]) => ({
      key, breakdowns: ev.length, downtime_h: sum(ev.map((e) => e.breakdown_min)) / 60,
      mttr_min: mean(ev.map((e) => e.breakdown_min)), avg_waiting_min: mean(ev.map((e) => e.waiting_min)),
      avg_repair_min: mean(ev.map((e) => e.repair_min)), _ev: ev,
    }));
    const total = sum(rows.map((r) => r.downtime_h));
    rows.forEach((r) => { r.share_pct = total ? (100 * r.downtime_h) / total : 0; });
    return rows.sort((a, b) => b.downtime_h - a.downtime_h);
  }

  function pareto(events, field, top = 10) {
    let cum = 0;
    return summary(events, (e) => e[field]).slice(0, top).map((r) => { cum += r.share_pct; return { ...r, cum_pct: cum }; });
  }

  function badMachines(events, top = 10) {
    return summary(events, (e) => e.machine + "\u0000" + e.category).slice(0, top).map((r) => {
      const [machine, category] = r.key.split("\u0000");
      const parts = summary(r._ev, (e) => e.object_part);
      return { ...r, machine, category, main_object_part: parts.length ? parts[0].key : "" };
    });
  }

  const badTools = (events, top = 10) => summary(events.filter((e) => e.category === "Applicator BD"), (e) => e.tool_id || "?").slice(0, top);
  const byShift = (events) => summary(events, (e) => e.shift).sort((a, b) => a.key.localeCompare(b.key));

  function byHour(events) {
    const out = Array.from({ length: 24 }, () => 0);
    events.forEach((e) => { out[e.hour] += 1; });
    return out;
  }

  function repeatFailures(events, minCount = 3) {
    return summary(events.filter((e) => e.object_part !== "(not coded)"), (e) => e.machine + "\u0000" + e.object_part)
      .filter((r) => r.breakdowns >= minCount)
      .map((r) => { const [machine, object_part] = r.key.split("\u0000"); return { ...r, machine, object_part, days: new Set(r._ev.map((e) => e.prod_day)).size }; })
      .sort((a, b) => b.breakdowns - a.breakdowns || b.downtime_h - a.downtime_h);
  }

  const technicians = (events, users) => summary(events, (e) => e.technician)
    .map((r) => ({ ...r, name: (users || {})[r.key] || "" })).sort((a, b) => b.breakdowns - a.breakdowns);

  function dataQuality(events, noOrder, cfg) {
    return [
      ["Notifications without a work order (ignored)", noOrder],
      ["Calls with an unknown fault code (category 'Unclassified')", events.filter((e) => e.category === "Unclassified").length],
      ["Calls without damage code", events.filter((e) => e.damage === "(not coded)").length],
      ["Calls without cause", events.filter((e) => e.cause === "(not coded)").length],
      [`Breakdowns longer than ${cfg.long_breakdown_minutes} min (check they are real)`, events.filter((e) => e.breakdown_min > cfg.long_breakdown_minutes).length],
      ["Calls with zero breakdown time", events.filter((e) => e.breakdown_min <= 0).length],
    ].map(([check, count]) => ({ check, count }));
  }

  const longBreakdowns = (events, cfg) => events.filter((e) => e.breakdown_min > cfg.long_breakdown_minutes).sort((a, b) => b.breakdown_min - a.breakdown_min);

  function fmt(v, unit) {
    if (!isNum(v)) return "–";
    if (unit === "%") return (v * 100).toFixed(2) + "%";
    return v.toFixed(Math.abs(v) < 10 ? 2 : 1) + " " + unit;
  }

  function highlights(cards, prevCards, machines, damage, shift, events, daily, cfg) {
    const out = [];
    cards.forEach((r) => {
      if (r.status === "no data") return;
      let line = `${r.kpi} ${r.name}: ${fmt(r.value, r.unit)} vs target ${fmt(r.target, r.unit)} (${r.status})`;
      const p = prevCards && prevCards.find((x) => x.kpi === r.kpi);
      if (p && isNum(p.value) && isNum(r.value) && p.value !== r.value) {
        const better = (r.value < p.value) === (r.better === "lower");
        line += `; ${better ? "better" : "worse"} than the previous period (${fmt(p.value, r.unit)})`;
      }
      out.push([r.status, line]);
    });
    if (machines.length > 1) {
      const top3 = machines.slice(0, 3);
      out.push(["info", `Top 3 machines cause ${sum(top3.map((m) => m.share_pct)).toFixed(0)}% of downtime: ` +
        top3.map((m) => `${m.machine} (${m.category.replace(" BD", "")}, ${m.downtime_h.toFixed(1)} h)`).join(", ") + "."]);
    }
    if (damage.length) out.push(["info", `Biggest damage type: ${damage[0].key} (${damage[0].share_pct.toFixed(0)}% of downtime hours).`]);
    if (shift.length) {
      const w = shift.reduce((a, b) => (b.downtime_h > a.downtime_h ? b : a));
      out.push(["info", `Shift with most downtime: ${w.key} (${w.downtime_h.toFixed(1)} h, ${w.breakdowns} calls).`]);
    }
    if (events.length) {
      out.push(["info", `Average call: ${mean(events.map((e) => e.waiting_min)).toFixed(1)} min waiting for a technician + ${mean(events.map((e) => e.repair_min)).toFixed(1)} min repair.`]);
    }
    const counted = daily.filter((d) => !cfg.downtime_excluded_weekdays.includes(d.weekday) && isNum(d.downtime_pct) && d.breakdowns);
    if (counted.length > 1) {
      const w = counted.reduce((a, b) => (b.downtime_pct > a.downtime_pct ? b : a));
      out.push(["info", `Worst day: ${w.weekday} ${niceDay(w.date)} with ${(w.downtime_pct * 100).toFixed(1)}% downtime.`]);
    }
    return out;
  }

  const api = { parseStamp, daysBetween, addDays, weekday, niceDay, niceMonth, targetFor, scoreBands, score, statusOf,
    prepareEvents, workingHours, dailyKpis, aggregate, scorecard, buckets, pareto, badMachines, badTools, byShift, byHour,
    repeatFailures, technicians, dataQuality, longBreakdowns, highlights, fmt, isNum, sum };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.KPI = api;
})(this);
