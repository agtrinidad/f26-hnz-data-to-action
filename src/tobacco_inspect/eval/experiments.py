"""Reusable experiments behind the implementation notebook (Gate B, policy simulation, power).

All functions take small, explicit parameters so the notebook can run a quick version and the
saved full results (outputs/*.csv) can be loaded for the written results.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from scipy.stats import norm

from tobacco_inspect import pipeline
from tobacco_inspect.eval import baselines, simulate
from tobacco_inspect.model import prize, thompson


# --------------------------------------------------------------------------- Gate B
def gate_b_sweep(
    config,
    inst,
    budgets=(4, 8, 15, 25),
    route_counts=(1, 2),
    day_minutes=(480, 240, 120),
    pool: int = 40,
    time_limit: float | None = None,
) -> pd.DataFrame:
    """Compare the team MILP with ranked+batched across budgets, route slots and day lengths.

    Random share is switched off (all stores compete on prize) and Thompson noise is the same
    for both planners (same draw), so any gap comes from routing alone.
    """
    scfg = config.raw["solve"]
    old_limit, old_share = scfg["time_limit_s"], config.coverage["random_share"]
    if time_limit:
        scfg["time_limit_s"] = time_limit
    config.coverage["random_share"] = 0.0
    rows = []
    try:
        for budget in budgets:
            for n_routes in route_counts:
                for day in day_minutes:
                    t0 = time.time()
                    res = pipeline.plan_cycle(
                        inst,
                        config,
                        np.random.default_rng(1),
                        set(),
                        budget=budget,
                        day_minutes=day,
                        n_routes=n_routes,
                        pool=pool,
                    )
                    m, h = res["plan"], res["heuristic"]
                    rows.append(
                        {
                            "budget": budget,
                            "n_routes": n_routes,
                            "day_minutes": day,
                            "milp_stores": len(m.visited),
                            "milp_prize": round(m.prize, 3),
                            "heuristic_stores": len(h.visited),
                            "heuristic_prize": round(h.prize, 3),
                            "gain_pct": round(100 * (m.prize / h.prize - 1), 1)
                            if h.prize
                            else np.nan,
                            "milp_minutes": round(sum(m.times)),
                            "heuristic_minutes": round(sum(h.times)),
                            "solver": m.solver,
                            "status": m.status,
                            "seconds": round(time.time() - t0, 1),
                        }
                    )
    finally:
        scfg["time_limit_s"], config.coverage["random_share"] = old_limit, old_share
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- policy simulation
POLICIES = (
    "random",
    "status_quo_followup",
    "prior_violators_first",
    "risk_only_topB_fixed",
    "prize_topB_fixed",
    "prize_topB_at_most_once",
    "thompson_prize",
    "thompson_prize+random",
    "thompson_prize+random_at_most_once",
)


def _policy(name: str, cand: pd.DataFrame, config, B: int, seed: int, kappa: float):
    rng = np.random.default_rng(seed)
    n, p = len(cand), cand["p"].to_numpy()
    h, det = cand["h"].to_numpy(), cand["deterrence"].to_numpy()
    r_det = prize.compute_prizes(config, h, p, det)
    a, b = thompson.beta_prior_from_p(p, kappa)
    quota = max(1, round(config.coverage["random_share"] * B))

    def seen(hist):
        return {i for x in hist for i in x}

    def thompson_pick(hist, share, at_most_once):
        r = prize.compute_prizes(config, h, thompson.sample_violation_rates(a, b, rng), det)
        if at_most_once:
            r = np.where(np.isin(np.arange(n), list(seen(hist))), -1.0, r)
        k = quota if share else 0
        rnd = rng.choice(n, k, replace=False) if k else np.array([], dtype=int)
        rest = [i for i in np.argsort(-r) if i not in set(rnd)][: B - k]
        return np.array(list(rnd) + rest)

    def f(c, hist):
        if name == "random":
            return rng.choice(n, B, replace=False)
        if name == "status_quo_followup":
            return baselines.status_quo_followup(cand, B, rng)
        if name == "prior_violators_first":
            return baselines.prior_violators_first(cand, B, rng)
        if name == "risk_only_topB_fixed":
            return np.argsort(-p)[:B]
        if name == "prize_topB_fixed":
            return np.argsort(-r_det)[:B]
        if name == "prize_topB_at_most_once":
            done = seen(hist)
            return np.array([i for i in np.argsort(-r_det) if i not in done][:B])
        if name == "thompson_prize":
            return thompson_pick(hist, False, False)
        if name == "thompson_prize+random":
            return thompson_pick(hist, True, False)
        if name == "thompson_prize+random_at_most_once":
            return thompson_pick(hist, True, True)
        raise ValueError(name)

    return f


def policy_simulation(
    config,
    cand: pd.DataFrame,
    scenarios=((0.0, 0.0), (0.25, 0.0), (0.0, 0.5), (0.0, 0.9), (0.25, 0.5)),
    policies=POLICIES,
    n_sims: int = 100,
    cycles: int = 36,
    kappa: float | None = None,
) -> pd.DataFrame:
    """Violations found per monthly cycle by policy under assumed (delta, rho) behavior.

    SIMULATED: truth = the model's own population-calibrated p_i, so results show policy logic
    given a correct model, not evidence that the model is right.
    """
    B = config.capacity.cycle_budget
    kappa = kappa or config.raw["risk"]["kappa"]
    p = cand["p"].to_numpy()
    rows = []
    for delta, rho in scenarios:
        for name in policies:
            totals, distinct = [], []
            for s in range(n_sims):
                res = simulate.run(
                    _policy(name, cand, config, B, 1000 + s, kappa),
                    p,
                    B,
                    cycles,
                    np.random.default_rng(s),
                    delta=delta,
                    rho=rho,
                )
                totals.append(res["total"])
                distinct.append(len({i for x in res["history"] for i in x}))
            rows.append(
                {
                    "delta": delta,
                    "rho": rho,
                    "policy": name,
                    "found_per_cycle": np.mean(totals) / cycles,
                    "lo": np.percentile(totals, 2.5) / cycles,
                    "hi": np.percentile(totals, 97.5) / cycles,
                    "distinct_stores": np.mean(distinct),
                }
            )
    return pd.DataFrame(rows)


def kappa_sensitivity(config, cand, kappas=(2, 5, 10, 20, 100), n_sims=60, cycles=36):
    """Thompson prior strength vs yield and coverage under mixed behavioral assumptions."""
    rows = []
    for kappa in kappas:
        out = policy_simulation(
            config,
            cand,
            scenarios=((0.0, 0.0), (0.25, 0.5)),
            policies=("thompson_prize+random", "thompson_prize+random_at_most_once"),
            n_sims=n_sims,
            cycles=cycles,
            kappa=kappa,
        )
        rows.append(out.assign(kappa=kappa))
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- power (Gate C)
def n_for_ci_halfwidth(p: float, halfwidth: float, conf: float = 0.95) -> int:
    """Sample size for a proportion estimate within +/- halfwidth."""
    z = norm.ppf(0.5 + conf / 2)
    return int(np.ceil(p * (1 - p) * (z / halfwidth) ** 2))


def n_per_arm_two_proportions(p1: float, p2: float, alpha=0.05, power=0.8) -> int:
    """Per-arm n to detect p1 vs p2 (two-sided z test)."""
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    return int(np.ceil((za + zb) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p1 - p2) ** 2))


def power_table(
    base_rate: float, checks_per_year: float, shares=(0.2, 0.3, 0.4, 1.0)
) -> pd.DataFrame:
    """Years of random-arm data needed (a) to estimate the base rate within +/-10 points and
    (b) to detect a 1.5x targeting lift at 80% power, for several random shares."""
    n_est = n_for_ci_halfwidth(base_rate, 0.10)
    n_lift = n_per_arm_two_proportions(min(base_rate * 1.5, 0.95), base_rate)
    rows = []
    for share in shares:
        per_year = checks_per_year * share
        rows.append(
            {
                "random_share": share,
                "random_checks_per_year": round(per_year, 1),
                "n_to_estimate_rate_pm10pts": n_est,
                "years_to_estimate": round(n_est / per_year, 1),
                "n_per_arm_to_detect_1.5x_lift": n_lift,
                "years_to_detect_lift": round(n_lift / per_year, 1),
            }
        )
    return pd.DataFrame(rows)
