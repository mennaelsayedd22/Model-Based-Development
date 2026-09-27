"""HTML report (charts embedded, opens offline) and Excel details workbook."""
import base64
import html
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import target_for  # noqa: E402
from .kpis import status_of  # noqa: E402

BLUE, GREY, RED, GREEN, AMBER = "#2f6db5", "#b8c0cc", "#c0392b", "#2e8b57", "#d4a017"
STATUS_COLOR = {"on target": GREEN, "close": AMBER, "off target": RED, "no data": GREY}

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True})


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _fmt(v, unit):
    if v is None or v != v:
        return "–"
    return f"{v * 100:.2f}%" if unit == "%" else f"{v:.{2 if abs(v) < 10 else 1}f} {unit}"


# ------------------------------------------------------------------------ charts
def chart_daily(daily, scorecard, cfg):
    tgt = scorecard.set_index("kpi")["target"]
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True)
    x = daily.index
    excluded = daily["weekday"].isin(cfg["downtime_excluded_weekdays"])
    colors = [GREY if e else (RED if v > tgt["L-109"] else BLUE)
              for e, v in zip(excluded, daily["downtime_pct"].fillna(0))]
    axes[0].bar(x, daily["downtime_pct"] * 100, color=colors, width=0.8)
    axes[0].axhline(tgt["L-109"] * 100, color="black", ls="--", lw=1)
    axes[0].set_ylabel("Downtime %")
    axes[0].set_title("Daily downtime % (red = above target, grey = not counted)", loc="left")
    for ax, col, k, label in [(axes[1], "mttr_min", "L-110", "MTTR (min)"),
                              (axes[2], "mtbf_h", "L-107", "MTBF (h)")]:
        ax.plot(x, daily[col], color=BLUE, marker="o", ms=3)
        ax.axhline(tgt[k], color="black", ls="--", lw=1)
        ax.set_ylabel(label)
    axes[2].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d"))
    fig.tight_layout()
    return _png(fig)


def chart_trend(history, cfg):
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.5))
    for ax, (k, kc) in zip(axes.flat, cfg["kpis"].items()):
        h = history[["month", k]].dropna() if k in history else pd.DataFrame(columns=["month", k])
        scale = 100 if kc["unit"] == "%" else 1
        ax.plot(h["month"].str[2:], h[k] * scale, color=BLUE, marker="o", ms=4)
        tg = [target_for(kc, m) for m in h["month"]]
        ax.plot(h["month"].str[2:], [t * scale for t in tg], color="black", ls="--", lw=1)
        ax.set_title(f"{k} {kc['name']} [{kc['unit']}]", loc="left")
        ax.tick_params(axis="x", rotation=60, labelsize=7)
    fig.tight_layout()
    return _png(fig)


def chart_bars(df, title, label_fn=str, color=BLUE):
    d = df.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.barh([label_fn(i) for i in d.index], d["downtime_h"], color=color)
    for i, (h, s) in enumerate(zip(d["downtime_h"], d["share_%"])):
        ax.text(h, i, f" {h:.1f} h ({s:.0f}%)", va="center", fontsize=7)
    ax.set_title(title, loc="left")
    ax.set_xlabel("Downtime hours")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, d["downtime_h"].max() * 1.35 if len(d) else 1)
    fig.tight_layout()
    return _png(fig)


def chart_hours(hours):
    order = list(range(7, 24)) + list(range(0, 7))
    h = hours.reindex(order).fillna(0)
    fig, ax = plt.subplots(figsize=(10, 2.8))
    colors = [BLUE if 7 <= i < 15 else ("#6fa0d8" if 15 <= i < 23 else "#1d3f6b") for i in order]
    ax.bar([f"{i:02d}" for i in order], h["breakdowns"], color=colors)
    ax.set_title("Breakdown calls by hour of day (colour = shift 1st / 2nd / 3rd)", loc="left")
    ax.set_ylabel("Calls")
    fig.tight_layout()
    return _png(fig)


# ------------------------------------------------------------------------ HTML
def _table(df, fmt=None, index=True):
    fmt = fmt or {}
    d = df.copy()
    for c in d.columns:
        if c in fmt:
            d[c] = d[c].map(lambda v, f=fmt[c]: "" if v is None or v != v else f.format(v))
        elif pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if v != v else f"{v:,.1f}")
    return d.to_html(index=index, border=0, classes="t", escape=True)


CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f9;color:#1f2933}
main{max-width:1100px;margin:auto;padding:24px 16px}
h1{margin:0 0 4px;font-size:24px} h2{margin:32px 0 10px;font-size:18px;border-bottom:2px solid #d9dee5;padding-bottom:4px}
.sub{color:#5b6775;margin-bottom:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}
.card{background:#fff;border-radius:8px;padding:12px 14px;border-left:6px solid #ccc;box-shadow:0 1px 2px #0001}
.card .k{font-size:12px;color:#5b6775}.card .v{font-size:24px;font-weight:600;margin:4px 0}
.card .s{font-size:12px}
ul.hl{background:#fff;border-radius:8px;padding:12px 12px 12px 32px;box-shadow:0 1px 2px #0001}
ul.hl li{margin:4px 0}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:12px}
.box{background:#fff;border-radius:8px;padding:10px;box-shadow:0 1px 2px #0001;overflow-x:auto}
img{max-width:100%}
table.t{border-collapse:collapse;font-size:12px;width:100%}
table.t th{background:#e8ecf1;text-align:left;padding:4px 6px}
table.t td{padding:3px 6px;border-bottom:1px solid #eef0f3}
.note{font-size:12px;color:#5b6775}
"""


def build_html(ctx):
    month_name = pd.Timestamp(ctx["month"] + "-01").strftime("%B %Y")
    cards = []
    for _, r in ctx["scorecard"].iterrows():
        st = status_of(r["score"])
        prev = ctx["prev"].get(r["kpi"]) if ctx["prev"] else None
        delta = f" · last month {_fmt(prev, r['unit'])}" if prev == prev and prev is not None else ""
        sc = "" if r["score"] is None or r["score"] != r["score"] else f" · score {r['score']:.1f}"
        cards.append(
            f'<div class="card" style="border-left-color:{STATUS_COLOR[st]}">'
            f'<div class="k">{html.escape(r["kpi"])} {html.escape(r["name"])}</div>'
            f'<div class="v">{_fmt(r["value"], r["unit"])}</div>'
            f'<div class="s">target {_fmt(r["target"], r["unit"])}{sc}<br>'
            f'<b style="color:{STATUS_COLOR[st]}">{st}</b>{delta}</div></div>')

    bullets = "".join(
        f'<li style="color:{STATUS_COLOR.get(s, "inherit")}"><span style="color:#1f2933">{html.escape(t)}</span></li>'
        for s, t in ctx["highlights"])

    img = lambda b: f'<img src="data:image/png;base64,{b}">'  # noqa: E731
    pct = "{:.0f}%"
    summ_fmt = {"share_%": pct, "cum_%": pct, "breakdowns": "{:,.0f}"}
    missing = "" if ctx["has_monthly_inputs"] else (
        '<p class="note">L-102, L-104 and L-108 need the monthly planned-maintenance figures '
        f'(add a row for {ctx["month"]} to data/monthly_inputs.csv).</p>')
    if not ctx["has_production"]:
        missing += ('<p class="note"><b>No production days found for this month</b> – add them to '
                    'data/production_days.csv, otherwise Downtime %, MTTR and MTBF cannot be calculated.</p>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Maintenance KPI {month_name}</title><style>{CSS}</style></head><body><main>
<h1>Maintenance KPI report – {month_name}</h1>
<div class="sub">Source: {html.escape(ctx["sap_file"])} · {ctx["n_events"]:,} breakdown calls with work order ·
{ctx["n_downtime"]:,} counted in downtime ({", ".join(ctx["cfg"]["downtime_categories"])})</div>
<div class="cards">{"".join(cards)}</div>{missing}
<h2>Highlights</h2><ul class="hl">{bullets}</ul>
<h2>Daily performance</h2><div class="box">{img(ctx["charts"]["daily"])}</div>
<h2>Trend this year</h2><div class="box">{img(ctx["charts"]["trend"])}
<p class="note">Dashed line = target.</p></div>
<h2>Where does the downtime come from?</h2>
<div class="grid2">
<div class="box">{img(ctx["charts"]["machines"])}</div>
<div class="box">{img(ctx["charts"]["tools"])}</div>
<div class="box">{img(ctx["charts"]["damage"])}</div>
<div class="box">{img(ctx["charts"]["object_part"])}</div>
</div>
<h2>Bad actor machines</h2><div class="box">{_table(ctx["machines"], summ_fmt)}</div>
<h2>Repeat failures (same machine + same part ≥ 3 times)</h2>
<div class="box">{_table(ctx["repeats"].head(15), summ_fmt)}</div>
<h2>Shifts and hours</h2>
<div class="box">{_table(ctx["shift"], summ_fmt)}{img(ctx["charts"]["hours"])}</div>
<h2>Causes</h2><div class="box">{_table(ctx["cause"], summ_fmt)}</div>
<h2>Data quality</h2><div class="box">{_table(ctx["quality"], index=False)}
<p class="note">Long breakdowns are listed in the Excel file (sheet "Long breakdowns") so you can check them in SAP.</p></div>
<h2>How the KPIs are calculated</h2><div class="box note">
Production day runs {ctx["cfg"]["day_start_hour"]:02d}:00 → {ctx["cfg"]["day_start_hour"]:02d}:00. Category comes from the fault code at the
start of the notification description (D = Machine, E = Applicator, F = Seal, N = IT; D on WPA equipment = WPA).<br>
Daily: Downtime % = breakdown hours ÷ (hours × working machines); MTTR = breakdown minutes ÷ calls; MTBF = (working hours − breakdown hours) ÷ calls.<br>
Monthly: average of the daily values (Downtime % skips {", ".join(ctx["cfg"]["downtime_excluded_weekdays"])}).
L-102 = (unplanned + planned hours) ÷ team attendance; L-104 = planned done ÷ planned target;
L-108 = calls &gt; {ctx["cfg"]["short_stop_minutes"]} min ÷ (those calls + planned tasks). Scores use the same 0–1.5 bands as the old workbook.
</div>
</main></body></html>"""


def write_excel(path, ctx):
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        sc = ctx["scorecard"].copy()
        sc["status"] = sc["score"].map(status_of)
        sc.to_excel(xw, sheet_name="Scorecard", index=False)
        pd.DataFrame(list(ctx["basis"].items()), columns=["item", "value"]).to_excel(
            xw, sheet_name="Scorecard", index=False, startrow=len(sc) + 3)
        ctx["daily"].to_excel(xw, sheet_name="Daily")
        ctx["machines"].to_excel(xw, sheet_name="Bad actor machines")
        ctx["tools"].to_excel(xw, sheet_name="Bad actor applicators")
        ctx["repeats"].to_excel(xw, sheet_name="Repeat failures")
        ctx["damage"].to_excel(xw, sheet_name="Pareto damage")
        ctx["cause"].to_excel(xw, sheet_name="Pareto cause")
        ctx["object_part"].to_excel(xw, sheet_name="Pareto object part")
        ctx["shift"].to_excel(xw, sheet_name="Shifts")
        ctx["technicians"].to_excel(xw, sheet_name="Technicians")
        ctx["quality"].to_excel(xw, sheet_name="Data quality", index=False)
        ctx["long"].to_excel(xw, sheet_name="Long breakdowns", index=False)
        cols = ["Notification", "Order", "prod_day", "shift", "start", "machine", "group", "category",
                "fault_code", "breakdown_min", "waiting_min", "repair_min", "damage", "cause",
                "object_part", "technician", "tool_id", "in_downtime", "Description"]
        ctx["events"][cols].to_excel(xw, sheet_name="Events", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 45)
