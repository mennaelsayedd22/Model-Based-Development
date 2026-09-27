"""Open the maintenance KPI dashboard for any SAP breakdown export.

    kpi                              -> choose the SAP file(s) in a window
    kpi export.xlsx                  -> one file (any period: a week, a month, a year ...)
    kpi jan.xlsx feb.xlsx mar.xlsx   -> several files, merged
    kpi C:\\SAP\\exports              -> every .xlsx file in the folder

Options:
    --production days.csv   exact working hours per day (columns: date,shift_hours,working_machines).
                            If production_days.csv is in this folder it is used automatically.
    --out folder            where the dashboard is saved (default: output next to this script)
    --no-open               only save the dashboard, do not open the browser
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DASH = HERE / "dashboard"

REQUIRED = ["Notification", "Order", "Equipment description", "Description",
            "Notification Start Time/Date Stamp", "Total Breakdown", "Waiting Time", "Intervention Time"]
OPTIONAL = ["Equipment.1", "DamageCode Short text", "Cause short text", "Object Parts short text",
            "WO Confirmation Creator Stamp"]
COLUMNS = REQUIRED + OPTIONAL
STAMP = "Notification Start Time/Date Stamp"


def norm(h):
    return re.sub(r"\s+", " ", str(h if h is not None else "")).strip()


def read_sap(path):
    """Return {notification: row-list in COLUMNS order} for one SAP export."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header, seen = [], {}
    for h in next(rows):
        h = norm(h)
        if h in seen:  # second "Equipment" column holds the tool / applicator ID
            seen[h] += 1
            h = f"{h}.{seen[h]}"
        else:
            seen[h] = 0
        header.append(h)
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ValueError(f"{path.name} does not look like the SAP breakdown export (missing: {', '.join(missing)})")
    idx = [header.index(c) if c in header else None for c in COLUMNS]

    out = {}
    for r in rows:
        if r is None or all(v is None for v in r):
            continue
        vals = []
        for c, i in zip(COLUMNS, idx):
            v = r[i] if i is not None and i < len(r) else None
            if isinstance(v, dt.datetime):
                v = v.strftime("%d.%m.%Y %H:%M:%S") if c == STAMP else v.isoformat(sep=" ")
            elif isinstance(v, (dt.date, dt.time)):
                v = v.isoformat()
            elif isinstance(v, float) and v.is_integer():
                v = int(v)
            vals.append(v)
        out[vals[0]] = vals
    wb.close()
    return out


def collect_files(args):
    files = []
    for a in args:
        p = Path(a).expanduser()
        if p.is_dir():
            found = sorted(f for f in p.iterdir()
                           if f.suffix.lower() in (".xlsx", ".xlsm") and not f.name.startswith("~$"))
            if not found:
                print(f"  (no .xlsx files in {p})")
            files.extend(found)
        elif p.exists():
            files.append(p)
        else:
            sys.exit(f"File not found: {p}")
    return files


def pick_files():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        sys.exit(__doc__)
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    chosen = filedialog.askopenfilenames(title="Choose the SAP breakdown export(s)",
                                         filetypes=[("Excel", "*.xlsx *.XLSX *.xlsm"), ("All files", "*.*")])
    root.destroy()
    return [Path(f) for f in chosen]


def read_production(path):
    prod = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                d = row["date"].strip()[:10]
                if re.match(r"\d{1,2}[./]\d{1,2}[./]\d{4}", d):
                    day, month, year = re.split(r"[./]", d)
                    d = f"{year}-{int(month):02d}-{int(day):02d}"
                prod[d] = [float(row["shift_hours"]), float(row["working_machines"])]
            except (KeyError, ValueError):
                continue
    return prod


def period_of(rows):
    days = []
    for r in rows:
        try:
            days.append(dt.datetime.strptime(str(r[COLUMNS.index(STAMP)])[:10], "%d.%m.%Y").date())
        except ValueError:
            pass
    return (min(days), max(days)) if days else (None, None)


def build_html(payload):
    html = (DASH / "template.html").read_text(encoding="utf-8")
    scripts = {
        "/*__XLSX__*/": DASH / "vendor" / "xlsx.full.min.js",
        "/*__CHARTJS__*/": DASH / "vendor" / "chart.umd.js",
        "/*__ENGINE__*/": DASH / "engine.js",
        "/*__APP__*/": DASH / "app.js",
    }
    for marker, path in scripts.items():
        html = html.replace(marker, path.read_text(encoding="utf-8").replace("</script", "<\\/script"))
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return html.replace("/*__DATA__*/null", data)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Maintenance KPI dashboard from SAP breakdown exports",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("files", nargs="*", help="SAP export file(s) or a folder")
    ap.add_argument("--production", help="CSV with exact working hours per day")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--out", default=str(HERE / "output"))
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)

    files = collect_files(args.files) if args.files else pick_files()
    if not files:
        sys.exit("No SAP file chosen.")

    merged = {}
    for f in files:
        print(f"Reading {f.name} ...", end=" ", flush=True)
        try:
            rows = read_sap(f)
        except Exception as e:  # noqa: BLE001 - show a clear message instead of a stack trace
            print(f"skipped: {e}")
            continue
        print(f"{len(rows):,} rows")
        merged.update(rows)  # later files win for the same notification
    if not merged:
        sys.exit("No usable SAP rows found.")

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    prod_file = Path(args.production) if args.production else HERE / "production_days.csv"
    production = read_production(prod_file) if prod_file.exists() else {}
    if args.production and not prod_file.exists():
        sys.exit(f"Production file not found: {prod_file}")
    if production:
        print(f"Working hours from {prod_file.name} ({len(production)} days)")
    rows = list(merged.values())
    first, last = period_of(rows)
    payload = {"files": [f.name for f in files], "columns": COLUMNS, "rows": rows,
               "config": config, "production": production,
               "created": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"KPI_Dashboard_{first:%Y-%m-%d}_to_{last:%Y-%m-%d}.html" if first else "KPI_Dashboard.html"
    out = out_dir / name
    out.write_text(build_html(payload), encoding="utf-8")
    print(f"\n{len(rows):,} notifications from {first} to {last}")
    print(f"Dashboard: {out}")
    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
