"""Fiscal-year time-split replay (Gate A) and the random-sample (Synar) benchmark.

Replay evaluates a ranking only on stores that were actually inspected (labels exist only
there), so it measures *lift among inspected stores*: how many more violations the top of the
ranking contains than a random draw from the same pool. It is selection-biased evidence, labeled
"observed-sample" in the notebook and results memo. It cannot say what would have happened at
stores that were not inspected.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from tobacco_inspect.data import synar
from tobacco_inspect.model import risk

SCORERS = ("model", "prior_violators_first", "status_quo_followup", "days_since_check", "random")


def baseline_scores(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Rule-based comparators computed from the same snapshot features (no labels)."""
    return {
        # Anyone with a prior violation first, more violations and more recent first.
        "prior_violators_first": (
            frame["viol_36m"].to_numpy() * 1000
            + frame["n_prior_viol"].to_numpy() * 10
            - frame["days_since_viol"].to_numpy() / 1000
        ),
        # FDA's real practice (OIG): re-inspect a retailer with a violation in the last 12 months.
        "status_quo_followup": (
            (frame["viol_12m"].to_numpy() > 0) * 1000 + frame["viol_24m"].to_numpy() * 10
        ),
        # Longest time since the last check first (the proposal's "time since past inspection").
        "days_since_check": frame["days_since_check"].to_numpy().astype(float),
        "random": rng.random(len(frame)),
    }


def rolling_backtest(
    frame: pd.DataFrame,
    test_years=(2022, 2023, 2024, 2025),
    city_keys: set | None = None,
    fracs=(0.1, 0.2),
    seed: int = 867,
    n_boot: int = 300,
) -> pd.DataFrame:
    """Train on fiscal years before t, test on year t. One row per (year, subset, scorer, frac)."""
    rng = np.random.default_rng(seed)
    rows = []
    for t in test_years:
        train, test = frame[frame["fy"] < t], frame[frame["fy"] == t]
        if test.empty or train["y"].sum() == 0:
            continue
        model = risk.fit_risk_model(train)
        scores = {"model": model.predict(test), **baseline_scores(test, rng)}
        subsets = {"PA": np.ones(len(test), bool)}
        if city_keys is not None:
            subsets["Pittsburgh city"] = test["location_key"].isin(city_keys).to_numpy()
        for subset, mask in subsets.items():
            y = test["y"].to_numpy()[mask]
            for name in SCORERS:
                s = scores[name][mask]
                auc = roc_auc_score(y, s) if 0 < y.sum() < len(y) else np.nan
                for frac in fracs:
                    lift, lo, hi = risk.lift_at_k(y, s, frac, rng, n_boot)
                    rows.append(
                        {
                            "fy": t,
                            "subset": subset,
                            "scorer": name,
                            "frac": frac,
                            "n": int(mask.sum()),
                            "violations": int(y.sum()),
                            "auc": auc,
                            "lift": lift,
                            "lift_lo": lo,
                            "lift_hi": hi,
                            "c": model.c,
                        }
                    )
    return pd.DataFrame(rows)


def pooled_lift(results: pd.DataFrame, subset: str, frac: float) -> pd.DataFrame:
    """Average lift across test years per scorer (simple mean; CI bounds averaged, indicative)."""
    r = results[(results["subset"] == subset) & (results["frac"] == frac)]
    return (
        r.groupby("scorer")[["auc", "lift", "lift_lo", "lift_hi"]]
        .mean()
        .sort_values("lift", ascending=False)
    )


def synar_enrichment(fy_table: pd.DataFrame) -> pd.DataFrame:
    """OCE statewide undercover violation rate vs Synar (random sample) by year.

    Synar's survey runs July-August of year Y, inside federal fiscal year Y. Ratio uses the
    midpoint of the chart-read bounds (approximate). Cigarettes only vs all products in OCE.
    """
    h = synar.history().rename(columns={"year": "fy"})
    t = fy_table[["fy", "up_checks", "violations", "violation_rate"]].merge(
        h[["fy", "lower", "upper", "midpoint"]], on="fy"
    )
    t["synar_lower"], t["synar_upper"], t["synar_mid"] = (
        t["lower"] / 100,
        t["upper"] / 100,
        t["midpoint"] / 100,
    )
    t["ratio_to_synar"] = t["violation_rate"] / t["synar_mid"]
    t["above_synar_band"] = t["violation_rate"] > t["synar_upper"]
    t["below_synar_band"] = t["violation_rate"] < t["synar_lower"]
    return t.drop(columns=["lower", "upper", "midpoint"])
