"""Marginal value of moving from today's budget-capped program to a census-floor regime.

The headline cost is *marginal*: what DOH adds to a running, contracted program (bottom-up cost
of the extra checks), not the full price of a new program (top-down, kept as a sensitivity).

This module adds only what `eval/census.py` (cost), `eval/regime.py` (frontier, year simulation)
and `pipeline.regime` do not report: incremental cost per added check and violator, a
break-even table for deterrence that asserts no dollar value of a prevented sale, the funder's
opportunity-cost comparison set, a structured what-if sweep, and a robustness check of the prize
weight on deterrence. Everything is arithmetic on existing outputs plus a few cheap recomputations.

Evidence labels: costs are PROXIED/ASSUMED (docs/assumptions.md); response numbers are SIMULATED
under ASSUMED behavior; shares of statewide volume are SOURCED (OCE files). Nothing here is
evidence that deterrence exists.
"""

from __future__ import annotations

import copy
from math import ceil

import numpy as np
import pandas as pd

from tobacco_inspect.eval import census as C
from tobacco_inspect.model import prize

WORKDAYS_PER_MONTH = 21


def _row(front: pd.DataFrame, policy: str, checks: int) -> pd.Series:
    sub = front[(front["policy"] == policy) & (front["checks"] == checks)]
    if sub.empty:
        raise KeyError(f"frontier has no {policy!r} row at {checks} checks")
    return sub.iloc[0]


# --------------------------------------------------------------------------- marginal cost
def marginal_cost_table(
    front: pd.DataFrame, params: C.CostParams, current_checks: int, N: int, second_pass: int
) -> pd.DataFrame:
    """Incremental bottom-up cost of each census variant over today's capped program.

    Rows are compared with `targeted` at `current_checks` (today's ~44 city checks a year, priced
    without commissioning because the contract is running). Top-down columns are the full-cost
    sensitivity (DOH award per check x incremental checks).
    """
    base = _row(front, "targeted", current_checks)
    rows = []
    for label, policy, n in (
        ("census floor", "census_floor", N),
        (
            "census floor + adaptive second pass",
            "census_floor+adaptive_second_pass",
            N + second_pass,
        ),
    ):
        r = _row(front, policy, n)
        d_checks = int(r["checks"] - base["checks"])
        d_dollars = float(r["cost_bottom_up"] - base["cost_bottom_up"])
        d_viol = float(r["distinct_violators"] - base["distinct_violators"])
        rows.append(
            {
                "option": label,
                "checks": int(r["checks"]),
                "bottom_up_dollars": round(float(r["cost_bottom_up"])),
                "incremental_checks": d_checks,
                "incremental_dollars": round(d_dollars),
                "dollars_per_incremental_check": round(d_dollars / d_checks, 1),
                "incremental_distinct_violators": round(d_viol, 1),
                "dollars_per_incremental_violator": round(d_dollars / d_viol),
                "topdown_low_incremental": round(params.topdown_per_check["low"] * d_checks),
                "topdown_high_incremental": round(params.topdown_per_check["high"] * d_checks),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- break-even
def break_even_table(
    grid: pd.DataFrame, cap_cost: float, cen_cost: float, baseline_events: float
) -> pd.DataFrame:
    """What the census's incremental dollars must buy, per assumed deterrence response.

    `grid` is `regime_response_grid` (reductions are fractions of violation exposure). No dollar
    value of a prevented sale is asserted: the table gives the *price* of each prevented unit so a
    reader can compare it with their own valuation.

    * `required_points`: percentage points of exposure the incremental dollars must remove to
      match the capped plan's average efficiency (its points per dollar x incremental dollars).
    * `achieved_points`: the census's extra reduction over the capped plan.
    * `dollars_per_point` / `dollars_per_prevented_violation`: incremental dollars per point of
      exposure removed, and per violation-equivalent (reduction x `baseline_events`, the expected
      violations in one full pass of checks).
    """
    d_dollars = cen_cost - cap_cost
    rows = []
    for _, g in grid.iterrows():
        capped_per_dollar = 100 * g["capped_reduction"] / cap_cost
        required = capped_per_dollar * d_dollars
        achieved = 100 * (g["census_reduction"] - g["capped_reduction"])
        prevented = (g["census_reduction"] - g["capped_reduction"]) * baseline_events
        rows.append(
            {
                "response": g["response"],
                "incremental_dollars": round(d_dollars),
                "capped_reduction_pct": round(100 * g["capped_reduction"], 2),
                "census_reduction_pct": round(100 * g["census_reduction"], 2),
                "required_points": round(required, 2),
                "achieved_points": round(achieved, 2),
                "achieved_over_required": round(achieved / required, 2)
                if required > 1e-9
                else np.nan,
                "dollars_per_point": round(d_dollars / achieved) if achieved > 1e-9 else np.nan,
                "dollars_per_prevented_violation": round(d_dollars / prevented)
                if prevented > 1e-9
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- opportunity cost
def opportunity_cost_table(
    params: C.CostParams,
    census_checks: int,
    incremental_dollars: float,
    incremental_checks: int,
    city_checks_year: int,
    pa_checks_year: int,
    award: float,
) -> pd.DataFrame:
    """The funder's comparison set: what the same checks and dollars are worth elsewhere."""
    lo, hi = params.topdown_per_check["low"], params.topdown_per_check["high"]
    rows = [
        (
            "Pittsburgh share of PA published checks today",
            city_checks_year / pa_checks_year,
            "share",
            "SOURCED/PROXIED",
        ),
        (
            "Census floor as a share of PA published checks",
            census_checks / pa_checks_year,
            "share",
            "SOURCED/PROXIED",
        ),
        ("Census floor / today's city volume", census_checks / city_checks_year, "x", "PROXIED"),
        (
            "Incremental marginal dollars as share of annual award",
            incremental_dollars / award,
            "share",
            "PROXIED",
        ),
        (
            "Incremental marginal dollars per added check",
            incremental_dollars / incremental_checks,
            "$",
            "ASSUMED",
        ),
        ("DOH award per published check (low)", lo, "$", "PROXIED"),
        ("DOH award per published check (high)", hi, "$", "PROXIED"),
        (
            "Checks the same incremental dollars buy statewide at the high award rate",
            incremental_dollars / hi,
            "checks",
            "PROXIED",
        ),
        (
            "Checks the same incremental dollars buy statewide at the low award rate",
            incremental_dollars / lo,
            "checks",
            "PROXIED",
        ),
    ]
    return pd.DataFrame(rows, columns=["measure", "value", "unit", "label"])


# --------------------------------------------------------------------------- what-if
def whatif_census(
    travel, params: C.CostParams, day_hours=(4, 8), teams=(1, 2, 3, 4, 8)
) -> pd.DataFrame:
    """What if we change the number of teams or the length of the field day? (census floor)"""
    rows = []
    for hours in day_hours:
        day = hours * 60.0
        routes, t, svc = C.build_routes(travel, params, day, "base")
        dollars = float(C.bottom_up_cost(routes, t, svc, params, "base")["dollars"].sum())
        for k in teams:
            days = ceil(len(routes) / k)
            rows.append(
                {
                    "day_hours": hours,
                    "teams": k,
                    "team_days": len(routes),
                    "calendar_workdays": days,
                    "calendar_months": round(days / WORKDAYS_PER_MONTH, 1),
                    "bottom_up_dollars": round(dollars),
                }
            )
    return pd.DataFrame(rows)


def whatif_capped(
    schedule_summary: pd.DataFrame, day_hours=(4, 8), teams=(1, 2, 3)
) -> pd.DataFrame:
    """Does a third team or a shorter day change the capped plan? (monthly route minutes vs day)"""
    longest = float(schedule_summary["route_minutes"].max())
    rows = []
    for hours in day_hours:
        for k in teams:
            rows.append(
                {
                    "day_hours": hours,
                    "teams": k,
                    "longest_cycle_route_minutes": round(longest, 1),
                    "route_fits_in_one_day": longest <= hours * 60,
                    "binding_constraint": "budget (stores per cycle)"
                    if longest <= hours * 60
                    else "time (needs a second route)",
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- robustness
def lambda_robustness(config, cand: pd.DataFrame, lambdas, budget: int) -> pd.DataFrame:
    """Does the deterrence term (and its double counting of prior violations) drive the list?

    Recomputes the deterministic prize at each lambda (no Thompson noise) and compares the top
    `budget` stores with the baseline lambda: overlap, tract spread and mean h and p.
    """
    base_lam = float(config.prize["lambda_deterrence"])
    h, p, det = cand["h"].to_numpy(), cand["p"].to_numpy(), cand["deterrence"].to_numpy()

    def top(lam: float) -> np.ndarray:
        cfg = copy.deepcopy(config)
        cfg.prize["lambda_deterrence"] = lam
        return np.argsort(-prize.compute_prizes(cfg, h, p, det))[:budget]

    base_top = set(top(base_lam))
    rows = []
    for lam in lambdas:
        sel = top(lam)
        rows.append(
            {
                "lambda_deterrence": lam,
                "is_baseline": bool(np.isclose(lam, base_lam)),
                "top_n": budget,
                "overlap_with_baseline": len(base_top & set(sel)),
                "distinct_tracts": int(cand.iloc[sel]["tract_geoid"].nunique()),
                "mean_p": round(float(p[sel].mean()), 3),
                "mean_h": round(float(h[sel].mean()), 3),
            }
        )
    return pd.DataFrame(rows)
