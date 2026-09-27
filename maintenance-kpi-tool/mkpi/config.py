"""Loading config.json and looking up targets / score bands."""
import json
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def load_config(path=None):
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        return json.load(f)


def target_for(kpi_cfg, month):
    """Target valid for `month` ("YYYY-MM"): the latest entry whose `from` <= month."""
    target = None
    for entry in sorted(kpi_cfg["targets"], key=lambda e: e["from"]):
        if entry["from"] <= month:
            target = entry["target"]
    return target


def score_bands(kpi_cfg, target):
    """The 16 score bands (0.0 .. 1.5) used by the old KPI workbook.

    Below 1.0 each 0.1 step moves the band by `step_below`, above 1.0 by `step_above`.
    """
    bands = []
    for i in range(16):
        score = round(i / 10, 1)
        if score <= 1:
            value = target - kpi_cfg["step_below"] * 10 * (1 - score)
        else:
            value = target + kpi_cfg["step_above"] * 10 * (score - 1)
        bands.append((score, value))
    return bands


def score(kpi_cfg, value, target):
    """Score a KPI value the same way the YEAR sheet does. Returns None without data."""
    if value is None or target is None or value != value or value == 0:
        return None
    bands = score_bands(kpi_cfg, target)
    method = kpi_cfg["scoring"]
    if method == "nearest":
        return min(bands, key=lambda b: abs(b[1] - value))[0]
    if method == "at_or_below":
        # smallest band value that is >= actual (lower is better)
        ok = [b for b in bands if b[1] >= value]
        return min(ok, key=lambda b: b[1])[0] if ok else 0.0
    if method == "at_or_above":
        # largest band value that is <= actual (higher is better)
        ok = [b for b in bands if b[1] <= value]
        return max(ok, key=lambda b: b[1])[0] if ok else 0.0
    raise ValueError(f"Unknown scoring method: {method}")
