"""Data-coverage figures (deck slides 6-8): what we have, and how little of it was ever observed."""

from __future__ import annotations

import pandas as pd

from tobacco_inspect.viz.registry import attach_table, figure
from tobacco_inspect.viz.theme import new_figure, palette, titled

SRC = "Source: PA Dept. of Revenue licenses; FDA undercover-check records (Pittsburgh city limits)."


def _funnel(data, config) -> pd.DataFrame:
    r = data["risk"]
    retail = r[r["retail_license"]]
    return pd.DataFrame(
        {
            "stage": [
                "Active licenses",
                "Retail licenses",
                "Distinct retail locations",
                "Retail licenses with FDA history",
            ],
            "n": [
                len(r),
                len(retail),
                retail["location_key"].nunique(),
                int(retail["fda_observed"].sum()),
            ],
        }
    )


@figure("coverage_funnel", "Overview", "License universe and FDA-history linkage", needs=("risk",))
def coverage_funnel(data, config):
    pal = palette(config)
    t = _funnel(data, config)
    fig = new_figure(config)
    ax = fig.subplots()
    colors = [pal["rule"], pal["muted"], pal["blue"], pal["red"]]
    ax.barh(t["stage"][::-1], t["n"][::-1], color=colors[::-1], height=0.62)
    for y, n in enumerate(t["n"][::-1]):
        ax.text(n + t["n"].max() * 0.012, y, f"{n:,}", va="center", fontweight="bold", fontsize=12)
    ax.set_xlim(0, t["n"].max() * 1.12)
    ax.grid(axis="y", visible=False)
    linked = t["n"].iloc[3] / t["n"].iloc[1]
    return titled(
        fig,
        config,
        "Fewer than half of retail licenses have any enforcement history",
        f"{linked:.0%} of retail licenses link to a prior FDA check; the rest are unobserved",
        SRC,
    )


attach_table("coverage_funnel")(_funnel)


def _by_year(data, config) -> pd.DataFrame:
    return data["fda_by_year"].query("city > 0").copy()


@figure(
    "checks_by_year", "Overview", "City checks and violation rate by year", needs=("fda_by_year",)
)
def checks_by_year(data, config):
    pal = palette(config)
    t = _by_year(data, config)
    fig = new_figure(config)
    ax = fig.subplots()
    ax.bar(t["yr"], t["city"], color=pal["muted"], width=0.7, label="City checks")
    ax.set_ylabel("Checks in city limits")
    ax2 = ax.twinx()
    ax2.plot(
        t["yr"], t["viol_rate"] * 100, color=pal["red"], marker="o", lw=2, label="Violation rate"
    )
    ax2.set_ylabel("Violation rate (%)", color=pal["red"])
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(pal["rule"])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left")
    return titled(
        fig,
        config,
        "Enforcement volume has been uneven, and fell steeply after 2019",
        "The deck's 30-day Decision Date guard limits sensitivity to this swing",
        SRC,
    )


attach_table("checks_by_year")(_by_year)


def _date_quality(data, config) -> pd.DataFrame:
    c = data["checks"]
    n, miss = len(c), int(c["inspection_date_parsed"].isna().sum())
    return pd.DataFrame(
        {"field": ["Usable Inspection Date", "Missing (Decision Date used)"], "n": [n - miss, miss]}
    )


@figure("date_quality", "Overview", "Inspection-date completeness", needs=("checks",))
def date_quality(data, config):
    pal = palette(config)
    t = _date_quality(data, config)
    fig = new_figure(config)
    ax = fig.subplots()
    ax.barh([""], [t["n"].iloc[0]], color=pal["blue"], label=t["field"].iloc[0])
    ax.barh(
        [""], [t["n"].iloc[1]], left=[t["n"].iloc[0]], color=pal["red"], label=t["field"].iloc[1]
    )
    for x, n in (
        (t["n"].iloc[0] / 2, t["n"].iloc[0]),
        (t["n"].iloc[0] + t["n"].iloc[1] / 2, t["n"].iloc[1]),
    ):
        ax.text(
            x, 0, f"{n:,}", ha="center", va="center", color="white", fontweight="bold", fontsize=14
        )
    ax.grid(False)
    ax.set_yticks([])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    total = int(t["n"].sum())
    return titled(
        fig,
        config,
        f"{t['n'].iloc[1]:,} of {total:,} historical checks lack an inspection date",
        "Timing falls back to Decision Date with a strict 30-day guard against leakage",
        SRC,
    )


attach_table("date_quality")(_date_quality)
