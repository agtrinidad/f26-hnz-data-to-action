"""Two implementations of one compliance regime: budget-capped vs census floor.

Both implementations score stores with the same risk model and spend checks need-first. They
differ in the constraint: *budget-capped* spends a fixed small number of checks (about 4 a month)
and picks the highest-need stores; *census floor* guarantees every store one check a year (random
dates), then spends a second-pass budget by need, updated with what the first pass found.

This module adds only what `eval/census.py` (cost, exact capture, calendars) and `eval/simulate.py`
(response model) do not cover:

1. `Truth`: the model's p is not the truth. The truth is a compressed (overconfident-model) and
   optionally noisier (hidden store-level heterogeneity) version of p, calibrated so the model's
   top-decile lift equals the observed replay lift. The census memo's targeted line assumed the
   model's own p was the truth (optimistic); this is the principled discount. How much hidden
   heterogeneity exists is not identified by today's data; first-pass labels would identify it.
2. `frontier`: cost and expected outcomes along a budget path from today's volume to the census
   and beyond (the marginal-cost curve `capture_table` only sampled at five budget fractions).
3. `adaptive_second_pass`: what first-pass labels are worth when choosing the second pass.
4. `year_sim`: a 12-month simulation of both regimes under one response model
   (`simulate.effective_p`), measuring *violation exposure* (what deterrence lowers), not only
   detections (which fall when deterrence works).
5. `equity_compare`: the tract audit, run on both regimes.

Everything is SIMULATED with ASSUMED behavior (delta, memory, rho, gamma); none of it is evidence
that deterrence exists. See docs/process/06_Regime_Comparison.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import expit, logit

from tobacco_inspect.eval import census as C
from tobacco_inspect.eval import equity, simulate
from tobacco_inspect.model import thompson

SECOND_PASS_POLICIES = (
    "random",
    "static_model",
    "violators_first",
    "posterior_mean",
    "thompson_posterior",
)


# --------------------------------------------------------------------------- truth with model error
@dataclass(frozen=True)
class Truth:
    """How the true violation probability q relates to the model's p (all ASSUMED shapes).

    logit q = centre + slope * (logit p - centre) + sigma * N(0, 1), then shifted so mean(q) =
    mean(p) (the Synar-calibrated city rate). `slope < 1` means the model is overconfident (true
    risk is less spread out than predicted); `sigma > 0` is hidden store-level heterogeneity the
    model cannot see. slope = 1, sigma = 0 is the optimistic "the model is the truth" case.
    """

    sigma: float = 0.0
    slope: float = 1.0

    def draws(self, p, n_draws: int, rng: np.random.Generator) -> np.ndarray:
        p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
        if self.sigma <= 0 and self.slope == 1.0:
            return np.tile(p, (n_draws, 1))
        lg = logit(p)
        centre = lg.mean()
        noise = self.sigma * rng.standard_normal((n_draws, len(p)))
        lg = centre + self.slope * (lg - centre) + noise
        lo, hi = np.full(n_draws, -6.0), np.full(n_draws, 6.0)
        for _ in range(40):
            mid = (lo + hi) / 2
            below = expit(lg + mid[:, None]).mean(axis=1) < p.mean()
            lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
        return expit(lg + ((lo + hi) / 2)[:, None])

    @classmethod
    def calibrated(
        cls, p, target_lift: float, sigma: float = 0.0, top_share: float = 0.1, seed: int = 867
    ) -> Truth:
        """Truth with hidden heterogeneity `sigma` whose slope makes the model's top-decile lift
        equal `target_lift` (the observed replay lift). Lift rises with slope, so bisection."""
        if realized_lift(p, cls(sigma, 1.0), top_share, 300, seed) <= target_lift:
            return cls(sigma, 1.0)  # even an unattenuated model is no better than observed
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if realized_lift(p, cls(sigma, mid), top_share, 300, seed) > target_lift:
                hi = mid
            else:
                lo = mid
        return cls(sigma, float((lo + hi) / 2))


def realized_lift(p, truth: Truth, top_share: float = 0.1, n_draws: int = 300, seed: int = 867):
    """Mean true rate among the model's top `top_share` stores, over the mean true rate."""
    p = np.asarray(p, dtype=float)
    q = truth.draws(p, n_draws, np.random.default_rng(seed))
    top = np.argsort(-p)[: max(1, int(round(top_share * len(p))))]
    return float((q[:, top].mean(axis=1) / q.mean(axis=1)).mean())


def max_hidden_sigma(p, target_lift: float, top_share: float = 0.1, seed: int = 867) -> float:
    """Largest hidden heterogeneity consistent with the observed lift (slope 1: no attenuation).

    Beyond this the model's ranking would be weaker than observed, so it bounds the sweep.
    """
    if realized_lift(p, Truth(0.0, 1.0), top_share, 2, seed) <= target_lift:
        return 0.0
    lo, hi = 0.0, 4.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if realized_lift(p, Truth(mid, 1.0), top_share, 300, seed) > target_lift:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2)


# --------------------------------------------------------------------------- second pass
def adaptive_second_pass(
    p, E: int, kappa: float, truth: Truth, n_sims: int, rng: np.random.Generator
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Value of first-pass labels when choosing `E` second-pass checks (SIMULATED).

    Stage 1 checks every store once (y1 ~ Bernoulli(q_i), q drawn from `truth`). Each store's
    Beta posterior (prior mean p_i, strength kappa) is updated with y1 via `thompson.update`.
    Stage 2 picks E stores by one of `SECOND_PASS_POLICIES`:

    - random: uniform, ignoring everything.
    - static_model: top E by the model's p (labels ignored).
    - violators_first: FDA's follow-up rule, re-check stage-1 violators, fill by model p.
    - posterior_mean / thompson_posterior: rank by the updated posterior mean / a posterior draw
      (the latter keeps the selection unpredictable).

    Returns (summary, one representative selection per policy, for costing). `repeat_events` are
    stores that violated in both passes, which is what triggers FDA's escalating penalties.
    """
    p = np.asarray(p, dtype=float)
    N = len(p)
    q_all = truth.draws(p, n_sims, rng)
    alpha, beta = thompson.beta_prior_from_p(p, kappa)
    static = np.argsort(-p)
    cols = {k: {"events2": [], "repeat": [], "new": []} for k in SECOND_PASS_POLICIES}
    stage1, example = [], {}
    for s in range(n_sims):
        q = q_all[s]
        y1 = rng.random(N) < q
        y2 = rng.random(N) < q
        a, b = thompson.update(alpha, beta, 1, y1.astype(int))
        viol = np.where(y1)[0]
        viol = viol[np.argsort(-p[viol])]
        fill = static[~np.isin(static, viol)]
        sels = {
            "random": rng.choice(N, size=E, replace=False),
            "static_model": static[:E],
            "violators_first": np.concatenate([viol, fill])[:E],
            "posterior_mean": np.argsort(-(a / (a + b)))[:E],
            "thompson_posterior": np.argsort(-thompson.sample_violation_rates(a, b, rng))[:E],
        }
        stage1.append(y1.sum())
        for name, sel in sels.items():
            cols[name]["events2"].append(y2[sel].sum())
            cols[name]["repeat"].append((y1 & y2)[sel].sum())
            cols[name]["new"].append((y2 & ~y1)[sel].sum())
            example.setdefault(name, sel)
    base = np.array(cols["random"]["events2"], dtype=float)
    rows = []
    for name in SECOND_PASS_POLICIES:
        ev = np.array(cols[name]["events2"], dtype=float)
        diff = ev - base
        rows.append(
            {
                "policy": name,
                "second_pass_checks": E,
                "stage1_events": float(np.mean(stage1)),
                "second_pass_events": float(ev.mean()),
                "repeat_events": float(np.mean(cols[name]["repeat"])),
                "new_distinct": float(np.mean(cols[name]["new"])),
                "distinct_two_pass": float(np.mean(stage1) + np.mean(cols[name]["new"])),
                "gain_vs_random": float(diff.mean()),
                "gain_se": float(diff.std(ddof=1) / np.sqrt(n_sims)) if n_sims > 1 else np.nan,
            }
        )
    return pd.DataFrame(rows), example


# --------------------------------------------------------------------------- frontier
def _cost(travel, params, day_minutes, scenario, idx, one_time: bool = True):
    """Bottom-up dollars and team-days to check the stores `idx` (indices into p)."""
    nodes = [int(i) + 1 for i in idx]
    routes, t, svc = C.build_routes(travel, params, day_minutes, scenario, nodes=nodes)
    total = float(C.bottom_up_cost(routes, t, svc, params, scenario)["dollars"].sum())
    if not one_time:  # a second pass reuses the trained team: drop commissioning and its overhead
        total -= params.pick("training_fixed", scenario) * (
            1 + params.pick("overhead_share", scenario)
        )
    return total, len(routes)


def frontier(
    p,
    travel,
    params: C.CostParams,
    day_minutes: float,
    budgets,
    truth: Truth,
    kappa: float,
    second_pass_fracs=(0.1, 0.25, 0.5),
    n_truth: int = 300,
    n_sims: int = 200,
    seed: int = 867,
    scenario: str = "base",
    charge_commissioning_to_capped: bool = False,
) -> pd.DataFrame:
    """Expected outcome and cost of each policy along a budget path (checks in the year).

    Policies for n <= N: `random` (simple random, no repeats), `targeted_model_p` (top n by p, if
    the model were truth: optimistic), `targeted` (top n by p against noisy truth, calibrated to
    the observed lift). At n = N: `census_floor`. Beyond N: census floor plus a second pass chosen
    `adaptive` (Thompson posterior) or `random`.

    Cost is bottom-up from the real routes of the selected stores, so a scattered targeted list
    costs more per check than the census. `se_rate` is the standard error of the city violation
    rate (not estimable from a targeted list). Budget-capped rows (n < N) are today's contracted
    program, so by default they carry no one-time commissioning cost (the census does; set
    `charge_commissioning_to_capped` to charge both). Evidence: the identities are exact, the
    levels are simulated, and the cost inputs are assumed (docs/assumptions.md).
    """
    p = np.asarray(p, dtype=float)
    N = len(p)
    rng = np.random.default_rng(seed)
    q = truth.draws(p, n_truth, rng)
    order = np.argsort(-p)
    top_decile = max(1, N // 10)
    td_lo, td_hi = params.topdown_per_check["low"], params.topdown_per_check["high"]
    rows = []

    def add(policy, n, distinct, events, cov, top_cov, se, idx, cost_override=None):
        cost, days = cost_override or _cost(
            travel,
            params,
            day_minutes,
            scenario,
            idx,
            one_time=charge_commissioning_to_capped or n >= N,
        )
        rows.append(
            {
                "policy": policy,
                "checks": int(n),
                "distinct_violators": float(distinct),
                "events": float(events),
                "coverage_stores": float(cov),
                "coverage_top_decile": float(top_cov),
                "se_rate": se,
                "team_days": days,
                "cost_bottom_up": float(cost),
                "cost_per_check": float(cost) / max(int(n), 1),
                "cost_topdown_low": td_lo * n,
                "cost_topdown_high": td_hi * n,
            }
        )

    for n in sorted(int(b) for b in budgets if b < N):
        add(
            "random",
            n,
            C.distinct_srs(p, n),
            C.expected_detected(p, n),
            n / N,
            n / N,
            C.se_rate_sample(p, n),
            rng.choice(N, size=n, replace=False),
        )
        add(
            "targeted_model_p",
            n,
            C.distinct_targeted(p, n),
            C.distinct_targeted(p, n),
            n / N,
            min(1.0, n / top_decile),
            np.nan,
            order[:n],
        )
        real = float(q[:, order[:n]].sum(axis=1).mean())
        add("targeted", n, real, real, n / N, min(1.0, n / top_decile), np.nan, order[:n])
    census_total = float(p.sum())
    add(
        "census_floor",
        N,
        census_total,
        census_total,
        1.0,
        1.0,
        C.se_rate_census(p),
        np.arange(N),
    )
    for frac in second_pass_fracs:
        E = int(round(frac * N))
        summary, example = adaptive_second_pass(p, E, kappa, truth, n_sims, rng)
        for label, name in (("adaptive", "thompson_posterior"), ("random", "random")):
            r = summary.set_index("policy").loc[name]
            second = _cost(travel, params, day_minutes, scenario, example[name], one_time=False)
            first = _cost(travel, params, day_minutes, scenario, np.arange(N))
            add(
                f"census_floor+{label}_second_pass",
                N + E,
                r["distinct_two_pass"],
                r["stage1_events"] + r["second_pass_events"],
                1.0,
                1.0,
                C.se_rate_census(p),
                None,
                cost_override=(first[0] + second[0], first[1] + second[1]),
            )
    return pd.DataFrame(rows)


def marginal(front: pd.DataFrame, policy: str) -> pd.DataFrame:
    """Added bottom-up dollars and checks per added distinct violator between budget steps."""
    f = front[front["policy"] == policy].sort_values("checks").reset_index(drop=True)
    out = f[["policy", "checks", "distinct_violators", "cost_bottom_up"]].copy()
    d = out[["checks", "distinct_violators", "cost_bottom_up"]].diff()
    out["checks_per_added_violator"] = d["checks"] / d["distinct_violators"]
    out["dollars_per_added_violator"] = d["cost_bottom_up"] / d["distinct_violators"]
    return out


# --------------------------------------------------------------------------- year simulation
def year_sim(
    p,
    regime: str,
    response: dict,
    truth: Truth,
    kappa: float,
    n_sims: int = 100,
    seed: int = 867,
    budget_per_cycle: int = 4,
    random_share: float = 0.2,
    floor_months: int = 9,
    second_pass_share: float = 0.25,
    second_pass: str = "thompson",
    order: str = "random",
    h=None,
) -> dict:
    """Simulate 12 monthly cycles of one regime against `truth` and an assumed response.

    regime `capped`: `budget_per_cycle` checks a month; (1 - random_share) by Thompson draw around
    the model's p (times `h` when given), the rest uniformly at random; each store at most once.
    regime `census_floor`: every store once over the first `floor_months` months (`order`: random,
    or risk_first = need decides *when*), then `second_pass_share` * N checks over the remaining
    months chosen by `second_pass` (thompson | posterior_mean | static | random) from the
    first-pass outcomes.

    `response` holds delta, memory, rho, window, gamma, gamma_power for `simulate.effective_p`
    (ASSUMED). Store
    outcomes use p_eff, so deterrence lowers detections too; the headline is `reduction`, the drop
    in the mean violation probability across all stores vs no enforcement (what the public sees),
    and `reduction_h` weights stores by `h` (exposure of minors). Returns means over sims.
    """
    if regime not in {"capped", "census_floor"}:
        raise ValueError(regime)
    p = np.asarray(p, dtype=float)
    N = len(p)
    w = np.ones(N) if h is None else np.asarray(h, dtype=float)
    rng = np.random.default_rng(seed)
    Q = truth.draws(p, n_sims, rng)
    alpha, beta = thompson.beta_prior_from_p(p, kappa)
    n2 = int(round(second_pass_share * N))
    out = {k: [] for k in ("checks", "detections", "distinct", "repeats", "red", "red_h")}
    counts = np.zeros(N)
    exposure_month = np.zeros(12)
    for s in range(n_sims):
        q = Q[s]
        history: list[np.ndarray] = []
        det = np.zeros(N)
        n_chk = np.zeros(N)
        exp_t = np.zeros(12)
        exp_h = np.zeros(12)
        if regime == "census_floor":
            key = p * w
            base_order = rng.permutation(N) if order == "random" else np.argsort(-key)
            stage1 = np.array_split(base_order, floor_months)
        for c in range(12):
            if regime == "capped":
                done = np.concatenate(history) if history else np.array([], dtype=int)
                eligible = np.setdiff1d(np.arange(N), done)
                rand = thompson.random_share_pick(budget_per_cycle, random_share, eligible, rng)
                score = w * thompson.sample_violation_rates(alpha, beta, rng)
                rest = np.setdiff1d(eligible, rand)
                sel = np.concatenate(
                    [rand, rest[np.argsort(-score[rest])][: budget_per_cycle - len(rand)]]
                )
            elif c < floor_months:
                sel = stage1[c]
            else:
                if c == floor_months:
                    a, b = thompson.update(alpha, beta, n_chk, det)
                    if second_pass == "thompson":
                        pick = np.argsort(-w * thompson.sample_violation_rates(a, b, rng))[:n2]
                    elif second_pass == "posterior_mean":
                        pick = np.argsort(-w * a / (a + b))[:n2]
                    elif second_pass == "static":
                        pick = np.argsort(-w * p)[:n2]
                    elif second_pass == "random":
                        pick = rng.choice(N, size=n2, replace=False)
                    else:
                        raise ValueError(second_pass)
                    chunks = np.array_split(pick, 12 - floor_months)
                sel = chunks[c - floor_months]
            p_eff = simulate.effective_p(q, history, **response)
            hit = rng.random(len(sel)) < p_eff[sel]
            det[sel[hit]] += 1
            n_chk[sel] += 1
            exp_t[c] = p_eff.mean()
            exp_h[c] = (w * p_eff).sum()
            history.append(np.asarray(sel, dtype=int))
        out["checks"].append(n_chk.sum())
        out["detections"].append(det.sum())
        out["distinct"].append((det > 0).sum())
        out["repeats"].append((det >= 2).sum())
        out["red"].append(1 - exp_t.mean() / q.mean())
        out["red_h"].append(1 - exp_h.mean() / (w * q).sum())
        counts += n_chk / n_sims
        exposure_month += exp_t / q.mean() / n_sims
    return {
        "regime": regime,
        "checks": float(np.mean(out["checks"])),
        "detections": float(np.mean(out["detections"])),
        "distinct_detected": float(np.mean(out["distinct"])),
        "repeat_violators": float(np.mean(out["repeats"])),
        "reduction": float(np.mean(out["red"])),
        "reduction_se": float(np.std(out["red"], ddof=1) / np.sqrt(n_sims)),
        "reduction_h": float(np.mean(out["red_h"])),
        "counts": counts,
        "exposure_by_month": exposure_month,
    }


def crossing(x, f) -> float:
    """First x where f changes sign (linear interpolation), or nan if it never does."""
    x, f = np.asarray(x, dtype=float), np.asarray(f, dtype=float)
    for i in range(len(f) - 1):
        if f[i] == 0:
            return float(x[i])
        if f[i] * f[i + 1] < 0:
            return float(x[i] - f[i] * (x[i + 1] - x[i]) / (f[i + 1] - f[i]))
    return float(x[-1]) if f[-1] == 0 else float("nan")


# --------------------------------------------------------------------------- equity
def equity_compare(cand: pd.DataFrame, universe: pd.DataFrame, counts: dict) -> pd.DataFrame:
    """Tract audit (`eval/equity.py`) for each regime's expected checks per store.

    `counts` maps regime name to an array of expected checks per store, aligned to `cand`.
    """
    acs_cols = [
        c for c in ("acs_poverty_rate", "acs_youth_share", "acs_minority_share") if c in universe
    ]
    uni = cand[["license_id", "tract_geoid"]].merge(
        universe[["license_id", *acs_cols]], on="license_id", how="left"
    )
    rows = []
    for name, c in counts.items():
        series = pd.Series(np.asarray(c, dtype=float), index=uni.index)
        cov = equity.coverage_by_tract(uni, series)
        row = {"regime": name, "expected_checks": float(series.sum())}
        row.update(equity.equity_summary(cov))
        # a store is checked at most once per pass, so expected checks c < 1 means P(never) = 1 - c
        row["share_stores_never_checked"] = float(np.clip(1 - series.to_numpy(), 0, 1).mean())
        rows.append(row)
    return pd.DataFrame(rows)
