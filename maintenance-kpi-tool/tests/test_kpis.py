"""Tests on small made-up data (no company data in this repository)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mkpi import kpis, sap  # noqa: E402
from mkpi.config import load_config, score, target_for  # noqa: E402

CFG = load_config()


def test_scores_match_old_workbook_bands():
    k = CFG["kpis"]
    assert score(k["L-109"], 0.0379, 0.03) == 0.6
    assert score(k["L-109"], 0.019, 0.03) == 1.3
    assert score(k["L-110"], 18.6, 25) == 1.1
    assert score(k["L-110"], 33.5, 30) == 0.9
    assert score(k["L-107"], 8.3, 3.75) == 1.5
    assert score(k["L-102"], 0.945, 0.9) == 1.2
    assert score(k["L-102"], 0.999, 0.9) == 1.5
    assert score(k["L-108"], 0.1166, 0.15) == 1.2
    assert score(k["L-109"], None, 0.03) is None


def test_target_changes_by_month():
    assert target_for(CFG["kpis"]["L-110"], "2026-06") == 30
    assert target_for(CFG["kpis"]["L-110"], "2026-07") == 25


def _raw():
    rows = [
        # notification, start, equipment, description, total, waiting, repair
        (1, "03.08.2026 08:00:00", "C3-CST-K01", "D1 - machine stop", 30, 10, 20),
        (2, "03.08.2026 09:00:00", "C3-CST-K01", "E1 - applicator", 10, 5, 5),
        (3, "04.08.2026 06:30:00", "C3-CST-K02", "d1", 60, 20, 40),       # before 07:00 -> 3 Aug
        (4, "03.08.2026 10:00:00", "C3-CST-K03", "F1 - seal", 45, 5, 40),  # seal not in downtime
        (5, "03.08.2026 11:00:00", "C3-WPA-MP01", "D1", 15, 5, 10),        # WPA machine
    ]
    df = pd.DataFrame(rows, columns=["Notification", "Notification Start Time/Date Stamp",
                                     "Equipment description", "Description", "Total Breakdown",
                                     "Waiting Time", "Intervention Time"])
    df["Order"] = range(100, 100 + len(df))
    return df


def test_prepare_events_categories_and_production_day():
    ev, no_order = sap.prepare_events(_raw(), CFG)
    assert list(ev["category"]) == ["Machine BD", "Applicator BD", "Machine BD", "Seal BD", "WPA BD"]
    assert ev.loc[ev["Notification"] == 3, "prod_day"].iloc[0] == pd.Timestamp("2026-08-03")
    assert ev.loc[ev["Notification"] == 3, "shift"].iloc[0] == "3rd"
    assert list(ev["machine"])[:3] == ["K01", "K01", "K02"]
    assert len(no_order) == 0


def test_daily_kpis():
    ev, _ = sap.prepare_events(_raw(), CFG)
    prod = pd.DataFrame({"working_hours": [100.0]}, index=pd.DatetimeIndex(["2026-08-03"]))
    d = kpis.daily_kpis(ev, prod, "2026-08", CFG).loc["2026-08-03"]
    assert d["breakdowns"] == 3                      # 30 + 10 + 60 minutes
    assert abs(d["downtime_h"] - 100 / 60) < 1e-9
    assert abs(d["downtime_pct"] - (100 / 60) / 100) < 1e-9
    assert abs(d["mttr_min"] - 100 / 3) < 1e-9
    assert abs(d["mtbf_h"] - (100 - 100 / 60) / 3) < 1e-9
    assert d["breakdowns_gt_short"] == 2             # the 10-minute call is a short stop
