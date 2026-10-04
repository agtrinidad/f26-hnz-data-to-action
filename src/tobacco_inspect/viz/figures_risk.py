"""Risk-model figures (deck slide 4): r_i = h_i * p_i + lambda * delta_i."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tobacco_inspect.viz.registry import attach_table, figure
from tobacco_inspect.viz.theme import new_figure, palette, titled

SRC = (
    "Source: tobacco_inspect risk model; Synar 2025 Allegheny benchmark; FDA OCE statewide checks."
)


def _lam(config) -> float:
    return float(config.prize["lambda_deterrence"])


def _decomp(data, config, top_n) -> pd.DataFrame:
    r = data["risk"].nlargest(int(top_n), "prize").copy()
    r["h_x_p"] = r["h"] * r["p"]
    r["followup"] = r["prize"] - r["h_x_p"]
    r["label"] = r["trade_name"].str.title().str.slice(0, 26)
    return r[["license_id", "label", "h", "p", "h_x_p", "followup", "prize"]]


@figure(
    "top_stores",
    "Risk",
    "Top stores by prize, decomposed",
    needs=("risk",),
    params={"top_n": (15, 5, 40, 1)},
)
def top_stores(data, config, top_n):
    pal = palette(config)
    t = _decomp(data, config, top_n).iloc[::-1]
    fig = new_figure(config)
    ax = fig.subplots()
    ax.barh(
        t["label"], t["h_x_p"], color=pal["red"], label="Exposure × violation probability (h·p)"
    )
    ax.barh(
        t["label"], t["followup"], left=t["h_x_p"], color=pal["blue"], label="Follow-up term (Δ)"
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    ax.set_xlabel("Prize r_i")
    ax.grid(axis="y", visible=False)
    return titled(
        fig,
        config,
        f"Top {int(top_n)} stores by risk-weighted prize",
        "Most of the prize comes from exposure × probability; Δ re-ranks stores that are due a follow-up",
        SRC,
    )


attach_table("top_stores")(_decomp)


def _calibration(data, config) -> pd.DataFrame:
    r = data["risk"]
    return pd.DataFrame(
        {
            "series": [
                "Raw model p (observed stores)",
                "Calibrated p (all stores)",
                "Synar Allegheny benchmark",
            ],
            "mean_p": [
                r.loc[r["fda_observed"], "p_raw"].mean(),
                r["p"].mean(),
                float(config.raw["risk"].get("population_rate", 0.26)),
            ],
        }
    )


@figure("calibration", "Risk", "Calibration to the Synar benchmark", needs=("risk",))
def calibration(data, config):
    pal = palette(config)
    t = _calibration(data, config)
    fig = new_figure(config)
    ax = fig.subplots()
    bars = ax.bar(
        t["series"], t["mean_p"], color=[pal["muted"], pal["red"], pal["blue"]], width=0.55
    )
    for b, v in zip(bars, t["mean_p"], strict=True):
        ax.text(
            b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.1%}", ha="center", fontweight="bold"
        )
    ax.set_ylabel("Mean violation probability")
    ax.grid(axis="x", visible=False)
    shift = (data.get("risk_summary") or {}).get("calibration_shift_logit")
    sub = "Historical checks over-sample risky stores; a logit shift rescales to the random-sample rate"
    if shift is not None:
        sub += f" (shift {shift:+.2f})"
    return titled(fig, config, "Predicted probabilities are corrected for selection bias", sub, SRC)


attach_table("calibration")(_calibration)


def _lift(data, config) -> pd.DataFrame:
    g = data["gate_a_backtest"]
    g = g[(g["subset"] == "PA") & (g["frac"] == 0.1)]
    return g.groupby("scorer")[["lift", "lift_lo", "lift_hi", "auc"]].mean().reset_index()


@figure("backtest_lift", "Risk", "Backtest: top-decile lift by scorer", needs=("gate_a_backtest",))
def backtest_lift(data, config):
    pal = palette(config)
    t = _lift(data, config).sort_values("lift")
    fig = new_figure(config)
    ax = fig.subplots()
    colors = [pal["red"] if s == "model" else pal["muted"] for s in t["scorer"]]
    err = np.array([t["lift"] - t["lift_lo"], t["lift_hi"] - t["lift"]])
    ax.barh(t["scorer"].str.replace("_", " "), t["lift"], xerr=err, color=colors, height=0.6,
            error_kw={"ecolor": pal["ink"], "lw": 1})  # fmt: skip
    ax.axvline(1, color=pal["ink"], lw=1, ls="--")
    ax.set_xlabel("Violations found in top 10% vs. random (lift, mean of FY2022-25)")
    ax.grid(axis="y", visible=False)
    return titled(
        fig,
        config,
        "Risk ranking beats status-quo follow-up on held-out years",
        "Time-split replay on statewide PA checks; bars show 95% intervals",
        SRC,
    )


attach_table("backtest_lift")(_lift)
