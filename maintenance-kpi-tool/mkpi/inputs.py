"""Non-SAP inputs: production days, monthly planned-maintenance figures and KPI history.

All of them live as CSV files in the data folder. `import_workbook` fills them once
from the old "Maintenance KPIs" Excel workbook so the history is not lost.
"""
from pathlib import Path

import openpyxl
import pandas as pd

PRODUCTION = "production_days.csv"
MONTHLY = "monthly_inputs.csv"
HISTORY = "history.csv"
USERS = "users.csv"

MONTHLY_COLUMNS = [
    "month", "team_attendance_hr", "app_requal_qty", "app_checks_qty", "seal_requal_qty",
    "seal_checks_qty", "subs_planned_hr_actual", "subs_planned_qty_actual",
    "subs_planned_hr_target", "subs_planned_qty_target", "cst_planned_hr_actual",
    "cst_planned_qty_actual", "cst_planned_hr_target", "cst_planned_qty_target",
]
KPI_IDS = ["L-109", "L-110", "L-107", "L-102", "L-104", "L-108"]


def _read_csv(data_dir, name, **kw):
    path = Path(data_dir) / name
    return pd.read_csv(path, **kw) if path.exists() else None


def load_production(data_dir):
    df = _read_csv(data_dir, PRODUCTION, parse_dates=["date"])
    if df is None:
        return None
    df["working_hours"] = df["shift_hours"] * df["working_machines"]
    return df.set_index("date")


def load_monthly_inputs(data_dir, month):
    df = _read_csv(data_dir, MONTHLY, dtype={"month": str})
    if df is None:
        return None
    row = df[df["month"] == month]
    return None if row.empty else row.iloc[-1].to_dict()


def load_history(data_dir):
    df = _read_csv(data_dir, HISTORY, dtype={"month": str})
    return df if df is not None else pd.DataFrame(columns=["month"] + KPI_IDS)


def save_history_month(data_dir, month, values):
    hist = load_history(data_dir)
    hist = hist[hist["month"] != month]
    row = {"month": month, **{k: values.get(k) for k in KPI_IDS}}
    hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True).sort_values("month")
    hist.to_csv(Path(data_dir) / HISTORY, index=False)


def load_users(data_dir):
    df = _read_csv(data_dir, USERS, dtype=str)
    return {} if df is None else dict(zip(df["user_id"].str.upper(), df["name"]))


# ---------------------------------------------------------------- old workbook import
MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
YEAR_ROWS = {  # row label in YEAR sheet -> monthly_inputs column
    "Team Attendance [Hr]": "team_attendance_hr",
    "Applicator Requalifications - 2Hr [Qty]": "app_requal_qty",
    "Applicator Checks - 10min [Qty]": "app_checks_qty",
    "SealTrack Requalifications - 1.5Hr [Qty]": "seal_requal_qty",
    "SealTrack Checks - 0.5Hr [Qty]": "seal_checks_qty",
    "Actual Subs Planned [Hrs]": "subs_planned_hr_actual",
    "Actual Subs Planned [Qty]": "subs_planned_qty_actual",
    "Target Subs Planned [Hrs]": "subs_planned_hr_target",
    "Target Subs Planned [Qty]": "subs_planned_qty_target",
    "Actual CST Planned [Hrs]": "cst_planned_hr_actual",
    "Actual CST Planned [Qty]": "cst_planned_qty_actual",
    "Target CST Planned [Hrs]": "cst_planned_hr_target",
    "Target CST Planned [Qty]": "cst_planned_qty_target",
}
KPI_ROW_PREFIX = {"L-109 Downtime": "L-109", "L-110 MTTR": "L-110", "L-107 MTBF": "L-107",
                  "L-102 Capacity": "L-102", "L-104 Proportion": "L-104",
                  "L-108 Proportion": "L-108"}


def import_workbook(xlsm_path, data_dir):
    """Copy production days, monthly inputs and KPI history out of the old workbook."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(xlsm_path, data_only=True, read_only=True)

    # Production days (Calc. Day sheet): date, hours per day, working machines
    day = pd.read_excel(xlsm_path, sheet_name="Calc. Day", header=2, usecols="A:C")
    day.columns = ["date", "shift_hours", "working_machines"]
    day = day[pd.to_datetime(day["date"], errors="coerce").notna()]
    day = day[pd.to_numeric(day["working_machines"], errors="coerce").fillna(0) > 0]
    day["date"] = pd.to_datetime(day["date"]).dt.strftime("%Y-%m-%d")
    day.to_csv(data_dir / PRODUCTION, index=False)

    # YEAR sheet: KPI values and monthly planned-maintenance inputs
    ws = wb["YEAR"]
    rows = list(ws.iter_rows(values_only=True))
    header = next(r for r in rows if isinstance(r[0], str) and r[0].startswith("KPI - "))
    year = header[0].split("-")[-1].strip()
    month_cols = {i: MONTH_ABBR.index(h) + 1 for i, h in enumerate(header) if h in MONTH_ABBR}

    monthly = {m: {"month": f"{year}-{m:02d}"} for m in month_cols.values()}
    history = {m: {"month": f"{year}-{m:02d}"} for m in month_cols.values()}
    for r in rows:
        label = (r[0] or "").strip() if isinstance(r[0], str) else ""
        col = YEAR_ROWS.get(label)
        kpi = next((k for p, k in KPI_ROW_PREFIX.items() if label.startswith(p)), None)
        for i, m in month_cols.items():
            v = r[i] if i < len(r) else None
            if not isinstance(v, (int, float)):
                continue
            if col:
                monthly[m][col] = v
            if kpi and v != 0:
                history[m][kpi] = v

    mdf = pd.DataFrame([v for v in monthly.values() if len(v) > 1], columns=MONTHLY_COLUMNS)
    mdf.dropna(subset=["team_attendance_hr"]).to_csv(data_dir / MONTHLY, index=False)
    hdf = pd.DataFrame([v for v in history.values() if len(v) > 1], columns=["month"] + KPI_IDS)
    hdf.to_csv(data_dir / HISTORY, index=False)
    return len(day), len(mdf.dropna(subset=["team_attendance_hr"])), len(hdf)
