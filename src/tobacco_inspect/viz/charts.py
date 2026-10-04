"""Chart kinds for the builder. Each kind is `compute(df, spec, config) -> plot frame` plus
`draw(plot, spec, config, ctx) -> Figure`; nothing here touches Streamlit.

Facetable kinds draw through `panels()`, so small multiples need no per-kind code.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from tobacco_inspect.config import Config
from tobacco_inspect.viz import datasets
from tobacco_inspect.viz.spec import AGGS, MAX_FACETS, ChartSpec
from tobacco_inspect.viz.theme import new_figure, palette, titled


@dataclass(frozen=True)
class Field:
    required: bool
    type: str  # cat | num | any
    label: str


@dataclass(frozen=True)
class Opt:
    name: str
    type: str  # bool | int | float | choice | columns
    default: Any
    label: str
    lo: float | None = None
    hi: float | None = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChartKind:
    label: str
    fields: dict[str, Field]
    compute: Callable[[pd.DataFrame, ChartSpec, Config], pd.DataFrame]
    draw: Callable[[pd.DataFrame, ChartSpec, Config, dict], Figure]
    options: tuple[Opt, ...] = ()
    facetable: bool = False
    uses_agg: bool = False
    uses_sort: bool = False
    note: str = ""


KINDS: dict[str, ChartKind] = {}


# --- shared helpers ---------------------------------------------------------------------------


def label(config: Config, col: str | None) -> str:
    return datasets.column_label(config, col) if col else ""


def fmt_value(v: float, share: bool = False) -> str:
    if share:
        return f"{v:.0%}"
    if v != v:
        return ""
    a = abs(v)
    if a >= 1000 or (a >= 100 and float(v).is_integer()):
        return f"{v:,.0f}"
    if a >= 10:
        return f"{v:,.1f}"
    return f"{v:.2f}"


def fmt_cat(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def series_colors(config: Config, n: int) -> list[str]:
    pal = palette(config)
    base = [pal["red"], pal["blue"], pal["muted"], pal["coral"], "#8FB8DE", "#B08D57", "#2E2E2E"]
    return [base[i % len(base)] for i in range(n)]


def apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    for f in filters:
        col = f["col"]
        if "values" in f:
            df = df[df[col].isin(f["values"])]
        else:
            df = df[df[col].between(f.get("min", -np.inf), f.get("max", np.inf))]
    return df


def aggregate(df: pd.DataFrame, keys: list[str], y: str | None, agg: str) -> pd.DataFrame:
    keys = list(dict.fromkeys(k for k in keys if k))
    g = df.groupby(keys, observed=True)
    if agg == "share":
        out = g.size() / max(len(df), 1)
    elif agg == "count" or y is None:
        out = g.size()
    else:
        out = getattr(g[y], agg)()
    return out.rename("value").reset_index()


def value_label(spec: ChartSpec, config: Config, y: str | None = None) -> str:
    y = y or spec.y
    if spec.agg == "share":
        return "Share of rows"
    if spec.agg == "count" or not y:
        return "Number of rows"
    return f"{spec.agg.capitalize()} {label(config, y).lower()}"


def cat_order(plot: pd.DataFrame, col: str, sort: str) -> list:
    tot = plot.groupby(col)["value"].sum()
    if sort in ("asc", "desc"):
        return list(tot.sort_values(ascending=sort == "asc").index)
    return sorted(tot.index)


def default_text(
    spec: ChartSpec, config: Config, title: str, subtitle: str | None = None
) -> tuple[str, str, str]:
    ds = datasets.DATASETS[spec.dataset]
    if subtitle is None:
        subtitle = f"{ds.label}: {ds.grain}"
    parts = []
    for f in spec.filters:
        if "values" in f:
            parts.append(f"{label(config, f['col'])}: {', '.join(fmt_cat(v) for v in f['values'])}")
        else:
            parts.append(f"{label(config, f['col'])} {f.get('min', '')}–{f.get('max', '')}")
    if parts:
        subtitle += "  ·  filter: " + "; ".join(parts)
    return title, subtitle, f"Source: tobacco_inspect; {ds.label}."


def finish(fig: Figure, spec: ChartSpec, config: Config, title: str, subtitle=None) -> Figure:
    return titled(fig, config, *default_text(spec, config, title, subtitle))


def panels(plot, spec, config, sharex=False, sharey=False):
    """Figure plus [(ax, sub-frame, panel title)]; one panel unless a facet column is set."""
    fig = new_figure(config)
    pal = palette(config)
    if spec.facet and spec.facet in plot.columns:
        vals = sorted(plot[spec.facet].dropna().unique())[:MAX_FACETS]
        ncols = min(3, len(vals))
        nrows = math.ceil(len(vals) / ncols)
        axes = fig.subplots(nrows, ncols, sharex=sharex, sharey=sharey, squeeze=False).ravel()
        for ax in axes[len(vals) :]:
            ax.set_visible(False)
        pairs = []
        for ax, v in zip(axes, vals, strict=False):
            ax.set_title(fmt_cat(v), fontsize=10, loc="left", color=pal["muted"])
            pairs.append((ax, plot[plot[spec.facet] == v]))
        return fig, pairs
    return fig, [(fig.subplots(), plot)]


def _groups(plot: pd.DataFrame, col: str | None) -> list:
    return sorted(plot[col].dropna().unique()) if col else [None]


def _log(ax, axis: str, on: bool) -> None:
    if on:
        getattr(ax, f"set_{axis}scale")("log")


# --- bar --------------------------------------------------------------------------------------


def _compute_bar(df, spec, config):
    d = apply_filters(df, spec.filters)
    out = aggregate(d, [spec.x, spec.color, spec.facet], spec.y, spec.agg)
    if spec.top_n:
        keep = out.groupby(spec.x)["value"].sum().nlargest(spec.top_n).index
        out = out[out[spec.x].isin(keep)]
    return out


def _draw_bar(plot, spec, config, ctx):
    horizontal, stacked = spec.opt("horizontal", True), spec.opt("stacked", False)
    share = spec.agg == "share"
    order = cat_order(plot, spec.x, spec.sort)
    series = _groups(plot, spec.color)
    colors = series_colors(config, len(series))
    fig, pairs = panels(plot, spec, config, sharex=horizontal, sharey=not horizontal)
    pos = np.arange(len(order))
    for k, (ax, d) in enumerate(pairs):
        if spec.color:
            piv = d.pivot_table(index=spec.x, columns=spec.color, values="value", aggfunc="sum")
        else:
            piv = d.groupby(spec.x)["value"].sum().to_frame("_")
        piv = piv.reindex(order).reindex(columns=series if spec.color else ["_"]).fillna(0)
        n = len(series)
        width = 0.7 if stacked or n == 1 else 0.8 / n
        bottom = np.zeros(len(order))
        for j, s in enumerate(series):
            vals = piv.iloc[:, j].to_numpy()
            offs = pos if stacked or n == 1 else pos - 0.4 + width * (j + 0.5)
            kw = {"color": colors[j], "label": fmt_cat(s) if spec.color else None}
            if horizontal:
                bars = ax.barh(offs, vals, width, left=bottom if stacked else None, **kw)
            else:
                bars = ax.bar(offs, vals, width, bottom=bottom if stacked else None, **kw)
            if spec.opt("labels", True) and (not stacked or n == 1):
                ax.bar_label(
                    bars, labels=[fmt_value(v, share) for v in vals], padding=3, fontsize=8
                )
            if stacked:
                bottom = bottom + vals
        names = [fmt_cat(o) for o in order]
        if horizontal:
            ax.set_yticks(pos, names)
            ax.invert_yaxis()
            ax.grid(axis="y", visible=False)
            ax.set_xlabel(value_label(spec, config))
            _log(ax, "x", spec.opt("log", False))
            if share:
                ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        else:
            ax.set_xticks(
                pos,
                names,
                rotation=30 if len(order) > 6 else 0,
                ha="right" if len(order) > 6 else "center",
            )
            ax.grid(axis="x", visible=False)
            ax.set_ylabel(value_label(spec, config))
            _log(ax, "y", spec.opt("log", False))
            if share:
                ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        if spec.color and k == 0:
            ax.legend(title=label(config, spec.color), loc="best")
    return finish(
        fig, spec, config, f"{value_label(spec, config)} by {label(config, spec.x).lower()}"
    )


KINDS["bar"] = ChartKind(
    "Bar",
    {
        "x": Field(True, "cat", "Category"),
        "y": Field(False, "num", "Value (blank = count rows)"),
        "color": Field(False, "cat", "Split by"),
        "facet": Field(False, "cat", "Facet by"),
    },
    _compute_bar,
    _draw_bar,
    options=(
        Opt("horizontal", "bool", True, "Horizontal bars"),
        Opt("stacked", "bool", False, "Stack series"),
        Opt("labels", "bool", True, "Value labels"),
        Opt("log", "bool", False, "Log value axis"),
    ),
    facetable=True,
    uses_agg=True,
    uses_sort=True,
)


# --- line -------------------------------------------------------------------------------------


def _compute_line(df, spec, config):
    d = apply_filters(df, spec.filters)
    return aggregate(d, [spec.x, spec.color, spec.facet], spec.y, spec.agg).sort_values(spec.x)


def _draw_line(plot, spec, config, ctx):
    series = _groups(plot, spec.color)
    colors = series_colors(config, len(series))
    fig, pairs = panels(plot, spec, config, sharex=True, sharey=True)
    for k, (ax, d) in enumerate(pairs):
        for c, s in zip(colors, series, strict=True):
            g = d if s is None else d[d[spec.color] == s]
            ax.plot(
                g[spec.x],
                g["value"],
                marker="o",
                lw=2,
                color=c,
                label=fmt_cat(s) if s is not None else None,
            )
        ax.set_xlabel(label(config, spec.x))
        ax.set_ylabel(value_label(spec, config))
        _log(ax, "y", spec.opt("log", False))
        if spec.agg == "share":
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        if spec.color and k == 0:
            ax.legend(title=label(config, spec.color))
    return finish(
        fig, spec, config, f"{value_label(spec, config)} by {label(config, spec.x).lower()}"
    )


KINDS["line"] = ChartKind(
    "Line",
    {
        "x": Field(True, "any", "X axis (ordered)"),
        "y": Field(False, "num", "Value (blank = count rows)"),
        "color": Field(False, "cat", "Series"),
        "facet": Field(False, "cat", "Facet by"),
    },
    _compute_line,
    _draw_line,
    options=(Opt("log", "bool", False, "Log value axis"),),
    facetable=True,
    uses_agg=True,
)


# --- scatter ----------------------------------------------------------------------------------


def _compute_scatter(df, spec, config):
    d = apply_filters(df, spec.filters)
    cols = list(dict.fromkeys(c for c in (spec.x, spec.y, spec.color, spec.size, spec.facet) if c))
    return d[cols].dropna(subset=[spec.x, spec.y])


def _scaled_size(s: pd.Series, full: pd.Series) -> np.ndarray:
    lo, hi = full.min(), full.max()
    return 20 + 220 * ((s - lo) / (hi - lo) if hi > lo else s * 0 + 0.3)


def _draw_scatter(plot, spec, config, ctx):
    pal = palette(config)
    numeric_color = (
        bool(spec.color)
        and pd.api.types.is_numeric_dtype(plot[spec.color])
        and (not pd.api.types.is_bool_dtype(plot[spec.color]))
    )
    series = [None] if (not spec.color or numeric_color) else _groups(plot, spec.color)
    colors = series_colors(config, len(series))
    norm = Normalize(plot[spec.color].min(), plot[spec.color].max()) if numeric_color else None
    fig, pairs = panels(plot, spec, config, sharex=True, sharey=True)
    for k, (ax, d) in enumerate(pairs):
        for c, s in zip(colors, series, strict=True):
            g = d if s is None else d[d[spec.color] == s]
            kw = {"s": _scaled_size(g[spec.size], plot[spec.size]) if spec.size else 38}
            if numeric_color:
                kw.update(c=g[spec.color], cmap="Reds", norm=norm)
            else:
                kw["color"] = c if spec.color else pal["red"]
            ax.scatter(g[spec.x], g[spec.y], alpha=0.8, edgecolor="white", linewidth=0.4,
                       label=fmt_cat(s) if s is not None else None, **kw)  # fmt: skip
        if spec.opt("trend", False) and len(d) > 2:
            m, b = np.polyfit(d[spec.x], d[spec.y], 1)
            r = np.corrcoef(d[spec.x], d[spec.y])[0, 1]
            xs = np.array([d[spec.x].min(), d[spec.x].max()])
            ax.plot(
                xs, m * xs + b, color=pal["ink"], ls="--", lw=1.2, label=f"Linear fit (r = {r:.2f})"
            )
        ax.set_xlabel(label(config, spec.x))
        ax.set_ylabel(label(config, spec.y))
        _log(ax, "x", spec.opt("log_x", False))
        _log(ax, "y", spec.opt("log_y", False))
        if k == 0 and (spec.color and not numeric_color or spec.opt("trend", False)):
            ax.legend(title=label(config, spec.color) if spec.color and not numeric_color else None)
    if numeric_color:
        fig.colorbar(
            ScalarMappable(norm, "Reds"),
            ax=pairs[0][0] if len(pairs) == 1 else [a for a, _ in pairs],
            shrink=0.7,
            label=label(config, spec.color),
        )
    note = f"Point size = {label(config, spec.size).lower()}" if spec.size else None
    sub = None
    if note:
        ds = datasets.DATASETS[spec.dataset]
        sub = f"{ds.label}: {ds.grain}  ·  {note}"
    return finish(
        fig, spec, config, f"{label(config, spec.y)} vs. {label(config, spec.x).lower()}", sub
    )


KINDS["scatter"] = ChartKind(
    "Scatter",
    {
        "x": Field(True, "num", "X axis"),
        "y": Field(True, "num", "Y axis"),
        "color": Field(False, "any", "Color by"),
        "size": Field(False, "num", "Size by"),
        "facet": Field(False, "cat", "Facet by"),
    },
    _compute_scatter,
    _draw_scatter,
    options=(
        Opt("trend", "bool", False, "Linear trend line"),
        Opt("log_x", "bool", False, "Log x axis"),
        Opt("log_y", "bool", False, "Log y axis"),
    ),
    facetable=True,
)


# --- histogram --------------------------------------------------------------------------------


def _compute_hist(df, spec, config):
    d = apply_filters(df, spec.filters)
    cols = list(dict.fromkeys(c for c in (spec.x, spec.color, spec.facet) if c))
    return d[cols].dropna(subset=[spec.x])


def _draw_hist(plot, spec, config, ctx):
    pal = palette(config)
    series = _groups(plot, spec.color)
    colors = series_colors(config, len(series))
    edges = np.histogram_bin_edges(plot[spec.x], bins=int(spec.opt("bins", 30)))
    fig, pairs = panels(plot, spec, config, sharex=True, sharey=True)
    for k, (ax, d) in enumerate(pairs):
        for c, s in zip(colors, series, strict=True):
            g = d if s is None else d[d[spec.color] == s]
            ax.hist(g[spec.x], bins=edges, color=c, alpha=0.75 if spec.color else 0.9,
                    label=fmt_cat(s) if s is not None else None)  # fmt: skip
        if spec.opt("median", True):
            ax.axvline(d[spec.x].median(), color=pal["ink"], ls="--", lw=1)
        ax.set_xlabel(label(config, spec.x))
        ax.set_ylabel("Number of rows")
        _log(ax, "y", spec.opt("log", False))
        if spec.color and k == 0:
            ax.legend(title=label(config, spec.color))
    return finish(fig, spec, config, f"Distribution of {label(config, spec.x).lower()}")


KINDS["hist"] = ChartKind(
    "Histogram",
    {
        "x": Field(True, "num", "Variable"),
        "color": Field(False, "cat", "Overlay by"),
        "facet": Field(False, "cat", "Facet by"),
    },
    _compute_hist,
    _draw_hist,
    options=(
        Opt("bins", "int", 30, "Bins", 5, 100),
        Opt("median", "bool", True, "Show median line"),
        Opt("log", "bool", False, "Log count axis"),
    ),
    facetable=True,
)


# --- box --------------------------------------------------------------------------------------


def _compute_box(df, spec, config):
    d = apply_filters(df, spec.filters)
    cols = list(dict.fromkeys(c for c in (spec.x, spec.y, spec.facet) if c))
    d = d[cols].dropna(subset=[spec.x, spec.y])
    if spec.top_n:
        d = d[d[spec.x].isin(d[spec.x].value_counts().nlargest(spec.top_n).index)]
    return d


def _draw_box(plot, spec, config, ctx):
    pal = palette(config)
    med = plot.groupby(spec.x)[spec.y].median()
    if spec.sort in ("asc", "desc"):
        order = list(med.sort_values(ascending=spec.sort == "asc").index)
    else:
        order = sorted(med.index)
    fig, pairs = panels(plot, spec, config, sharey=True)
    for ax, d in pairs:
        groups = [d.loc[d[spec.x] == o, spec.y].to_numpy() for o in order]
        keep = [i for i, g in enumerate(groups) if len(g)]
        bp = ax.boxplot([groups[i] for i in keep], positions=keep, widths=0.6, patch_artist=True,
                        medianprops={"color": pal["red"], "lw": 2}, flierprops={"markersize": 3, "alpha": 0.5})  # fmt: skip
        for box in bp["boxes"]:
            box.set(facecolor="#F2F2F3", edgecolor=pal["muted"])
        names = [f"{fmt_cat(o)}\n(n={len(g)})" for o, g in zip(order, groups, strict=True)]
        ax.set_xticks(range(len(order)), names, rotation=30 if len(order) > 5 else 0,
                      ha="right" if len(order) > 5 else "center", fontsize=8)  # fmt: skip
        ax.grid(axis="x", visible=False)
        ax.set_ylabel(label(config, spec.y))
        _log(ax, "y", spec.opt("log", False))
    return finish(fig, spec, config, f"{label(config, spec.y)} by {label(config, spec.x).lower()}")


KINDS["box"] = ChartKind(
    "Box plot",
    {
        "x": Field(True, "cat", "Category"),
        "y": Field(True, "num", "Value"),
        "facet": Field(False, "cat", "Facet by"),
    },
    _compute_box,
    _draw_box,
    options=(Opt("log", "bool", False, "Log value axis"),),
    facetable=True,
    uses_sort=True,
    note="Sort orders categories by median.",
)


# --- heatmap ----------------------------------------------------------------------------------


def _compute_heatmap(df, spec, config):
    d = apply_filters(df, spec.filters)
    return aggregate(d, [spec.x, spec.y], spec.color, spec.agg)


def _draw_heatmap(plot, spec, config, ctx):
    pal = palette(config)
    piv = plot.pivot_table(index=spec.y, columns=spec.x, values="value", aggfunc="sum")
    fig = new_figure(config)
    ax = fig.subplots()
    share = spec.agg == "share"
    im = ax.imshow(np.ma.masked_invalid(piv.to_numpy(dtype=float)), cmap="Reds", aspect="auto")
    ax.set_xticks(range(piv.shape[1]), [fmt_cat(c) for c in piv.columns],
                  rotation=30 if piv.shape[1] > 6 else 0, ha="right" if piv.shape[1] > 6 else "center")  # fmt: skip
    ax.set_yticks(range(piv.shape[0]), [fmt_cat(i) for i in piv.index])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel(label(config, spec.x))
    ax.set_ylabel(label(config, spec.y))
    if piv.size <= 150:
        vals = piv.to_numpy(dtype=float)
        mid = (
            np.nanmin(vals) + 0.6 * (np.nanmax(vals) - np.nanmin(vals))
            if np.isfinite(vals).any()
            else 0
        )
        for i in range(piv.shape[0]):
            for j in range(piv.shape[1]):
                if np.isfinite(vals[i, j]):
                    ax.text(j, i, fmt_value(vals[i, j], share), ha="center", va="center", fontsize=8,
                            color="white" if vals[i, j] > mid else pal["ink"])  # fmt: skip
    vlabel = value_label(spec, config, spec.color)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, label=vlabel)
    if share:
        cb.formatter = PercentFormatter(1.0)
    title = f"{vlabel} by {label(config, spec.x).lower()} and {label(config, spec.y).lower()}"
    return finish(fig, spec, config, title)


KINDS["heatmap"] = ChartKind(
    "Heatmap",
    {
        "x": Field(True, "cat", "Columns"),
        "y": Field(True, "cat", "Rows"),
        "color": Field(False, "num", "Cell value (blank = count rows)"),
    },
    _compute_heatmap,
    _draw_heatmap,
    uses_agg=True,
)


# --- concentration curve ----------------------------------------------------------------------


def _compute_curve(df, spec, config):
    d = apply_filters(df, spec.filters)
    val_col = spec.y or spec.x
    d = d.dropna(subset=list(dict.fromkeys([spec.x, val_col])))
    val = d[val_col].clip(lower=0).to_numpy(dtype=float)
    ranked = val[np.argsort(-d[spec.x].to_numpy(dtype=float), kind="stable")]
    n, total = len(val), val.sum()
    share = np.arange(1, n + 1) / n
    return pd.DataFrame(
        {
            "share_of_rows": np.r_[0.0, share],
            "cum_share_ranked": np.r_[0.0, np.cumsum(ranked) / total],
            "cum_share_best": np.r_[0.0, np.cumsum(np.sort(val)[::-1]) / total],
        }
    )


def _draw_curve(plot, spec, config, ctx):
    pal = palette(config)
    q = float(spec.opt("top_share", 0.1))
    hit = float(np.interp(q, plot["share_of_rows"], plot["cum_share_ranked"]))
    fig = new_figure(config)
    ax = fig.subplots()
    ax.fill_between(
        plot["share_of_rows"],
        plot["cum_share_ranked"],
        plot["share_of_rows"],
        color=pal["red"],
        alpha=0.1,
    )
    ax.plot(
        plot["share_of_rows"],
        plot["cum_share_best"],
        color=pal["blue"],
        ls="--",
        lw=1.5,
        label="Best possible ranking",
    )
    ax.plot(
        plot["share_of_rows"],
        plot["cum_share_ranked"],
        color=pal["red"],
        lw=2.8,
        label=f"Ranked by {label(config, spec.x).lower()}",
    )
    ax.plot([0, 1], [0, 1], color=pal["muted"], ls=":", lw=1.5, label="No targeting (random)")
    ax.plot([q], [hit], "o", color=pal["red"], ms=9, zorder=5)
    ax.annotate(
        f"{hit:.0%}",
        (q, hit),
        xytext=(10, -4),
        textcoords="offset points",
        fontsize=14,
        fontweight="bold",
        color=pal["red"],
    )
    ax.axvline(q, color=pal["rule"], lw=1)
    noun = datasets.DATASETS[spec.dataset].label.lower()
    ax.set_xlabel(f"Share of {noun}, highest ranked first")
    ax.set_ylabel(f"Cumulative share of {label(config, spec.y or spec.x).lower()}")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right")
    title = f"Top {q:.0%} of {noun} hold {hit:.0%} of {label(config, spec.y or spec.x).lower()}"
    return finish(fig, spec, config, title)


KINDS["concentration"] = ChartKind(
    "Concentration curve",
    {
        "x": Field(True, "num", "Rank by (score)"),
        "y": Field(False, "num", "Accumulate (blank = same as rank)"),
    },
    _compute_curve,
    _draw_curve,
    options=(Opt("top_share", "float", 0.1, "Highlight top share", 0.01, 0.5),),
)

__all__ = ["AGGS", "KINDS", "ChartKind", "Field", "Opt"]
