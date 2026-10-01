"""Coverage-by-tract audit and neighborhood equity gaps.

Stores are scored from behavior and exposure features, not demographics. This audit checks the
outcome of the plan: do inspections concentrate in some tracts more than the store counts
justify, and does coverage correlate with tract poverty? Poverty and youth share come from ACS
estimates with large margins of error, so gaps are indicative, not precise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def coverage_by_tract(universe: pd.DataFrame, selected_counts: pd.Series) -> pd.DataFrame:
    """Per tract: retailers, inspections (summed over cycles), coverage rate and ACS context.

    `universe` needs tract_geoid, acs_poverty_rate, acs_youth_share; `selected_counts` is indexed
    like `universe` (inspections per store over the planning horizon).
    """
    df = universe.assign(inspections=selected_counts.reindex(universe.index).fillna(0))
    out = (
        df.groupby("tract_geoid")
        .agg(
            retailers=("license_id", "size"),
            inspections=("inspections", "sum"),
            stores_inspected=("inspections", lambda s: int((s > 0).sum())),
            poverty_rate=("acs_poverty_rate", "first"),
            youth_share=("acs_youth_share", "first"),
        )
        .reset_index()
    )
    out["inspections_per_retailer"] = out["inspections"] / out["retailers"]
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
    return summary
