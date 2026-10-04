"""Load the committed CSVs the figures draw on. Missing files become None, never an error."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from tobacco_inspect.config import Config

OUTPUT_CSVS = [
    "coverage_by_tract",
    "gate_a_backtest",
    "regime_frontier",
    "regime_equity",
    "valuation_marginal",
    "valuation_break_even",
    "simulation_policies",
    "census_cost_summary",
]


def _csv(path: Path, **kw: Any) -> pd.DataFrame | None:
    return pd.read_csv(path, **kw) if path.exists() else None


def load_tracts(config: Config):
    """Pittsburgh-area tract polygons (TIGER cartographic), or None if not downloaded."""
    d = config.raw["data"]
    zpath = (
        config.path("raw") / "boundaries" / f"cb_{d['tiger_year']}_{d['state_fips']}_tract_500k.zip"
    )
    if not zpath.exists():
        return None
    from tobacco_inspect.data.ingest import read_zipped_shapefile

    gdf = read_zipped_shapefile(zpath, bbox=(-80.15, 40.35, -79.80, 40.50))
    gdf = gdf[gdf["COUNTYFP"] == d["county_fips"]]
    return gdf.rename(columns={"GEOID": "tract_geoid"})[["tract_geoid", "geometry"]].copy()


def load_viz_data(config: Config, with_boundaries: bool = True) -> dict[str, Any]:
    proc, out, interim = config.path("processed"), config.path("outputs"), config.path("interim")
    data: dict[str, Any] = {
        "risk": _csv(proc / "risk_scores.csv", dtype={"tract_geoid": str}),
        "features": _csv(proc / "location_features.csv", dtype={"tract_geoid": str}),
        "universe": _csv(proc / "retailer_universe.csv", dtype={"tract_geoid": str}),
        "checks": _csv(proc / "fda_city_checks.csv.gz"),
        "fda_by_year": _csv(interim / "pittsburgh_fda_records_by_year.csv"),
        "schools": _csv(interim / "schools_pgh.csv"),
        "tracts": load_tracts(config) if with_boundaries else None,
    }
    for name in OUTPUT_CSVS:
        data[name] = _csv(out / f"{name}.csv", dtype={"tract_geoid": str})
    summ = out / "risk_model_summary.json"
    data["risk_summary"] = json.loads(summ.read_text(encoding="utf-8")) if summ.exists() else None
    return data
