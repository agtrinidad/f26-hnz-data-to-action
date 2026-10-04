"""Coverage-by-tract audit and neighborhood equity gaps.

Stores are scored from behavior and exposure features, not demographics. This audit checks the
outcome of the plan: do inspections concentrate in some tracts more than the store counts
justify, does coverage correlate with tract poverty, and do majority-minority tracts (more than
half the residents not non-Hispanic White) get more checks per store than other tracts? Poverty,
youth and minority shares come from ACS estimates with large margins of error, so gaps are
indicative, not precise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MAJORITY_MINORITY = 0.5


def coverage_by_tract(universe: pd.DataFrame, selected_counts: pd.Series) -> pd.DataFrame:
    """Per tract: retailers, inspections (summed over cycles), coverage rate and ACS context.

    `universe` needs tract_geoid, acs_poverty_rate, acs_youth_share (and optionally
    acs_minority_share); `selected_counts` is indexed like `universe` (inspections per store
    over the planning horizon).
    """
    df = universe.assign(inspections=selected_counts.reindex(universe.index).fillna(0))
    spec = dict(
        retailers=("license_id", "size"),
        inspections=("inspections", "sum"),
        stores_inspected=("inspections", lambda s: int((s > 0).sum())),
        poverty_rate=("acs_poverty_rate", "first"),
        youth_share=("acs_youth_share", "first"),
    )
    if "acs_minority_share" in df:
        spec["minority_share"] = ("acs_minority_share", "first")
    out = df.groupby("tract_geoid").agg(**spec).reset_index()
    out["inspections_per_retailer"] = out["inspections"] / out["retailers"]
    return out


def _minority_summary(cov: pd.DataFrame, total_ret: float, total_ins: float) -> dict[str, float]:
    """Coverage in majority-minority (> 50% non-White-or-Hispanic) tracts vs. all other tracts."""
    known = cov["minority_share"].notna()
    mm = known & (cov["minority_share"] > MAJORITY_MINORITY)
    other = known & ~mm
    out = {
        "tracts_majority_minority": int(mm.sum()),
        "share_retailers_majority_minority": float(cov.loc[mm, "retailers"].sum() / total_ret),
        "share_inspections_majority_minority": float(cov.loc[mm, "inspections"].sum() / total_ins)
        if total_ins
        else float("nan"),
    }
    ret_mm, ret_other = cov.loc[mm, "retailers"].sum(), cov.loc[other, "retailers"].sum()
    if total_ins and ret_mm and ret_other:
        per_mm = cov.loc[mm, "inspections"].sum() / ret_mm
        per_other = cov.loc[other, "inspections"].sum() / ret_other
        out["inspections_per_retailer_majority_minority"] = float(per_mm)
        out["inspections_per_retailer_other"] = float(per_other)
        # > 1 means majority-minority tracts get more checks per store than other tracts
        out["majority_minority_coverage_ratio"] = float(per_mm / per_other) if per_other else np.nan
    if total_ins and known.sum() > 3:
        out["corr_coverage_minority"] = float(
            np.corrcoef(
                cov.loc[known, "inspections_per_retailer"], cov.loc[known, "minority_share"]
            )[0, 1]
        )
    return out


def equity_summary(cov: pd.DataFrame) -> dict[str, float]:
    """Gaps between where retailers are and where inspections go."""
    total_ret, total_ins = cov["retailers"].sum(), cov["inspections"].sum()
    q = cov["poverty_rate"].quantile(0.75)
    high = cov["poverty_rate"] >= q
    summary = {
        "tracts": int(len(cov)),
        "tracts_with_inspection": int((cov["inspections"] > 0).sum()),
        "share_retailers_high_poverty": float(cov.loc[high, "retailers"].sum() / total_ret),
        "share_inspections_high_poverty": float(cov.loc[high, "inspections"].sum() / total_ins)
        if total_ins
        else float("nan"),
    }
    ok = cov["poverty_rate"].notna()
    if total_ins and ok.sum() > 3:
        summary["corr_coverage_poverty"] = float(
            np.corrcoef(cov.loc[ok, "inspections_per_retailer"], cov.loc[ok, "poverty_rate"])[0, 1]
        )
    if "minority_share" in cov:
        summary.update(_minority_summary(cov, total_ret, total_ins))
    return summary
