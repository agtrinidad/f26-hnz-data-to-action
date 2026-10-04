"""Dataset catalog for the chart builder: one registered function per table.

Adding a dataset is one decorated function. Column roles are inferred from dtype and cardinality;
display names come from `viz.columns` in config/default.yaml (falling back to the column name).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from tobacco_inspect.config import Config
from tobacco_inspect.eval import geo

CATEGORY_MAX = 40  # a text/bool column with more distinct values is treated as an identifier


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    label: str
    grain: str  # what one row is; shown in the UI so 345 vs 467 is never ambiguous
    needs: tuple[str, ...]
    fn: Callable[[dict[str, Any], Config], pd.DataFrame]


DATASETS: dict[str, DatasetSpec] = {}


def dataset(name: str, label: str, grain: str, needs: tuple[str, ...]):
    def deco(fn):
        DATASETS[name] = DatasetSpec(name, label, grain, tuple(needs), fn)
        return fn

    return deco


def available(name: str, data: dict[str, Any]) -> bool:
    return all(data.get(k) is not None for k in DATASETS[name].needs)


def load(name: str, data: dict[str, Any], config: Config) -> pd.DataFrame:
    if name not in DATASETS:
        raise KeyError(f"unknown dataset {name!r}; known: {sorted(DATASETS)}")
    if not available(name, data):
        raise KeyError(f"dataset {name!r} needs {DATASETS[name].needs}; run the pipeline first")
    return DATASETS[name].fn(data, config).reset_index(drop=True)


def column_label(config: Config, col: str) -> str:
    labels = config.raw.get("viz", {}).get("columns", {})
    return labels.get(col, col.replace("_", " ").capitalize())


def infer_roles(df: pd.DataFrame) -> dict[str, str]:
    """Map each column to numeric | category | id | geo | date."""
    roles = {}
    for col in df.columns:
        s, low = df[col], str(col).lower()
        if low in {"lon", "lat"}:
            roles[col] = "geo"
        elif "geoid" in low or low.endswith(("_id", "_key")):
            roles[col] = "id"
        elif pd.api.types.is_bool_dtype(s):
            roles[col] = "category"
        elif pd.api.types.is_datetime64_any_dtype(s):
            roles[col] = "date"
        elif pd.api.types.is_numeric_dtype(s):
            roles[col] = "numeric"
        else:
            roles[col] = "category" if s.nunique() <= CATEGORY_MAX else "id"
    return roles


def _stores(data, config) -> pd.DataFrame:
    """Retail locations: the highest-prize license at each address (345 rows)."""
    r = data["risk"]
    r = r[r["retail_license"]]
    seen = r.groupby("location_key")["fda_observed"].max()
    out = r.sort_values("prize", ascending=False).drop_duplicates("location_key").copy()
    out["fda_observed"] = out["location_key"].map(seen)
    return _decorate(out, data)


def _decorate(df: pd.DataFrame, data) -> pd.DataFrame:
    df = df.copy()
    f = data.get("features")
    if f is not None:
        cols = [
            c
            for c in (
                "acs_poverty_rate",
                "acs_youth_share",
                "acs_minority_share",
                "school_nearest_m",
                "school_within_1000m",
                "chain_flag",
            )
            if c in f.columns
        ]
        df = df.merge(f[["license_id", *cols]], on="license_id", how="left")
    df["fda_history"] = df["fda_observed"].map({True: "FDA history", False: "No FDA history"})
    df["prize_rank"] = df["prize"].rank(ascending=False, method="first").astype(int)
    return df


@dataset("stores", "Retail locations", "one row per physical retail location (345)", ("risk",))
def _ds_stores(data, config):
    return _stores(data, config)


@dataset("licenses", "Active licenses", "one row per active license, all types (467)", ("risk",))
def _ds_licenses(data, config):
    return _decorate(data["risk"], data)


@dataset("tracts", "Census tracts", "one row per tract with a retail location", ("risk",))
def _ds_tracts(data, config):
    t = geo.tract_summary(_stores(data, config))
    cov = data.get("coverage_by_tract")
    if cov is not None:
        keep = [
            "tract_geoid",
            "poverty_rate",
            "youth_share",
            "minority_share",
            "inspections",
            "stores_inspected",
        ]
        t = t.merge(cov[[c for c in keep if c in cov.columns]], on="tract_geoid", how="left")
    return t


@dataset("fda_checks", "FDA city checks", "one row per undercover check (911)", ("checks",))
def _ds_checks(data, config):
    c = data["checks"]
    out = pd.DataFrame(
        {
            "year": pd.to_datetime(c["decision_date_parsed"], errors="coerce").dt.year,
            "zip": c["Zip"].astype(str),
            "violation": c["underage_sale_violation"],
            "outcome": c["Outcome"],
            "has_inspection_date": c["inspection_date_parsed"].notna(),
            "tract_geoid": c["tract_geoid"].map(lambda v: "" if pd.isna(v) else str(int(v))),
        }
    )
    return out


@dataset("fda_by_year", "FDA records by year", "one row per year", ("fda_by_year",))
def _ds_by_year(data, config):
    return data["fda_by_year"]


@dataset(
    "regime_frontier",
    "Policy frontier",
    "one row per policy and check volume",
    ("regime_frontier",),
)
def _ds_frontier(data, config):
    return data["regime_frontier"]


@dataset("valuation_marginal", "Marginal cost", "one row per sweep option", ("valuation_marginal",))
def _ds_marginal(data, config):
    return data["valuation_marginal"]


@dataset(
    "backtest", "Backtest", "one row per year, subset, scorer and fraction", ("gate_a_backtest",)
)
def _ds_backtest(data, config):
    return data["gate_a_backtest"]


@dataset(
    "simulation",
    "Policy simulation",
    "one row per response cell and policy",
    ("simulation_policies",),
)
def _ds_simulation(data, config):
    return data["simulation_policies"]
