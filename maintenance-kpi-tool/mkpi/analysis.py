"""Root-cause views of the month: where the downtime comes from."""
import pandas as pd

from .kpis import status_of


def _summary(ev, by):
    g = ev.groupby(by)
    out = pd.DataFrame({
        "breakdowns": g.size(),
        "downtime_h": g["breakdown_min"].sum() / 60,
        "mttr_min": g["breakdown_min"].mean(),
        "avg_waiting_min": g["waiting_min"].mean(),
        "avg_repair_min": g["repair_min"].mean(),
    })
    total = out["downtime_h"].sum()
    out["share_%"] = 100 * out["downtime_h"] / total if total else 0
    return out.sort_values("downtime_h", ascending=False)


def pareto(ev, col, top=10):
    out = _summary(ev, col)
    out["cum_%"] = out["share_%"].cumsum()
    return out.head(top)


def bad_actor_machines(ev, top=10):
    out = _summary(ev, ["machine", "category"]).head(top)
    parts = (ev.groupby(["machine", "category", "object_part"])["breakdown_min"].sum()
             .reset_index().sort_values("breakdown_min", ascending=False)
             .drop_duplicates(["machine", "category"]).set_index(["machine", "category"])["object_part"])
    out["main_object_part"] = parts.reindex(out.index)
    return out


def bad_actor_tools(ev, top=10):
    app = ev[ev["category"] == "Applicator BD"].copy()
    app["tool_id"] = app["tool_id"].fillna(0).astype("int64").astype(str)
    return _summary(app, "tool_id").head(top)


def by_shift(ev):
    return _summary(ev, "shift").sort_index()


def by_hour(ev):
    return ev.groupby("hour").agg(breakdowns=("breakdown_min", "size"),
                                  downtime_h=("breakdown_min", lambda s: s.sum() / 60))


def repeat_failures(ev, min_count=3):
    g = ev.groupby(["machine", "object_part"]).agg(
        breakdowns=("breakdown_min", "size"), downtime_h=("breakdown_min", lambda s: s.sum() / 60),
        days=("prod_day", "nunique"))
    g = g[(g["breakdowns"] >= min_count) & (g.index.get_level_values("object_part") != "(not coded)")]
    return g.sort_values(["breakdowns", "downtime_h"], ascending=False)


def technicians(ev, users):
    out = _summary(ev, "technician")
    out.insert(0, "name", [users.get(t, "") for t in out.index])
    return out.sort_values("breakdowns", ascending=False)


def data_quality(events, no_order, cfg):
    ev = events
    checks = [
        ("Notifications without a work order (ignored in KPIs)", len(no_order)),
        ("Calls with an unknown fault code (category 'Unclassified')", int((ev["category"] == "Unclassified").sum())),
        ("Calls without damage code", int((ev["damage"] == "(not coded)").sum())),
        ("Calls without cause", int((ev["cause"] == "(not coded)").sum())),
        (f"Breakdowns longer than {cfg['long_breakdown_minutes']} min (check they are real)",
         int((ev["breakdown_min"] > cfg["long_breakdown_minutes"]).sum())),
        ("Calls with zero breakdown time", int((ev["breakdown_min"] <= 0).sum())),
    ]
    return pd.DataFrame(checks, columns=["check", "count"])


def long_breakdowns(ev, cfg):
    cols = ["Notification", "Order", "machine", "category", "start", "breakdown_min",
            "waiting_min", "repair_min", "object_part", "Description"]
    return ev[ev["breakdown_min"] > cfg["long_breakdown_minutes"]][cols].sort_values(
        "breakdown_min", ascending=False)


def _fmt(v, unit):
    if v is None or v != v:
        return "n/a"
    return f"{v * 100:.2f}%" if unit == "%" else f"{v:.{2 if abs(v) < 10 else 1}f} {unit}"


def highlights(scorecard, prev, machines, damage, shift, ev, daily, cfg):
    """Plain-language bullets for the top of the report."""
    out = []
    for _, r in scorecard.iterrows():
        st = status_of(r["score"])
        if st == "no data":
            continue
        line = f"{r['kpi']} {r['name']}: {_fmt(r['value'], r['unit'])} vs target {_fmt(r['target'], r['unit'])} ({st}, score {r['score']:.1f})"
        p = prev.get(r["kpi"]) if prev else None
        if p is not None and p == p and r["value"]:
            better = (r["value"] < p) == (r["better"] == "lower")
            line += f"; {'better' if better else 'worse'} than last month ({_fmt(p, r['unit'])})"
        out.append((st, line))

    if len(machines):
        top3 = machines.head(3)
        share = top3["share_%"].sum()
        names = ", ".join(f"{m} ({c.replace(' BD', '')}, {h:.1f} h)" for (m, c), h in top3["downtime_h"].items())
        out.append(("info", f"Top 3 machines cause {share:.0f}% of downtime: {names}."))
    if len(damage):
        d = damage.iloc[0]
        out.append(("info", f"Biggest damage type: {damage.index[0]} ({d['share_%']:.0f}% of downtime hours)."))
    if len(shift):
        worst = shift["downtime_h"].idxmax()
        out.append(("info", f"Shift with most downtime: {worst} ({shift.loc[worst, 'downtime_h']:.1f} h, "
                            f"{shift.loc[worst, 'breakdowns']} calls)."))
    if len(ev):
        wait, rep = ev["waiting_min"].mean(), ev["repair_min"].mean()
        out.append(("info", f"Average call: {wait:.1f} min waiting for a technician + {rep:.1f} min repair."))
    counted = daily.loc[~daily["weekday"].isin(cfg["downtime_excluded_weekdays"]), "downtime_pct"]
    if counted.notna().any():
        worst_day = counted.idxmax()
        out.append(("info", f"Worst day: {worst_day:%a %d %b} with {counted[worst_day] * 100:.1f}% downtime."))
    return out
