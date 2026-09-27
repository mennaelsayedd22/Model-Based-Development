// Run with: node --test tests/engine.test.js   (made-up data only – no company data in this repository)
const test = require("node:test");
const assert = require("node:assert");
const K = require("../dashboard/engine.js");
const cfg = require("../config.json");

const row = (n, start, equip, desc, total, wait, rep) => ({
  Notification: n, Order: 100 + n, "Equipment description": equip, Description: desc,
  "Notification Start Time/Date Stamp": start, "Total Breakdown": total, "Waiting Time": wait, "Intervention Time": rep,
});
const rows = [
  row(1, "03.08.2026 08:00:00", "C3-CST-K01", "D1 - machine stop", 30, 10, 20),
  row(2, "03.08.2026 09:00:00", "C3-CST-K01", "E1 - applicator", 10, 5, 5),
  row(3, "04.08.2026 06:30:00", "C3-CST-K02", "d1", 60, 20, 40),        // before 07:00 -> production day 3 Aug
  row(4, "03.08.2026 10:00:00", "C3-CST-K03", "F1 - seal", 45, 5, 40),   // Seal BD
  row(5, "03.08.2026 11:00:00", "C3-WPA-MP01", "D1", 15, 5, 10),         // WPA BD
  { ...row(6, "03.08.2026 12:00:00", "C3-CST-K01", "D1", 5, 1, 4), Order: null }, // no work order -> ignored
];

test("scores match the old KPI workbook bands", () => {
  const k = cfg.kpis;
  assert.strictEqual(K.score(k["L-109"], 0.0379, 0.03), 0.6);
  assert.strictEqual(K.score(k["L-109"], 0.019, 0.03), 1.3);
  assert.strictEqual(K.score(k["L-110"], 18.6, 25), 1.1);
  assert.strictEqual(K.score(k["L-110"], 33.5, 30), 0.9);
  assert.strictEqual(K.score(k["L-107"], 8.3, 3.75), 1.5);
  assert.strictEqual(K.score(k["L-109"], null, 0.03), null);
});

test("target changes by month", () => {
  assert.strictEqual(K.targetFor(cfg.kpis["L-110"], "2026-06"), 30);
  assert.strictEqual(K.targetFor(cfg.kpis["L-110"], "2026-07"), 25);
});

test("events: categories, production day, shift, machine", () => {
  const { events, noOrder } = K.prepareEvents(rows, cfg);
  assert.strictEqual(noOrder, 1);
  assert.deepStrictEqual(events.map((e) => e.category), ["Machine BD", "Applicator BD", "Machine BD", "Seal BD", "WPA BD"]);
  const e3 = events.find((e) => e.notification === 3);
  assert.strictEqual(e3.prod_day, "2026-08-03");
  assert.strictEqual(e3.shift, "3rd");
  assert.strictEqual(events[0].machine, "K01");
});

test("daily KPIs with exact working hours", () => {
  const { events } = K.prepareEvents(rows, cfg);
  const dt = events.filter((e) => cfg.downtime_categories.includes(e.category));
  const [d] = K.dailyKpis(dt, ["2026-08-03"], cfg, { "2026-08-03": [10, 10] }, false);
  assert.strictEqual(d.breakdowns, 3);                    // 30 + 10 + 60 min
  assert.ok(Math.abs(d.downtime_pct - (100 / 60) / 100) < 1e-12);
  assert.ok(Math.abs(d.mttr_min - 100 / 3) < 1e-12);
  assert.ok(Math.abs(d.mtbf_h - (100 - 100 / 60) / 3) < 1e-12);
  assert.strictEqual(d.breakdowns_gt_short, 2);           // the 10-minute call is a short stop
});

test("period value = average of daily values, Downtime % skips Fridays", () => {
  const daily = [
    { weekday: "Thu", downtime_pct: 0.02, mttr_min: 10, mtbf_h: 5, breakdowns: 1, breakdowns_gt_short: 1, downtime_h: 1, working_hours: 50 },
    { weekday: "Fri", downtime_pct: 0.50, mttr_min: 20, mtbf_h: 7, breakdowns: 1, breakdowns_gt_short: 1, downtime_h: 1, working_hours: 2 },
    { weekday: "Sat", downtime_pct: 0.04, mttr_min: 0, mtbf_h: null, breakdowns: 0, breakdowns_gt_short: 0, downtime_h: 2, working_hours: 50 },
  ];
  const a = K.aggregate(daily, cfg);
  assert.ok(Math.abs(a["L-109"] - 0.03) < 1e-12);
  assert.strictEqual(a["L-110"], 15);
  assert.strictEqual(a["L-107"], 6);
});

test("default working hours come from config, Friday override, single machine", () => {
  assert.strictEqual(K.workingHours("2026-08-03", cfg, {}, false), 24 * 60);
  const fri = cfg.production.weekday_overrides.Fri;
  assert.strictEqual(K.workingHours("2026-08-07", cfg, {}, false), fri.hours * fri.machines);
  assert.strictEqual(K.workingHours("2026-08-03", cfg, {}, true), 24);
});

test("weekly buckets start on Monday", () => {
  const days = K.daysBetween("2026-08-01", "2026-08-12");
  const b = K.buckets(K.dailyKpis([], days, cfg, {}, false), "week", cfg);
  assert.deepStrictEqual(b.map((x) => x.from), ["2026-08-01", "2026-08-03", "2026-08-10"]);
});
