"""Geographic figures: where risk sits, where clusters are, and where nothing has been observed."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from tobacco_inspect.eval import geo
from tobacco_inspect.viz.registry import attach_table, figure
from tobacco_inspect.viz.theme import new_figure, palette, titled

SRC = "Source: PA Dept. of Revenue licenses (345 retail locations); Census TIGER 2023 tracts; NCES schools."
CLUSTER_PARAMS = {"eps_m": (400, 150, 1000, 50), "min_samples": (4, 2, 10, 1)}


def _locations(data) -> pd.DataFrame:
    r = data["risk"]
    return geo.one_row_per_location(r[r["retail_license"]])


def base_map(ax, data, pal, fill: pd.Series | None = None, cmap: str = "Reds", label: str = ""):
    """Tract outlines (optionally shaded by `fill`, indexed by tract_geoid); equal-ish aspect."""
    tr = data.get("tracts")
    if tr is not None:
        city = _locations(data)
        tr = tr[tr["tract_geoid"].isin(city["tract_geoid"])]
        if fill is not None:
            tr = tr.assign(_v=tr["tract_geoid"].map(fill))
            tr.plot(ax=ax, column="_v", cmap=cmap, edgecolor="white", linewidth=0.6,
                    legend=True, legend_kwds={"label": label, "shrink": 0.6},
                    missing_kwds={"color": "#F2F2F3"})  # fmt: skip
        else:
            tr.plot(ax=ax, color="#F2F2F3", edgecolor="white", linewidth=0.6)
    ax.set_aspect(1 / np.cos(np.radians(40.44)))
    ax.grid(False)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


@figure("map_prize", "Geography", "Store prize across the city", needs=("risk",))
def map_prize(data, config):
    pal = palette(config)
    loc = _locations(data).sort_values("prize")
    fig = new_figure(config)
    ax = fig.subplots()
    base_map(ax, data, pal)
    sc = ax.scatter(loc["lon"], loc["lat"], c=loc["prize"], cmap="Reds", s=28 + 220 * loc["prize"],
                    edgecolor=pal["ink"], linewidth=0.3, alpha=0.9)  # fmt: skip
    fig.colorbar(sc, ax=ax, shrink=0.6, label="Prize r_i")
    schools = data.get("schools")
    if schools is not None:
        ax.scatter(
            schools["lon"],
            schools["lat"],
            marker="^",
            s=14,
            color=pal["blue"],
            alpha=0.6,
            label="School",
        )
        ax.legend(loc="lower left")
    ax.autoscale_view()
    return titled(
        fig, config, "High-prize stores are not evenly spread",
        "One point per retail location; size and color scale with risk-weighted prize", SRC,
    )  # fmt: skip


attach_table("map_prize")(
    lambda data, config: _locations(data).sort_values("prize", ascending=False)
)


def _clusters(data, config, eps_m, min_samples) -> pd.DataFrame:
    g = config.raw["viz"]["geo"]
    return geo.hotspot_table(
        _locations(data), "prize", float(eps_m), int(min_samples), float(g["unobserved_flag"])
    )


@figure(
    "map_clusters", "Geography", "Store clusters (DBSCAN)", needs=("risk",), params=CLUSTER_PARAMS
)
def map_clusters(data, config, eps_m, min_samples):
    pal = palette(config)
    loc = _locations(data)
    loc["cluster"] = geo.cluster_stores(loc, float(eps_m), int(min_samples))
    hot = _clusters(data, config, eps_m, min_samples)
    fig = new_figure(config)
    ax = fig.subplots()
    base_map(ax, data, pal)
    noise = loc[loc["cluster"] < 0]
    ax.scatter(noise["lon"], noise["lat"], s=14, color=pal["muted"], alpha=0.5)
    clustered = loc[loc["cluster"] >= 0]
    ax.scatter(
        clustered["lon"], clustered["lat"], s=34, c=pal["red"], edgecolor="white", linewidth=0.4
    )
    for _, c in hot.iterrows():
        ax.annotate(f"#{int(c['rank'])}", (c["lon"], c["lat"]), fontsize=11, fontweight="bold",
                    xytext=(0, 9), textcoords="offset points", ha="center", color=pal["ink"])  # fmt: skip
    ax.legend(
        handles=[
            Line2D(
                [], [], marker="o", ls="", color=pal["red"], label=f"Clustered ({len(clustered)})"
            ),
            Line2D([], [], marker="o", ls="", color=pal["muted"], label=f"Isolated ({len(noise)})"),
        ],
        loc="lower left",
    )
    return titled(
        fig, config, f"{len(hot)} clusters hold {len(clustered)} of {len(loc)} retail locations",
        f"DBSCAN, {int(eps_m)} m radius, at least {int(min_samples)} stores; numbers rank clusters by summed prize", SRC,
    )  # fmt: skip


attach_table("map_clusters")(_clusters)


@figure(
    "cluster_ranking",
    "Geography",
    "Cluster ranking by prize mass",
    needs=("risk",),
    params=CLUSTER_PARAMS,
)
def cluster_ranking(data, config, eps_m, min_samples):
    pal = palette(config)
    hot = (
        _clusters(data, config, eps_m, min_samples).head(int(config.raw["viz"]["top_n"])).iloc[::-1]
    )
    fig = new_figure(config)
    ax = fig.subplots()
    colors = [pal["coral"] if f else pal["blue"] for f in hot["flag_unobserved"]]
    ax.barh([f"#{int(r)}  ({int(n)} stores)" for r, n in zip(hot["rank"], hot["stores"], strict=True)],
            hot["prize_sum"], color=colors, height=0.65)  # fmt: skip
    ax.set_xlabel("Summed prize")
    ax.grid(axis="y", visible=False)
    ax.legend(
        handles=[
            Line2D(
                [],
                [],
                marker="s",
                ls="",
                color=pal["coral"],
                label="Mostly unobserved: sweep labels these first",
            ),
            Line2D([], [], marker="s", ls="", color=pal["blue"], label="Mostly observed"),
        ],
        loc="lower right",
    )
    return titled(
        fig, config, "A few clusters carry most of the risk mass",
        "Clusters ranked by summed prize; color marks the share of stores never checked by FDA", SRC,
    )  # fmt: skip


attach_table("cluster_ranking")(_clusters)


def _tract_density(data, config) -> pd.DataFrame:
    t = geo.tract_summary(_locations(data))
    cov = data.get("coverage_by_tract")
    if cov is not None:
        t = t.merge(
            cov[["tract_geoid", "poverty_rate", "youth_share"]], on="tract_geoid", how="left"
        )
    return t


@figure("map_tract_prize", "Geography", "Tract prize mass", needs=("risk", "tracts"))
def map_tract_prize(data, config):
    pal = palette(config)
    t = _tract_density(data, config).set_index("tract_geoid")
    fig = new_figure(config)
    ax = fig.subplots()
    base_map(ax, data, pal, fill=t["prize_sum"], cmap="Reds", label="Summed prize")
    return titled(
        fig, config, "Risk mass is concentrated in a handful of tracts",
        "Summed store prize by census tract (retail locations only)", SRC,
    )  # fmt: skip


attach_table("map_tract_prize")(_tract_density)


@figure("map_observed", "Geography", "Observed vs. unobserved stores", needs=("risk",))
def map_observed(data, config):
    pal = palette(config)
    loc = _locations(data)
    fig = new_figure(config)
    ax = fig.subplots()
    base_map(ax, data, pal)
    for observed, color, label in (
        (False, pal["muted"], "No FDA history"),
        (True, pal["red"], "FDA history"),
    ):
        d = loc[loc["fda_observed"] == observed]
        ax.scatter(d["lon"], d["lat"], s=30, color=color, alpha=0.85, edgecolor="white", linewidth=0.4,
                   label=f"{label} ({len(d)})")  # fmt: skip
    ax.legend(loc="lower left")
    ax.autoscale_view()
    return titled(
        fig, config, "Where we have never looked is where a sweep adds the most information",
        "Retail locations with and without any prior FDA undercover check", SRC,
    )  # fmt: skip


attach_table("map_observed")(
    lambda data, config: _locations(data)[["location_key", "trade_name", "fda_observed", "prize"]]
)
