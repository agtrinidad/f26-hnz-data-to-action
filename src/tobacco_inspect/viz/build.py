"""Validate a ChartSpec and turn it into a figure or its plotted table."""

from __future__ import annotations

from typing import Any

import pandas as pd
from matplotlib.figure import Figure

from tobacco_inspect.config import Config
from tobacco_inspect.viz import (
    charts_special,  # noqa: F401  (registers map, kpi, table)
    datasets,
)
from tobacco_inspect.viz.charts import KINDS, apply_filters
from tobacco_inspect.viz.spec import AGGS, FIELDS, MAX_FACETS, ChartSpec, SpecError
from tobacco_inspect.viz.theme import apply_theme, current_overrides, text_overrides

LOW_CARD = 40


def _is_num(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def column_ok(s: pd.Series, ftype: str) -> bool:
    """Can column `s` fill a field of type cat | num | any?"""
    if ftype == "num":
        return _is_num(s)
    if ftype == "cat":
        return not _is_num(s) or s.nunique() <= LOW_CARD
    return True


def choices(df: pd.DataFrame, ftype: str) -> list[str]:
    return [c for c in df.columns if column_ok(df[c], ftype)]


def validate(spec: ChartSpec, df: pd.DataFrame) -> list[str]:
    """Readable problems that would stop `spec` drawing on `df` (empty list = fine)."""
    kind = KINDS.get(spec.kind)
    if kind is None:
        return [f"Unknown chart kind {spec.kind!r}."]
    bad = []
    for name in FIELDS:
        col, fld = getattr(spec, name), kind.fields.get(name)
        if fld is None:
            if col:
                bad.append(f"'{name}' is not used by {kind.label} charts.")
        elif not col:
            if fld.required:
                bad.append(f"{kind.label} needs '{fld.label}'.")
        elif col not in df.columns:
            bad.append(f"Column {col!r} is not in this dataset.")
        elif not column_ok(df[col], fld.type):
            want = "numeric" if fld.type == "num" else "categorical"
            bad.append(f"'{fld.label}' ({col}) must be {want}.")
    if spec.agg not in AGGS:
        bad.append(f"Aggregation must be one of {AGGS}.")

    if spec.top_n is not None and spec.top_n < 1:
        bad.append("Top N must be at least 1.")
    for f in spec.filters:
        if f.get("col") not in df.columns:
            bad.append(f"Filter column {f.get('col')!r} is not in this dataset.")
    if spec.kind == "map":
        mode = spec.opt("map_mode", "points")
        need = ["tract_geoid"] if mode == "choropleth" else ["lon", "lat"]
        bad += [
            f"Maps need a '{c}' column; pick a location-level dataset."
            for c in need
            if c not in df.columns
        ]
    if kind.facetable and spec.facet and not bad:
        n = apply_filters(df, spec.filters)[spec.facet].nunique()
        if n > MAX_FACETS:
            bad.append(
                f"Facet by {spec.facet!r} has {n} values (max {MAX_FACETS}); filter it first."
            )
    return bad


def prepare(spec: ChartSpec, data: dict[str, Any], config: Config) -> pd.DataFrame:
    """The frame that is actually plotted (also what the CSV download contains)."""
    df = datasets.load(spec.dataset, data, config)
    problems = validate(spec, df)
    if problems:
        raise SpecError(problems)
    plot = KINDS[spec.kind].compute(df, spec, config)
    if plot.empty:
        raise SpecError("No rows left after filtering.")
    return plot


def build(spec: ChartSpec, data: dict[str, Any], config: Config) -> Figure:
    """Render `spec`. Text edits made by the caller (registry.render) win over `spec.text`."""
    plot = prepare(spec, data, config)
    apply_theme(config)
    with text_overrides({**spec.text, **current_overrides()}):
        return KINDS[spec.kind].draw(plot, spec, config, data)
