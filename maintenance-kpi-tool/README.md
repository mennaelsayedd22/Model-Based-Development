# Maintenance KPI Dashboard

Type one command, give it any SAP breakdown export, and an interactive dashboard opens in
your browser. The export can cover a week, a month, a year, or several files together.

```
kpi C:\SAP\export.XLSX
```

The dashboard shows:
- **KPIs:** L-109 Downtime %, L-110 MTTR and L-107 MTBF, with targets, 0–1.5 scores and a comparison with the previous period.
- **Trends** by day, week or month.
- **Where the downtime comes from:** bad-actor machines and applicators, damage codes, object parts, repeat failures, shifts and hours, causes and technicians.
- **Data-quality checks.**

**Filters:** date range, month buttons, categories, and a single machine. You can also click a machine to drill down.
**Download Excel** exports the current view. **Print / PDF** prints it.

The dashboard is a single HTML file saved in `output\`. It works offline and nothing is uploaded.

> **This repository is public.** Never commit SAP exports, production files or dashboards.
> `.gitignore` already blocks `*.xlsx`, `*.csv` and `output/`.

## Install (once, on your laptop)

1. Install Python 3 from python.org and tick **"Add Python to PATH"** during setup.
2. Download this folder (`maintenance-kpi-tool`) to your laptop, for example `C:\Tools\maintenance-kpi-tool`.
3. Open a command window in that folder and run:
   ```
   pip install -r requirements.txt
   ```
4. Optional, so you can type `kpi` from any folder: add `C:\Tools\maintenance-kpi-tool` to your PATH.
   Start → "Edit environment variables for your account" → Path → New.

## Use

```
kpi                                  choose the SAP file(s) in a window
kpi C:\SAP\aug.XLSX                  one file, any period
kpi jul.XLSX aug.XLSX sep.XLSX       several files, merged (duplicates removed)
kpi C:\SAP\exports                   every .xlsx file in the folder
```

If `kpi` is not on your PATH, run `python kpi.py ...` from inside the tool folder instead.

## Working hours (not in SAP)

Downtime % and MTBF need the working hours of each day: hours × working machines.

- **Exact:** put a file `production_days.csv` in the tool folder and it is used automatically.
  You can also pass one with `--production file.csv`.
  ```
  date,shift_hours,working_machines
  2026-08-01,24,60.08
  2026-08-02,24,60.49
  ```
- **Otherwise** the defaults in `config.json` are used: 60 machines × 24 h, and Fridays 12 h × 41 machines.
  These are close but not exact, because real days vary (holidays, short Thursdays, and so on).

## Settings: `config.json`

| Setting | Meaning |
|---|---|
| `production` | default hours per day and working machines, with per-weekday overrides |
| `kpis.*.targets` | targets; add `{"from": "2026-10", "target": 0.025}` to change one from a given month |
| `downtime_categories` | categories counted in the KPIs (Machine BD and Applicator BD) |
| `fault_code_categories` | first letter of the notification description → category |
| `day_start_hour` | the production day starts at 07:00 |
| `technician_names` | `{"SAP_USER_ID": "Name"}` to show names instead of IDs |

## How the KPIs are calculated

This is the same logic as the old `Maintenance KPIs` workbook.

- **Rows used:** only notifications that have a work order.
- **Production day:** runs from 07:00 to 07:00.
- **Shifts:** 1st 07–15, 2nd 15–23, 3rd 23–07.
- **Category:** comes from the fault code at the start of the description:
  `D` Machine, `E` Applicator, `F` Seal, `N` IT. A `D` on WPA equipment is WPA.
- **Per day:**
  - Downtime % = breakdown h ÷ working h
  - MTTR = breakdown min ÷ calls
  - MTBF = (working h − breakdown h) ÷ calls
- **For a period:** the average of the daily values. Downtime % skips Fridays.
- **Scores:** the workbook's 0–1.5 bands, using the targets valid in the last month of the period.

L-102, L-104 and L-108 are not included. They need planned-maintenance counts that are not in the
breakdown export.

## For developers

- `kpi.py` reads the Excel files with openpyxl and writes the data, `config.json` and the
  `dashboard/` files into one HTML file.
- `dashboard/engine.js` holds all the calculations.
- Tests: `node --test tests/engine.test.js`
