"""Leakage-safe history features for the risk model.

Every feature for a check at time t uses only records at the same location whose *decision
date* is at least `lag_days` before t. Decision date is the clock because inspection dates are
missing for about 90% of records; the lag guard approximates the publication delay (a decision
cannot inform scheduling before it is known). See docs/process/02_Data_Acquisition_Memo.md.

Training rows are PA undercover checks (`data/processed/oce_pa_checks.csv.gz`). Scoring rows are
Pittsburgh licenses at an as-of date, built from the same function so train and score features
cannot drift apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tobacco_inspect.data import synar
from tobacco_inspect.model.prize import SEVERITY_POINTS

DAY = np.timedelta64(1, "D")
DAYS_CAP = 1825  # 5 years: "no history" and "very old history" collapse to the cap
NUMERIC = [
    "log_prior_checks",
    "log_prior_viol",
    "prior_viol_share",
    "viol_12m",
    "viol_24m",
    "viol_36m",
    "log_days_since_check",
    "log_days_since_viol",
    "has_prior_check",
    "has_prior_viol",
    "log_chain_size",
    "prior_fy_rate",
]
CATEGORICAL = ["outlet_type"]
FEATURES = NUMERIC + CATEGORICAL


@dataclass(frozen=True)
class LocationHistory:
    """Sorted decision dates and violation flags for one location (or merged locations)."""

    dates: np.ndarray  # datetime64[ns], ascending
    viol: np.ndarray  # int8, aligned with dates


def name_key(name: str) -> str:
    """Retailer name with store numbers and punctuation removed (chain grouping key)."""
    text = re.sub(r"[#\d]+", " ", str(name).upper())
    text = re.sub(r"[^A-Z& ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_index(checks: pd.DataFrame) -> dict[str, LocationHistory]:
    """location_key -> LocationHistory from a checks table (needs decision_date_parsed)."""
    index = {}
    ordered = checks.sort_values("decision_date_parsed")
    for key, grp in ordered.groupby("location_key", sort=False):
        index[key] = LocationHistory(
            grp["decision_date_parsed"].to_numpy("datetime64[ns]"),
            grp["underage_sale_violation"].to_numpy("int8"),
        )
    return index


def merge_histories(histories: list[LocationHistory]) -> LocationHistory | None:
    """Combine several locations (a license can match more than one FDA location)."""
    histories = [h for h in histories if h is not None and len(h.dates)]
    if not histories:
        return None
    if len(histories) == 1:
        return histories[0]
    dates = np.concatenate([h.dates for h in histories])
    viol = np.concatenate([h.viol for h in histories])
    order = np.argsort(dates, kind="stable")
    return LocationHistory(dates[order], viol[order])


def history_features(h: LocationHistory | None, t, lag_days: int) -> dict[str, float]:
    """History features at time `t` using decision dates <= t - lag_days."""
    t = np.datetime64(t, "ns")
    cutoff = t - np.timedelta64(int(lag_days), "D")
    if h is None:
        n = 0
    else:
        n = int(np.searchsorted(h.dates, cutoff, side="right"))
    if n == 0:
        return {
            "n_prior_checks": 0,
            "n_prior_viol": 0,
            "viol_12m": 0,
            "viol_24m": 0,
            "viol_36m": 0,
            "days_since_check": DAYS_CAP,
            "days_since_viol": DAYS_CAP,
        }
    dates, viol = h.dates[:n], h.viol[:n]
    vdates = dates[viol == 1]
    last_check = (cutoff - dates[-1]) / DAY
    last_viol = (cutoff - vdates[-1]) / DAY if len(vdates) else DAYS_CAP

    def within(days: int) -> int:
        return int((vdates > cutoff - np.timedelta64(days, "D")).sum())

    return {
        "n_prior_checks": n,
        "n_prior_viol": int(len(vdates)),
        "viol_12m": within(365),
        "viol_24m": within(730),
        "viol_36m": within(1095),
        "days_since_check": float(min(last_check, DAYS_CAP)),
        "days_since_viol": float(min(last_viol, DAYS_CAP)),
    }


def prior_fy_rates(checks: pd.DataFrame, min_checks: int = 500) -> pd.Series:
    """Statewide violation rate per fiscal year; thin years (COVID) are carried forward."""
    g = checks.groupby("fy")["underage_sale_violation"].agg(["mean", "size"])
    rate = g["mean"].where(g["size"] >= min_checks)
    return rate.ffill().bfill()


def _finish(frame: pd.DataFrame) -> pd.DataFrame:
    """Derived/transformed columns shared by training and scoring."""
    f = frame.copy()
    f["log_prior_checks"] = np.log1p(f["n_prior_checks"])
    f["log_prior_viol"] = np.log1p(f["n_prior_viol"])
    f["prior_viol_share"] = np.where(
        f["n_prior_checks"] > 0, f["n_prior_viol"] / f["n_prior_checks"].clip(lower=1), 0.0
    )
    f["log_days_since_check"] = np.log1p(f["days_since_check"])
    f["log_days_since_viol"] = np.log1p(f["days_since_viol"])
    f["has_prior_check"] = (f["n_prior_checks"] > 0).astype(int)
    f["has_prior_viol"] = (f["n_prior_viol"] > 0).astype(int)
    return f


def build_training_frame(checks: pd.DataFrame, lag_days: int = 30) -> pd.DataFrame:
    """One row per undercover check with snapshot features and the violation label.

    Chain size counts distinct PA locations sharing a normalized retailer name (no outcomes used).
    `prior_fy_rate` is last fiscal year's statewide violation rate, a covariate for period effects
    that is known at decision time.
    """
    checks = checks[checks["up_involved"]].copy()
    checks["decision_date_parsed"] = pd.to_datetime(checks["decision_date_parsed"])
    checks["name_key"] = checks["Retailer Name"].map(name_key)
    chain_size = checks.groupby("name_key")["location_key"].nunique()
    index = build_index(checks)
    rates = prior_fy_rates(checks)
    rows = [
        history_features(index.get(loc), t, lag_days)
        for loc, t in zip(checks["location_key"], checks["decision_date_parsed"], strict=True)
    ]
    out = pd.concat([checks.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    out["log_chain_size"] = np.log1p(out["name_key"].map(chain_size).fillna(1))
    prev_map = {
        fy: (rates[rates.index < fy].iloc[-1] if (rates.index < fy).any() else rates.iloc[0])
        for fy in out["fy"].unique()
    }
    prev = out["fy"].map(prev_map)
    out["prior_fy_rate"] = prev
    out["outlet_type"] = out["Retailer Name"].map(synar.classify_outlet)
    out["y"] = out["underage_sale_violation"].astype(int)
    return _finish(out)


def build_scoring_frame(
    universe: pd.DataFrame, checks: pd.DataFrame, as_of, lag_days: int = 30
) -> pd.DataFrame:
    """Features for each license in `universe` at `as_of` (full history up to the lag guard).

    `universe` needs `license_id`, `trade_name` and `fda_location_keys` (' || '-joined keys).
    """
    checks = checks[checks["up_involved"]].copy()
    checks["decision_date_parsed"] = pd.to_datetime(checks["decision_date_parsed"])
    checks["name_key"] = checks["Retailer Name"].map(name_key)
    chain_size = checks.groupby("name_key")["location_key"].nunique()
    index = build_index(checks)
    rates = prior_fy_rates(checks)
    current_rate = float(rates.iloc[-1])
    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=int(lag_days))
    known = checks[checks["decision_date_parsed"] <= cutoff].copy()
    known["points"] = known["Outcome"].map(SEVERITY_POINTS).fillna(0.0)
    severity = known.groupby("location_key")["points"].sum()
    rows = []
    for _, lic in universe.iterrows():
        keys = [
            k for k in str(lic.get("fda_location_keys") or "").split(" || ") if k and k != "nan"
        ]
        hist = merge_histories([index.get(k) for k in keys])
        row = history_features(hist, as_of, lag_days)
        row["license_id"] = lic["license_id"]
        row["name_key"] = name_key(lic["trade_name"])
        row["severity_points"] = float(sum(severity.get(k, 0.0) for k in keys))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["log_chain_size"] = np.log1p(out["name_key"].map(chain_size).fillna(1))
    out["prior_fy_rate"] = current_rate
    out["outlet_type"] = universe["trade_name"].map(synar.classify_outlet).to_numpy()
    return _finish(out)
