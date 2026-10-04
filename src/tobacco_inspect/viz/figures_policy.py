"""Policy figures: coverage regimes, marginal cost of a full sweep, equity, simulated policies."""

from __future__ import annotations

import pandas as pd

from tobacco_inspect.viz.registry import attach_table, figure
from tobacco_inspect.viz.theme import new_figure, palette, titled

SRC = "Source: tobacco_inspect regime/valuation scenarios (config/default.yaml; ASSUMED/PROXIED inputs)."


def _frontier(data, config) -> pd.DataFrame:
    return data["regime_frontier"].query(
        "policy in ['random','targeted_model_p','census_floor','census_floor+adaptive_second_pass']"
    )


@figure("regime_frontier", "Policy", "Violators found vs. checks", needs=("regime_frontier",))
def regime_frontier(data, config):
    pal = palette(config)
    t = _frontier(data, config)
    style = {
        "random": ("Random", pal["muted"], "o"),
        "targeted_model_p": ("Model-targeted", pal["red"], "o"),
        "census_floor": ("Census floor", pal["blue"], "s"),
        "census_floor+adaptive_second_pass": ("Census + adaptive 2nd pass", pal["coral"], "D"),
    }
    fig = new_figure(config)
    ax = fig.subplots()
    for pol, (label, color, marker) in style.items():
        d = t[t["policy"] == pol].sort_values("checks")
        ax.plot(d["checks"], d["distinct_violators"], color=color, marker=marker, lw=2, label=label)
    ax.set_xlabel("Checks per year")
    ax.set_ylabel("Expected distinct violators found")
    ax.legend(loc="upper left")
    return titled(
        fig,
        config,
        "A full sweep finds the most violators; targeting only helps below it",
        "Expected distinct violators vs. annual check volume, by policy",
        SRC,
    )


attach_table("regime_frontier")(_frontier)


def _marginal(data, config) -> pd.DataFrame:
    return data["valuation_marginal"][
        ["option", "incremental_checks", "incremental_dollars", "dollars_per_incremental_check",
         "incremental_distinct_violators", "dollars_per_incremental_violator"]
    ]  # fmt: skip


@figure(
    "marginal_value", "Policy", "Marginal cost of the full sweep", needs=("valuation_marginal",)
)
def marginal_value(data, config):
    pal = palette(config)
    t = _marginal(data, config)
    fig = new_figure(config)
    axes = fig.subplots(1, 2)
    labels = ["Census floor", "+ adaptive\nsecond pass"]
    for ax, col, title, color in (
        (axes[0], "incremental_dollars", "Incremental cost ($/yr)", pal["blue"]),
        (axes[1], "dollars_per_incremental_violator", "Cost per added violator ($)", pal["red"]),
    ):
        bars = ax.bar(labels, t[col], color=color, width=0.5)
        for b, v in zip(bars, t[col], strict=True):
            ax.text(
                b.get_x() + b.get_width() / 2,
                v * 1.01,
                f"${v:,.0f}",
                ha="center",
                fontweight="bold",
            )
        ax.set_title(title, fontsize=10.5, color=pal["muted"], loc="left")
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, t[col].max() * 1.15)
    first = t.iloc[0]
    return titled(
        fig,
        config,
        f"A full sweep adds ${first['incremental_dollars']:,.0f} a year over today's volume",
        f"About ${first['dollars_per_incremental_check']:,.0f} per added check and "
        f"${first['dollars_per_incremental_violator']:,.0f} per added distinct violator (bottom-up cost)",
        SRC,
    )


attach_table("marginal_value")(_marginal)


def _equity(data, config) -> pd.DataFrame:
    return data["regime_equity"][
        [
            "regime",
            "share_retailers_high_poverty",
            "share_inspections_high_poverty",
            "share_stores_never_checked",
        ]
    ].copy()


@figure(
    "equity_regimes", "Policy", "Where checks land vs. where stores are", needs=("regime_equity",)
)
def equity_regimes(data, config):
    pal = palette(config)
    t = _equity(data, config)
    fig = new_figure(config)
    ax = fig.subplots()
    x = range(len(t))
    w = 0.34
    ax.bar(
        [i - w / 2 for i in x],
        t["share_retailers_high_poverty"],
        w,
        color=pal["muted"],
        label="Share of retailers",
    )
    ax.bar(
        [i + w / 2 for i in x],
        t["share_inspections_high_poverty"],
        w,
        color=pal["red"],
        label="Share of inspections",
    )
    for i, (a, b) in enumerate(
        zip(t["share_retailers_high_poverty"], t["share_inspections_high_poverty"], strict=True)
    ):
        ax.text(i - w / 2, a + 0.004, f"{a:.0%}", ha="center", fontsize=10)
        ax.text(i + w / 2, b + 0.004, f"{b:.0%}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(list(x), t["regime"])
    ax.set_ylabel("In high-poverty tracts")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    return titled(
        fig,
        config,
        "Neither regime concentrates checks in high-poverty tracts",
        "Share of inspections vs. share of retailers located in high-poverty tracts",
        SRC,
    )


attach_table("equity_regimes")(_equity)


def _sim(data, config) -> pd.DataFrame:
    s = data["simulation_policies"]
    cell = s.sort_values(["delta", "rho"]).iloc[-1][
        ["delta", "rho"]
    ]  # strongest simulated response
    s = s[(s["delta"] == cell["delta"]) & (s["rho"] == cell["rho"])]
    return s.sort_values("found_per_cycle")


@figure(
    "simulated_policies",
    "Policy",
    "Simulated policies under strategic response",
    needs=("simulation_policies",),
)
def simulated_policies(data, config):
    pal = palette(config)
    t = _sim(data, config)
    fig = new_figure(config)
    ax = fig.subplots()
    colors = [pal["red"] if "thompson" in p else pal["muted"] for p in t["policy"]]
    err = [t["found_per_cycle"] - t["lo"], t["hi"] - t["found_per_cycle"]]
    ax.barh(t["policy"].str.replace("_", " "), t["found_per_cycle"], xerr=err, color=colors, height=0.6,
            error_kw={"ecolor": pal["ink"], "lw": 1})  # fmt: skip
    ax.set_xlabel("Violations found per cycle")
    ax.grid(axis="y", visible=False)
    d, r = t["delta"].iloc[0], t["rho"].iloc[0]
    return titled(
        fig,
        config,
        "Predictable schedules lose their edge once stores react",
        f"Strongest response simulated (deterrence δ={d:g}, persistence ρ={r:g}); randomized rotation holds up",
        SRC,
    )


attach_table("simulated_policies")(_sim)
