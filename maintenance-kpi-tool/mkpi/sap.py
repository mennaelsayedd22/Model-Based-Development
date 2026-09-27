"""Reading the monthly SAP breakdown export and turning it into clean events."""
import re

import numpy as np
import pandas as pd

REQUIRED = [
    "Notification", "Order", "Equipment description", "Description",
    "Notification Start Time/Date Stamp", "Total Breakdown", "Waiting Time",
    "Intervention Time",
]
OPTIONAL = [
    "Equipment", "Equipment.1", "DamageCode Short text", "Cause short text",
    "Object Parts short text", "Confirmation text", "WO Confirmation Creator Stamp",
    "Order Type", "Notification Status",
]


def _norm(col):
    return re.sub(r"\s+", " ", str(col)).strip()


def read_sap_export(path):
    df = pd.read_excel(path)
    df.columns = [_norm(c) for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"SAP export {path} is missing columns: {missing}")
    return df


def shift_of(ts):
    t = ts.dt.hour * 60 + ts.dt.minute + ts.dt.second / 60
    return np.select([(t >= 7 * 60) & (t <= 15 * 60), (t > 15 * 60) & (t <= 23 * 60)],
                     ["1st", "2nd"], "3rd")


def prepare_events(raw, cfg):
    """Return (events, notifications_without_order).

    One row per breakdown notification that has a work order, with the production day
    (07:00 -> 07:00), shift, machine, fault code and KPI category worked out.
    """
    raw = raw.assign(**{c: np.nan for c in OPTIONAL if c not in raw.columns})
    no_order = raw[raw["Order"].isna()]
    df = raw[raw["Order"].notna()].copy()

    df["start"] = pd.to_datetime(df["Notification Start Time/Date Stamp"],
                                 format="%d.%m.%Y %H:%M:%S", errors="coerce")
    df = df[df["start"].notna()]
    df["prod_day"] = (df["start"] - pd.Timedelta(hours=cfg["day_start_hour"])).dt.normalize()
    df["shift"] = shift_of(df["start"])
    df["hour"] = df["start"].dt.hour

    equip = df["Equipment description"].astype(str)
    df["group"] = equip.str.split("-").str[1].fillna("")
    df["machine"] = equip.str.replace(r"^[^-]+-[^-]+-", "", regex=True)
    df["tool_id"] = df["Equipment.1"]

    desc = df["Description"].astype(str).str.strip().str.upper()
    df["fault_code"] = desc.str.extract(r"^([A-Z]\d*)")[0]
    letter = df["fault_code"].str[0]
    cat = letter.map(cfg["fault_code_categories"])
    for group, mapping in cfg.get("equipment_group_overrides", {}).items():
        for code, override in mapping.items():
            cat = cat.mask(df["group"].eq(group) & letter.eq(code), override)
    df["category"] = cat.fillna("Unclassified")

    df["breakdown_min"] = pd.to_numeric(df["Total Breakdown"], errors="coerce").fillna(0)
    df["waiting_min"] = pd.to_numeric(df["Waiting Time"], errors="coerce").fillna(0)
    df["repair_min"] = pd.to_numeric(df["Intervention Time"], errors="coerce").fillna(0)
    df["technician"] = df["WO Confirmation Creator Stamp"].fillna("?").astype(str).str.upper()
    df["damage"] = df["DamageCode Short text"].fillna("(not coded)")
    df["cause"] = df["Cause short text"].fillna("(not coded)")
    df["object_part"] = df["Object Parts short text"].fillna("(not coded)")
    df["in_downtime"] = df["category"].isin(cfg["downtime_categories"])
    return df, no_order
