# Maintenance KPI tool

Turns the monthly SAP breakdown export into the maintenance KPI report
(L-109 Downtime, L-110 MTTR, L-107 MTBF, L-102 Capacity utilization, L-104 Proportion PM,
L-108 Proportion unplanned). It adds root-cause analysis on top: bad-actor machines and
applicators, Pareto charts, repeat failures, shift and hour patterns, and data-quality checks.

It uses the same calculations and 0–1.5 score bands as the old `Maintenance KPIs - 2026.xlsm`
workbook. For January–August 2026, every score the tool calculates matches the workbook.

> **This repository is public.** Never commit SAP exports, the KPI workbook or anything in
> `data/` or `output/`. `.gitignore` already blocks them.

## Setup (once)

```bash
pip install -r requirements.txt
python kpi_tool.py import-workbook "Maintenance KPIs - 2026.xlsm"
```

The import fills `data/` with:

| File | What it holds | Where it comes from |
|---|---|---|
| `production_days.csv` | date, shift hours, working machines per day | `Calc. Day` sheet |
| `monthly_inputs.csv` | team attendance and planned-maintenance counts per month | `YEAR` sheet |
| `history.csv` | KPI values per month (for trends and "vs last month") | `YEAR` sheet |

Optionally add `data/users.csv` (`user_id,name`) to show technician names instead of SAP user IDs.

## Every month

1. Export the breakdown report from SAP (same layout as `aug.XLSX`).
2. Add the month's production days to `data/production_days.csv`.
3. Add one row for the month to `data/monthly_inputs.csv` (team attendance, applicator and
   seal-track requalifications and checks, subs and CST planned work).
4. Run:

```bash
python kpi_tool.py run "sep.XLSX"
```

You get `output/2026-09/KPI_Report_2026-09.html`, a report that opens in any browser and
works offline, and `KPI_Details_2026-09.xlsx`, which has every table plus the cleaned event list.

Templates for the CSV files are in `templates/`.

## How it calculates

- **Events**: SAP rows that have a work order. The production day runs 07:00 → 07:00.
  Shifts are 1st 07–15, 2nd 15–23 and 3rd 23–07.
- **Category** comes from the fault code at the start of the notification description:
  `D` Machine BD, `E` Applicator BD, `F` Seal BD, `N` IT BD. A `D` on WPA equipment is WPA BD.
- **Downtime** counts Machine BD and Applicator BD. This is the rule since May 2026, set in `config.json`.
- **Daily values**:
  - Downtime % = breakdown h ÷ (hours × working machines)
  - MTTR = breakdown min ÷ calls
  - MTBF = (working h − breakdown h) ÷ calls
- **Monthly values**: the average of the daily values. Downtime % skips Fridays.
- **L-102** = (unplanned h + planned h) ÷ team attendance h
- **L-104** = planned tasks done ÷ planned target
- **L-108** = calls over 10 min ÷ (those calls + planned tasks)

Targets, score steps, categories and the day start are all in `config.json`. When a target
changes, add a new `{"from": "YYYY-MM", "target": ...}` entry so older months keep their old target.

## Tests

```bash
python -m pytest tests
```
