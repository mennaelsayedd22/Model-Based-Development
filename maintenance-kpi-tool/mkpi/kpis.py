"""Daily and monthly KPI calculation (same logic as the old Calc. Day / YEAR sheets)."""
import pandas as pd

from .config import score, target_for


def daily_kpis(events, production, month, cfg):
    """One row per production day of `month`.

    Downtime % = breakdown hours / (shift hours x working machines)
    MTTR       = breakdown minutes / number of breakdowns
    MTBF       = (working hours - breakdown hours) / number of breakdowns
    """
    start = pd.Timestamp(month + "-01")
    days = pd.date_range(start, start + pd.offsets.MonthEnd(0), freq="D")
    ev = events[events["in_downtime"]]
    ev = ev[ev["prod_day"].isin(days)]

    g = ev.groupby("prod_day")
    out = pd.DataFrame(index=days)
    out.index.name = "date"
    out["weekday"] = out.index.strftime("%a")
    out["working_hours"] = production["working_hours"].reindex(days) if production is not None else None
    out["breakdowns"] = g.size().reindex(days).fillna(0).astype(int)
    out["breakdowns_gt_short"] = (ev[ev["breakdown_min"] > cfg["short_stop_minutes"]]
                                  .groupby("prod_day").size().reindex(days).fillna(0).astype(int))
    out["downtime_h"] = (g["breakdown_min"].sum() / 60).reindex(days).fillna(0)
    for cat in cfg["downtime_categories"]:
        out[f"{cat} h"] = (ev[ev["category"] == cat].groupby("prod_day")["breakdown_min"].sum()
                           / 60).reindex(days).fillna(0)
    out["waiting_min_avg"] = g["waiting_min"].mean().reindex(days)
    out["repair_min_avg"] = g["repair_min"].mean().reindex(days)

    wh = out["working_hours"]
    n = out["breakdowns"].where(out["breakdowns"] > 0)
    out["downtime_pct"] = out["downtime_h"] / wh
    out["mttr_min"] = out["downtime_h"] * 60 / n
    out["mtbf_h"] = (wh - out["downtime_h"]) / n
    return out


def _mean_nonzero(s):
    s = pd.to_numeric(s, errors="coerce")
    s = s[s.notna() & (s != 0)]
    return float(s.mean()) if len(s) else None


def monthly_kpis(daily, monthly_inputs, month, cfg):
    """KPI values, targets and scores for the month plus the numbers behind them."""
    counted = daily[~daily["weekday"].isin(cfg["downtime_excluded_weekdays"])]
    values = {
        "L-109": _mean_nonzero(counted["downtime_pct"]),
        "L-110": _mean_nonzero(daily["mttr_min"]),
        "L-107": _mean_nonzero(daily["mtbf_h"]),
    }
    unplanned_hr = float((counted["downtime_pct"].fillna(0) * counted["working_hours"].fillna(0)).sum())
    unplanned_qty = int(daily["breakdowns_gt_short"].sum())
    basis = {"Unplanned maint. [Hr]": unplanned_hr, "Unplanned maint. [Qty]": unplanned_qty,
             "Breakdowns (all)": int(daily["breakdowns"].sum()),
             "Downtime hours (all days)": float(daily["downtime_h"].sum()),
             "Working hours": float(daily["working_hours"].sum())}

    if monthly_inputs:
        mi, hrs = monthly_inputs, cfg["planned_hours_per_task"]
        app_hr = mi["app_requal_qty"] * hrs["app_requal"] + mi["app_checks_qty"] * hrs["app_check"]
        seal_hr = mi["seal_requal_qty"] * hrs["seal_requal"] + mi["seal_checks_qty"] * hrs["seal_check"]
        app_qty = mi["app_requal_qty"] + mi["app_checks_qty"]
        seal_qty = mi["seal_requal_qty"] + mi["seal_checks_qty"]
        planned_hr = app_hr + seal_hr + mi["subs_planned_hr_actual"] + mi["cst_planned_hr_actual"]
        planned_qty = app_qty + seal_qty + mi["subs_planned_qty_actual"] + mi["cst_planned_qty_actual"]
        target_qty = app_qty + seal_qty + mi["subs_planned_qty_target"] + mi["cst_planned_qty_target"]
        values["L-102"] = (unplanned_hr + planned_hr) / mi["team_attendance_hr"]
        values["L-104"] = planned_qty / target_qty
        values["L-108"] = unplanned_qty / (unplanned_qty + planned_qty)
        basis.update({"Team attendance [Hr]": mi["team_attendance_hr"],
                      "Planned maint. [Hr]": planned_hr, "Planned maint. [Qty]": planned_qty,
                      "Target planned maint. [Qty]": target_qty})

    rows = []
    for kpi_id, kc in cfg["kpis"].items():
        value = values.get(kpi_id)
        target = target_for(kc, month)
        rows.append({"kpi": kpi_id, "name": kc["name"], "unit": kc["unit"], "better": kc["better"],
                     "value": value, "target": target, "score": score(kc, value, target)})
    return pd.DataFrame(rows), basis


def status_of(score_value):
    if score_value is None or score_value != score_value:
        return "no data"
    if score_value >= 1:
        return "on target"
    return "close" if score_value >= 0.9 else "off target"
