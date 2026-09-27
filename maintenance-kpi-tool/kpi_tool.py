"""Maintenance KPI tool.

  python kpi_tool.py import-workbook "Maintenance KPIs - 2026.xlsm"
  python kpi_tool.py run aug.XLSX            (month is detected from the data)
  python kpi_tool.py run aug.XLSX --month 2026-08
"""
import argparse
import sys
from pathlib import Path

from mkpi import analysis, inputs, kpis, report, sap
from mkpi.config import load_config

HERE = Path(__file__).resolve().parent


def cmd_import(args):
    n_days, n_months, n_hist = inputs.import_workbook(args.workbook, args.data)
    print(f"Imported {n_days} production days, {n_months} months of planned-maintenance inputs "
          f"and {n_hist} months of KPI history into {args.data}/")


def cmd_run(args):
    cfg = load_config(args.config)
    raw = sap.read_sap_export(args.sap_file)
    events, no_order = sap.prepare_events(raw, cfg)
    month = args.month or events["prod_day"].dt.strftime("%Y-%m").mode()[0]
    events = events[events["prod_day"].dt.strftime("%Y-%m") == month]

    production = inputs.load_production(args.data)
    monthly_inputs = inputs.load_monthly_inputs(args.data, month)
    history = inputs.load_history(args.data)
    users = inputs.load_users(args.data)

    has_production = production is not None and (production.index.strftime("%Y-%m") == month).any()
    daily = kpis.daily_kpis(events, production if has_production else None, month, cfg)
    scorecard, basis = kpis.monthly_kpis(daily, monthly_inputs, month, cfg)

    prev_rows = history[history["month"] < month].sort_values("month")
    prev = prev_rows.iloc[-1].to_dict() if len(prev_rows) else {}
    if has_production:
        inputs.save_history_month(args.data, month, dict(zip(scorecard["kpi"], scorecard["value"])))
        history = inputs.load_history(args.data)

    dt_ev = events[events["in_downtime"]]
    ctx = {
        "month": month, "cfg": cfg, "sap_file": Path(args.sap_file).name, "events": events,
        "n_events": len(events), "n_downtime": len(dt_ev), "daily": daily,
        "scorecard": scorecard, "basis": basis, "prev": prev,
        "has_monthly_inputs": monthly_inputs is not None, "has_production": has_production,
        "machines": analysis.bad_actor_machines(dt_ev),
        "tools": analysis.bad_actor_tools(dt_ev),
        "damage": analysis.pareto(dt_ev, "damage"),
        "cause": analysis.pareto(dt_ev, "cause"),
        "object_part": analysis.pareto(dt_ev, "object_part"),
        "shift": analysis.by_shift(dt_ev),
        "repeats": analysis.repeat_failures(dt_ev),
        "technicians": analysis.technicians(dt_ev, users),
        "quality": analysis.data_quality(events, no_order, cfg),
        "long": analysis.long_breakdowns(events, cfg),
    }
    ctx["highlights"] = analysis.highlights(scorecard, prev, ctx["machines"], ctx["damage"],
                                            ctx["shift"], dt_ev, daily, cfg)
    ctx["charts"] = {
        "daily": report.chart_daily(daily, scorecard, cfg),
        "trend": report.chart_trend(history, cfg),
        "machines": report.chart_bars(ctx["machines"], "Top machines",
                                      lambda i: f"{i[0]} ({i[1].replace(' BD', '')})"),
        "tools": report.chart_bars(ctx["tools"], "Top applicators (tool ID)", color="#6fa0d8"),
        "damage": report.chart_bars(ctx["damage"], "Downtime by damage code", color="#1d3f6b"),
        "object_part": report.chart_bars(ctx["object_part"], "Downtime by object part", color="#1d3f6b"),
        "hours": report.chart_hours(analysis.by_hour(dt_ev)),
    }

    out_dir = Path(args.out) / month
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"KPI_Report_{month}.html"
    xlsx_path = out_dir / f"KPI_Details_{month}.xlsx"
    html_path.write_text(report.build_html(ctx), encoding="utf-8")
    report.write_excel(xlsx_path, ctx)

    print(f"\nMaintenance KPIs {month}")
    for _, r in scorecard.iterrows():
        v = "n/a" if r["value"] is None or r["value"] != r["value"] else (
            f"{r['value'] * 100:.2f}%" if r["unit"] == "%" else f"{r['value']:.2f} {r['unit']}")
        print(f"  {r['kpi']:6} {r['name']:22} {v:>12}   score {r['score'] if r['score'] is not None else '-':>4}   "
              f"{kpis.status_of(r['score'])}")
    if not has_production:
        print(f"\n  ! No production days for {month} in {args.data}/{inputs.PRODUCTION} – Downtime/MTTR/MTBF not calculated.")
    if monthly_inputs is None:
        print(f"  ! No row for {month} in {args.data}/{inputs.MONTHLY} – L-102/L-104/L-108 not calculated.")
    print(f"\nReport: {html_path}\nDetails: {xlsx_path}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Monthly maintenance KPI analysis from the SAP export")
    p.add_argument("--data", default=str(HERE / "data"), help="folder with the CSV inputs and history")
    p.add_argument("--out", default=str(HERE / "output"), help="folder for reports")
    p.add_argument("--config", default=None, help="config.json with targets and rules")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("import-workbook", help="one-time import from the old KPI Excel workbook")
    pi.add_argument("workbook")
    pi.set_defaults(func=cmd_import)
    pr = sub.add_parser("run", help="analyse one month's SAP export")
    pr.add_argument("sap_file")
    pr.add_argument("--month", help="YYYY-MM (default: detected from the data)")
    pr.set_defaults(func=cmd_run)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
