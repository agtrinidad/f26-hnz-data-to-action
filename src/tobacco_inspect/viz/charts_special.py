"""Chart kinds that are not plain axes charts: maps, KPI tiles and ranked tables."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from tobacco_inspect.eval import geo
from tobacco_inspect.viz import datasets
from tobacco_inspect.viz.charts import (
    KINDS,
    ChartKind,
    Field,
    Opt,
    aggregate,
    apply_filters,
    finish,
    fmt_cat,
    fmt_value,
    label,
    series_colors,
    value_label,
)
from tobacco_inspect.viz.figures_geo import base_map
from tobacco_inspect.viz.spec import SpecError
from tobacco_inspect.viz.theme import new_figure, palette

KPI_AGGS = ("count", "nunique", "sum", "mean", "median", "min", "max")
KPI_FORMATS = ("number", "percent", "dollars")
MAP_MODES = ("points", "choropleth", "density")


# --- map --------------------------------------------------------------------------------------


def _compute_map(df, spec, config):
    d = apply_filters(df, spec.filters)
    if spec.opt("map_mode", "points") == "choropleth":
        return aggregate(d.dropna(subset=["tract_geoid"]), ["tract_geoid"], spec.color, spec.agg)
    cols = list(dict.fromkeys(c for c in ("lon", "lat", spec.color, spec.size) if c))
    return d[cols].dropna(subset=["lon", "lat"])


def _is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _draw_map(plot, spec, config, ctx):
    pal = palette(config)
    mode = spec.opt("map_mode", "points")
    fig = new_figure(config)
    ax = fig.subplots()
    noun = datasets.DATASETS[spec.dataset].label.lower()
    if mode == "choropleth":
        if ctx.get("tracts") is None:
            raise SpecError("Tract boundaries are not downloaded; run `tobacco-inspect refresh`.")
        fill = plot.set_index("tract_geoid")["value"]
        vlabel = value_label(spec, config, spec.color)
        base_map(ax, ctx, pal, fill=fill, cmap="Reds", label=vlabel)
        return finish(fig, spec, config, f"{vlabel} by census tract")
    base_map(ax, ctx, pal)
    if mode == "density":
        reducer = {"sum": np.sum, "mean": np.mean, "median": np.median}.get(spec.agg)
        use_c = bool(spec.color) and reducer is not None and _is_numeric(plot[spec.color])
        hb = ax.hexbin(plot["lon"], plot["lat"], C=plot[spec.color] if use_c else None,
                       reduce_C_function=reducer or np.mean, gridsize=int(spec.opt("gridsize", 25)),
                       cmap="Reds", mincnt=1, linewidths=0.3, edgecolors="white")  # fmt: skip
        fig.colorbar(
            hb,
            ax=ax,
            shrink=0.6,
            label=value_label(spec, config, spec.color) if use_c else f"Number of {noun}",
        )
        title = (
            f"Where {noun} concentrate"
            if not use_c
            else f"{value_label(spec, config, spec.color)} by area"
        )
    else:
        sizes = 38
        if spec.size:
            full = plot[spec.size]
            span = full.max() - full.min()
            sizes = 20 + 220 * ((full - full.min()) / span if span > 0 else full * 0 + 0.3)
        plot = plot.assign(_s=sizes) if spec.size else plot
        s_of = (lambda d: d["_s"]) if spec.size else (lambda d: 38)
        if spec.color and _is_numeric(plot[spec.color]):
            norm = Normalize(plot[spec.color].min(), plot[spec.color].max())
            ax.scatter(plot["lon"], plot["lat"], c=plot[spec.color], cmap="Reds", norm=norm, s=s_of(plot),
                       edgecolor=pal["ink"], linewidth=0.3, alpha=0.9)  # fmt: skip
            fig.colorbar(
                ScalarMappable(norm, "Reds"), ax=ax, shrink=0.6, label=label(config, spec.color)
            )
        elif spec.color:
            groups = sorted(plot[spec.color].dropna().unique())
            for c, g in zip(series_colors(config, len(groups)), groups, strict=True):
                d = plot[plot[spec.color] == g]
                ax.scatter(d["lon"], d["lat"], s=s_of(d), color=c, alpha=0.85, edgecolor="white",
                           linewidth=0.4, label=f"{fmt_cat(g)} ({len(d)})")  # fmt: skip
            ax.legend(
                title=label(config, spec.color),
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                fontsize=8,
            )
        else:
            ax.scatter(plot["lon"], plot["lat"], s=s_of(plot), color=pal["red"], alpha=0.85,
                       edgecolor="white", linewidth=0.4)  # fmt: skip
        if spec.opt("clusters", False) and len(plot) > 1:
            lab = geo.cluster_stores(
                plot, float(spec.opt("eps_m", 400)), int(spec.opt("min_samples", 4))
            )
            hit = plot[lab >= 0]
            ax.scatter(
                hit["lon"],
                hit["lat"],
                s=95,
                facecolors="none",
                edgecolors=pal["ink"],
                linewidths=1.1,
            )
            for k in sorted(set(lab[lab >= 0])):
                m = plot[lab == k]
                ax.annotate(str(len(m)), (m["lon"].mean(), m["lat"].mean()), xytext=(0, 12),
                            textcoords="offset points", ha="center", fontsize=10, fontweight="bold")  # fmt: skip
        title = f"Map of {noun}"
    schools = ctx.get("schools")
    if spec.opt("schools", False) and schools is not None:
        pad = 0.01  # keep only schools near the plotted stores (the file covers more than the city)
        near = (
            schools[
                schools["lon"].between(plot["lon"].min() - pad, plot["lon"].max() + pad)
                & schools["lat"].between(plot["lat"].min() - pad, plot["lat"].max() + pad)
            ]
            if "lon" in plot.columns
            else schools
        )
        schools = near
        ax.scatter(
            schools["lon"],
            schools["lat"],
            marker="^",
            s=9,
            color=pal["blue"],
            alpha=0.45,
            label="School",
        )
    ax.autoscale_view()
    return finish(fig, spec, config, title)


KINDS["map"] = ChartKind(
    "Map",
    {
        "color": Field(False, "any", "Color by / value"),
        "size": Field(False, "num", "Size by (points)"),
    },
    _compute_map,
    _draw_map,
    options=(
        Opt("map_mode", "choice", "points", "Map type", choices=MAP_MODES),
        Opt("clusters", "bool", False, "Outline DBSCAN clusters (points)"),
        Opt("eps_m", "int", 400, "Cluster radius (m)", 150, 1000),
        Opt("min_samples", "int", 4, "Min stores per cluster", 2, 10),
        Opt("schools", "bool", False, "Show schools"),
        Opt("gridsize", "int", 25, "Density grid size", 10, 60),
    ),
    uses_agg=True,
    note="Choropleth and density use the aggregation; points show each row.",
)


# --- KPI tiles --------------------------------------------------------------------------------


def _kpi_value(d: pd.DataFrame, col: str | None, agg: str) -> float:
    if agg == "count" or not col:
        return float(len(d))
    s = d[col].dropna()
    if agg == "nunique":
        return float(s.nunique())
    return float(getattr(s.astype(float), agg)()) if len(s) else float("nan")


def _fmt_kpi(v: float, kind: str) -> str:
    if v != v:
        return "n/a"
    if kind == "percent":
        return f"{v:.0%}"
    if kind == "dollars":
        return f"${v:,.0f}"
    return fmt_value(v)


def _compute_kpi(df, spec, config):
    d = apply_filters(df, spec.filters)
    rows = []
    for k in spec.opt("kpis", [])[:4]:
        v = _kpi_value(d, k.get("column"), k.get("agg", "count"))
        rows.append({"label": k.get("label") or k.get("column") or "Rows", "value": v,
                     "display": _fmt_kpi(v, k.get("fmt", "number"))})  # fmt: skip
    return pd.DataFrame(rows, columns=["label", "value", "display"])


def _draw_kpi(plot, spec, config, ctx):
    pal = palette(config)
    fig = new_figure(config)
    ax = fig.subplots()
    ax.axis("off")
    n = max(len(plot), 1)
    for i, row in enumerate(plot.itertuples()):
        x0 = i / n + 0.01
        ax.plot(
            [x0, x0 + 0.9 / n],
            [0.8, 0.8],
            color=pal["ink"],
            lw=3,
            transform=ax.transAxes,
            clip_on=False,
        )
        ax.text(x0, 0.55, row.display, fontsize=44 if n <= 3 else 36, fontweight="bold", color=pal["coral"],
                transform=ax.transAxes, va="center")  # fmt: skip
        ax.text(x0, 0.28, row.label, fontsize=13, fontweight="bold", color=pal["ink"],
                transform=ax.transAxes, va="top", wrap=True)  # fmt: skip
    return finish(fig, spec, config, "Key figures")


KINDS["kpi"] = ChartKind(
    "KPI tiles",
    {},
    _compute_kpi,
    _draw_kpi,
    note="Up to four big numbers; add them below.",
)


# --- ranked table -----------------------------------------------------------------------------


def _compute_table(df, spec, config):
    d = apply_filters(df, spec.filters)
    if spec.y:
        d = d.dropna(subset=[spec.y]).sort_values(spec.y, ascending=spec.sort == "asc")
    cols = [c for c in spec.opt("columns", []) if c in d.columns] or list(d.columns[:6])
    return d[cols].head(spec.top_n or 10)


def _cell(v) -> str:
    if isinstance(v, bool | np.bool_):
        return "Yes" if v else "No"
    if isinstance(v, float | np.floating):
        return fmt_value(float(v))
    s = str(v)
    return s if len(s) <= 30 else s[:29] + "…"


def _draw_table(plot, spec, config, ctx):
    pal = palette(config)
    fig = new_figure(config)
    ax = fig.subplots()
    ax.axis("off")
    cells = [[_cell(v) for v in row] for row in plot.to_numpy()]
    header = [label(config, c) for c in plot.columns]
    widths = np.array(
        [max([len(h), *(len(r[j]) for r in cells)]) + 2 for j, h in enumerate(header)], float
    )
    tbl = ax.table(
        cellText=cells, colLabels=header, cellLoc="left", colWidths=list(widths / widths.sum()),
        bbox=[0, max(0.0, 1 - 0.085 * (len(cells) + 1)), 1, min(1.0, 0.085 * (len(cells) + 1))],
    )  # fmt: skip
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(max(7, min(11, 150 // (len(plot) + 2))))
    for (r, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(pal["rule"])
        if r == 0:
            cell.set_facecolor(pal["red"])
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#F8F9FA")
    noun = datasets.DATASETS[spec.dataset].label.lower()
    n = len(plot)
    title = (
        f"Top {n} {noun} by {label(config, spec.y).lower()}"
        if spec.y
        else f"{noun.capitalize()} (first {n})"
    )
    return finish(fig, spec, config, title)


KINDS["table"] = ChartKind(
    "Ranked table",
    {"y": Field(False, "num", "Rank by")},
    _compute_table,
    _draw_table,
    options=(Opt("columns", "columns", [], "Columns to show"),),
    uses_sort=True,
    note="Rows are the top N after sorting (descending unless Sort is ascending).",
)
