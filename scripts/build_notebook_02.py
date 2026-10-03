"""Generate notebooks/02_risk_and_schedule.ipynb.

Proposal passages are read from docs/sources/proposed_alternative.md and inserted verbatim as
blockquote cells tagged `proposal-quote`; tests/test_notebook.py checks they still match.
Run: uv run python scripts/build_notebook_02.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

from _nb import cells, code, md

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "sources" / "proposed_alternative.md"
OUT = ROOT / "notebooks" / "02_risk_and_schedule.ipynb"

paras = [p.strip() for p in SRC.read_text(encoding="utf-8").split("\n") if p.strip()]
HEADING, P1, P2, P3, P4 = paras  # heading + four paragraphs


def quote(paragraph: str, label: str):
    md(f"**{label}** (quoted from the Proposed Alternative)\n\n> {paragraph}", ["proposal-quote"])


# --------------------------------------------------------------------------- title
md(
    """
# 02 · Risk model, prizes and the monthly schedule

**Project:** Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA
**Purpose:** implement the Proposed Alternative end to end on the data prepared in notebook 01 and
`docs/process/02_Data_Acquisition_Memo.md`, test whether it beats the comparators, and say plainly
where current information makes a piece infeasible or meaningless.

Every quoted passage below is the team's Proposed Alternative, unchanged; the "Implementation"
notes underneath are this notebook's own text.

**Evidence labels used on every result**
- *observed-sample*: computed from real FDA/Synar records, but only for stores that were inspected (selection bias);
- *simulated*: computed on a synthetic truth, so it shows what a policy does *if the model is right*;
- *assumed*: depends on a parameter no data identifies (deterrence strength, purchaser response, service time).

Reusable code lives in `src/tobacco_inspect/`; this notebook is the narrative. Set `FULL = True` below to rerun the
slow experiments (about 15 minutes); otherwise saved results in `outputs/` are loaded.
"""
)
code(
    """
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tobacco_inspect import pipeline
from tobacco_inspect.config import load_config
from tobacco_inspect.data import synar
from tobacco_inspect.eval import backtest, equity, experiments, metrics
from tobacco_inspect.model import history, risk

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.max_columns", 40, "display.width", 160)
cfg = load_config()
OUT = cfg.path("outputs")
FULL = False  # True reruns Gate B and the simulations (slow); False loads saved results if present
RNG = np.random.default_rng(cfg.seed)
"""
)

# --------------------------------------------------------------------------- 1 PCTSP
md("## 1. Problem framing: a budgeted prize-collecting tour")
quote(P1, "Proposal, paragraph 1")
md(
    """
**Implementation.** The prize is a risk score per store; the budget is the number of inspections and the
working day of each team. `solve_team_orienteering` (`model/orienteering.py`) is the budgeted PCTSP in team form: route slots
(team x day), at most one visit per store, a total budget B, a time limit per route, coverage floors.

**Reality check on scale.** The budget is small: the cell below derives it from the data. If the budget binds long before
the working day does, the "traveling" part of the problem has little to optimize. Section 5 measures when that changes.
"""
)
code(
    """
cap = cfg.capacity
fy = pd.read_csv(cfg.path("interim") / "oce_pa_by_fiscal_year.csv")
print(f"City-limits undercover checks per fiscal year (FDA OCE files):")
print(fy[["fy", "up_checks", "city_up_checks", "city_violations"]].tail(8).to_string(index=False))
stops_per_day = (cap.daily_budget_minutes - 30) / (cap.service_minutes + 10)  # rough: 20 min service + ~10 min drive
print(f"\\nHorizon {cap.horizon_weeks} weeks, {cap.cycles} monthly cycles, budget {cap.budget_inspections} per horizon "
      f"= {cap.cycle_budget} per cycle")
print(f"Team-days available per cycle: {cap.teams * cap.cycle_days}; one team-day fits about {stops_per_day:.0f} stops")
print(f"=> a cycle needs about {cap.cycle_budget / stops_per_day:.1f} team-days out of {cap.teams * cap.cycle_days}: the budget binds, not time.")
"""
)

# --------------------------------------------------------------------------- 2 risk
md("## 2. Targeted and untargeted firms: does prior noncompliance predict violations?")
quote(P2, "Proposal, paragraph 2")
md(
    """
**Implementation.**
- *Targeted vs untargeted* (`model/harrington.py`): a store is targeted when it has a violation in the last 24 months. The
  enforcement state follows FDA's real escalation schedule (violations in 12/24/36-month windows, HHS-OIG
  OEI-01-20-00240), not an invented state space. How strongly an inspection changes behavior (`prize.lambda_deterrence`)
  is **assumed**; no data identifies it.
- *Prior noncompliance and time since past inspection* (`model/history.py`): leakage-safe features computed only from records
  decided at least 30 days before the check. Decision date is the clock because inspection dates are missing for about 90% of records.
- *Risk score* (`model/risk.py`): L2 logistic regression trained on all Pennsylvania undercover checks (49k), then applied to Pittsburgh.
  Pittsburgh alone is too small to evaluate (174 city checks and 57 violations over the four test years, as few as 3 in one year).

**Gate A** asks whether this beats the comparators, replaying fiscal years 2022-2025 (train on earlier years, test on year t).
Replay can only score stores that were actually inspected, so its lift is *observed-sample*.
"""
)
code(
    """
fit = pipeline.fit(cfg, write=False)
model, bt, scores = fit["model"], fit["backtest"], fit["scores"]
print(f"Model: C={model.c}, trained on {model.n_train:,} checks with {model.positives:,} violations")
for subset in ["PA", "Pittsburgh city"]:
    for frac in (0.1, 0.2):
        tab = backtest.pooled_lift(bt, subset, frac)
        print(f"\\n{subset}, top {int(frac*100)}% of the ranking - mean over test years (observed-sample)")
        print(tab.round(3).to_string())
"""
)
code(
    """
# Lift at top 10% by test year, PA-wide, with bootstrap intervals
sub = bt[(bt.subset == "PA") & (bt.frac == 0.1)]
fig, ax = plt.subplots(figsize=(8, 3.8))
order = ["random", "status_quo_followup", "days_since_check", "prior_violators_first", "model"]
for k, name in enumerate(order):
    d = sub[sub.scorer == name].sort_values("fy")
    ax.errorbar(d.fy + (k - 2) * 0.08, d.lift, yerr=[(d.lift - d.lift_lo).clip(lower=0), (d.lift_hi - d.lift).clip(lower=0)],
                fmt="o-", capsize=2, label=name)
ax.axhline(1, color="grey", lw=0.8)
ax.set_xlabel("test fiscal year"); ax.set_ylabel("lift of top 10% vs pool average")
ax.set_title("Gate A (observed-sample): PA undercover checks, replay"); ax.legend(fontsize=8)
plt.tight_layout(); plt.show()
"""
)
md(
    """
**Reading Gate A.** At the PA level the model's ranking beats random with intervals clear of 1. The prior-violators-first
rule is about as good in the very top of the ranking; the model's edge is across the whole ranking (higher AUC), which
comes from combining outlet type (the largest coefficients) with the history and time-since-check terms. FDA's follow-up rule is the weakest informative
comparator. Pittsburgh-only replay is too thin to say anything (intervals span 0 to 3). *All observed-sample.*
"""
)
md(
    """
### Random-sample benchmark: Synar

The 2025 PA Synar report (a probability sample of cigarette retailers) is the only random baseline available. Two uses:
1. *Is the status quo already better than random?* Compare FDA's yearly undercover violation rate with Synar's confidence band.
2. *Prior-shift calibration:* the model is trained on an enriched sample, so its mean is rescaled to Synar's Allegheny
   rate (26.0%, 95% CI 17.3-34.7) to approximate P(violation | store exists).
Caveats: Synar is cigarettes only (OCE includes cigars and ENDS and follow-up checks); Synar's yearly bounds here are read
off a chart (approximate); Allegheny is one summer, n = 100.
"""
)
code(
    """
enrich = backtest.synar_enrichment(pd.read_csv(cfg.path("interim") / "oce_pa_by_fiscal_year.csv"))
print(enrich[["fy", "up_checks", "violation_rate", "synar_lower", "synar_upper", "ratio_to_synar",
              "above_synar_band", "below_synar_band"]].round(3).to_string(index=False))
al, lo, hi = synar.allegheny_rate()
print(f"\\nSynar Allegheny: {al:.1%} ({lo:.1%}-{hi:.1%}), n=100 completed")
city = fy[["fy", "city_up_checks", "city_violations", "city_violation_rate"]].tail(6)
print("\\nPittsburgh city FDA undercover rate by fiscal year (observed-sample):")
print(city.to_string(index=False))
r = scores[scores.retail_license]
print(f"\\nModel mean p: raw {r.p_raw.mean():.1%} -> calibrated {r.p.mean():.1%} (logit shift {fit['calibration_shift']:+.2f})")
"""
)
md(
    """
**Outlet-type check.** Synar Table 8 gives violation rates by outlet type (dollar stores 2.9%, supermarkets 6.6%, chain
convenience/gas 13.9%, tobacco shops 22.3%, independent convenience 23.7%). The model should order types the same way.
"""
)
code(
    """
frame = history.build_training_frame(pd.read_csv(cfg.path("processed") / "oce_pa_checks.csv.gz",
                                                 dtype={"Zip": str}, parse_dates=["decision_date_parsed"]).assign(up_involved=True),
                                     lag_days=cfg.raw["risk"]["lag_days"])
eff = risk.outlet_effects(frame, model.predict(frame)).set_index("outlet_type")
syn = synar.outlet_type_rates().set_index("outlet_type")[["rate"]].rename(columns={"rate": "synar_2025"})
cmp = eff.join(syn).round(3)
print(cmp.sort_values("mean_p").to_string())
ok = cmp.dropna()
print(f"\\nSpearman rank correlation, model vs Synar (types with a Synar rate, n={len(ok)}): "
      f"{ok['mean_p'].corr(ok['synar_2025'], method='spearman'):.2f}")
coef = fit["coefficients"]
print("\\nLargest coefficients (standardized features):")
print(pd.concat([coef.head(4), coef.tail(5)]).round(3).to_string())
"""
)

# --------------------------------------------------------------------------- 3 prize
md("## 3. Externalities: proximity to vulnerable sites as the exposure proxy")
quote(P3, "Proposal, paragraph 3")
md(
    """
**Implementation** (`model/prize.py`). No per-store sales volumes or health-cost data exist, so exposure h_i is a proxy for the
externality, built from (a) proximity to vulnerable sites: NCES public and private schools plus OpenStreetMap libraries, community
centres, childcare, playgrounds and parks ("community centers, etc." is only available through OSM), (b) tract youth share, shrunk
toward the city median where the ACS margin of error is large, and (c) historical severity of past penalties. Weights are in
`config/default.yaml`. The prize is `r_i = h_i * p_i + lambda * D_i`, where D_i (recency x state weight) carries the proposal's
"greater time since past inspection" and `lambda` is assumed. The score is unit-free; it is **not** a dollar estimate of harm.
Caveat: historical severity partly double counts violations already in p_i.
"""
)
code(
    """
r = scores[scores.retail_license].copy()
print(r[["p", "h", "site", "youth", "severity", "deterrence", "prize"]].describe().round(3).T)
top = r.sort_values("prize", ascending=False).drop_duplicates("location_key").head(10)
print("\\nTop 10 by prize (one row per location):")
print(top[["trade_name", "street_address", "outlet_type", "p", "h", "deterrence", "prize", "viol_12m",
           "days_since_check"]].round(3).to_string(index=False))
uni = pipeline.load_universe(cfg)
print(f"\\nTract youth-share estimates flagged unreliable (MOE > 50% of estimate): "
      f"{uni[uni.retail_license].acs_youth_share_unreliable.mean():.0%} of retail licenses")
"""
)
code(
    """
# Sensitivity of the ranking to the exposure weights and lambda (overlap of the top-B stores)
cand = pipeline.unique_locations(r)
B = 11
base = set(cand.nlargest(B, "prize").index)
rows = []
variants = {"site-heavy": (0.7, 0.15, 0.15), "youth-heavy": (0.15, 0.7, 0.15), "severity-heavy": (0.15, 0.15, 0.7),
            "no severity": (0.5, 0.5, 0.0), "equal": (1/3, 1/3, 1/3)}
lam0 = cfg.prize["lambda_deterrence"]
for name, w in variants.items():
    h2 = w[0] * cand["site"] + w[1] * cand["youth"] + w[2] * cand["severity"]
    pr = h2 * cand["p"] + lam0 * cand["deterrence"]
    rows.append({"variant": name, "overlap_top_B": len(base & set(pr.nlargest(B).index))})
for lam in (0.0, 0.1, 0.25, 0.5):
    pr = cand["h"] * cand["p"] + lam * cand["deterrence"]
    rows.append({"variant": f"lambda={lam}", "overlap_top_B": len(base & set(pr.nlargest(B).index))})
print(pd.DataFrame(rows).to_string(index=False))
print(f"(overlap with the baseline top {B}; assumed parameters, so the schedule should never be read as sensitive-free)")
"""
)

# --------------------------------------------------------------------------- 4 stackelberg
md("## 4. Randomized monthly schedule and bounded rationality")
quote(P4, "Proposal, paragraph 4")
md(
    """
**Implementation.** No data shows how Pittsburgh retailers respond to schedules, so a Stackelberg MILP is **not built**; the
passage is used as the design rationale for randomization (`model/thompson.py`, `eval/simulate.py`):
- each monthly cycle samples every store's violation probability from a Beta distribution centered on the model's p_i
  (Thompson sampling, strength `kappa`), so the schedule is not a fixed list;
- a reserved random share is drawn like Synar's simple random Allegheny stratum;
- each store is visited at most once per horizon;
- *bounded rationality* enters the simulation as an assumed parameter rho: stores know how often they were recently checked,
  not when the next check comes, and cut violations in proportion to that frequency; deterrence delta is the effect of a check.

All results here are **simulated** with **assumed** delta and rho; the truth is the model's own calibrated p_i, so these runs show
what each policy does if the model is right.
"""
)
code(
    """
cand_sim = pipeline.unique_locations(scores[scores.retail_license & scores.lon.notna()]).reset_index(drop=True)
saved = OUT / "simulation_policies.csv"
if FULL or not saved.exists():
    sim = experiments.policy_simulation(cfg, cand_sim, n_sims=60 if not FULL else 200)
    sim.to_csv(saved, index=False)
sim = pd.read_csv(saved)
piv = sim.pivot_table(index="policy", columns=["delta", "rho"], values="found_per_cycle").round(2)
print("Violations found per monthly cycle (4 stores per cycle); columns are (deterrence delta, exploitation rho)")
print(piv.to_string())
dist = sim[(sim.delta == 0) & (sim.rho == 0)].set_index("policy")["distinct_stores"].round(0)
print("\\nDistinct stores visited over 36 cycles:"); print(dist.to_string())
"""
)
code(
    """
fig, ax = plt.subplots(figsize=(9, 3.8))
pol = ["random", "status_quo_followup", "prior_violators_first", "prize_topB_fixed", "prize_topB_at_most_once",
       "thompson_prize+random", "thompson_prize+random_at_most_once"]
width = 0.16
scen = [(0.0, 0.0), (0.25, 0.0), (0.0, 0.5), (0.0, 0.9), (0.25, 0.5)]
for k, (d, rho) in enumerate(scen):
    vals = [sim[(sim.policy == p) & (sim.delta == d) & (sim.rho == rho)].found_per_cycle.mean() for p in pol]
    ax.bar(np.arange(len(pol)) + (k - 2) * width, vals, width, label=f"delta={d}, rho={rho}")
ax.set_xticks(range(len(pol))); ax.set_xticklabels(pol, rotation=25, ha="right", fontsize=8)
ax.set_ylabel("violations found per cycle"); ax.axhline(sim[sim.policy == "random"].found_per_cycle.mean(), color="k", lw=0.7)
ax.set_title("Policy simulation (simulated truth, assumed behavior)"); ax.legend(fontsize=7)
plt.tight_layout(); plt.show()
"""
)
md(
    """
**Reading the simulation.** With no behavioral response, repeating the highest-scoring stores each month finds the most.
As soon as stores react to inspection frequency (deterrence delta or exploitation rho), a fixed top-B list collapses, at strong
exploitation below random. Policies that rotate through stores (at most once per horizon, with Thompson noise and a random share)
stay about 1.2-1.4 times random across all assumptions. This is the practical content of the Stackelberg and bounded-rationality
passage: do not publish a predictable list. `kappa` controls how much the sampled rate varies; a quick sensitivity follows.
"""
)
code(
    """
saved = OUT / "simulation_kappa.csv"
if FULL or not saved.exists():
    ks = experiments.kappa_sensitivity(cfg, cand_sim, n_sims=60)
    ks.to_csv(saved, index=False)
ks = pd.read_csv(saved)
cols = [c for c in ["kappa", "policy", "delta", "rho", "found_per_cycle", "distinct_stores", "random_share", "at_most_once"] if c in ks]
print(ks[cols].round(2).to_string(index=False))
print(f"\\nconfig kappa = {cfg.raw['risk']['kappa']}")
"""
)

# --------------------------------------------------------------------------- 5 optimization
md("## 5. Optimization: one monthly cycle, and when routing matters (Gate B)")
md(
    """
**Implementation.** `pipeline.plan_cycle` samples prizes, reserves the random share, prunes to the top candidates plus the random picks
and solves the team model on the OSM drive-time matrix. The comparator is `plan_ranked_batched`: rank by prize, take the top B, then
batch by nearest neighbor. Solver: Gurobi (size-limited pip license) with automatic fallback to HiGHS if the model is too large.
**Gate B** asks whether the MILP collects more prize than ranked+batched.
"""
)
code(
    """
schedule, summary, inst = pipeline.solve(cfg, scores=scores, write=False)
print(f"Travel times: {inst['travel_source']} (OSM drive network); candidates: {len(inst['cand'])} unique retail locations")
print(summary.to_string(index=False))
print(schedule[["cycle", "route", "team", "date", "stop", "store", "address", "p", "h", "prize", "random_share_pick"]]
      .round(3).to_string(index=False))
"""
)
code(
    """
saved = OUT / "gate_b_sweep.csv"
if FULL or not saved.exists():
    sweep = experiments.gate_b_sweep(cfg, inst, budgets=(4, 8, 15, 25), route_counts=(1, 2),
                                     day_minutes=(480, 240, 120), time_limit=20 if not FULL else 60)
    sweep.to_csv(saved, index=False)
sweep = pd.read_csv(saved)
print(sweep[["budget", "n_routes", "day_minutes", "milp_prize", "heuristic_prize", "gain_pct", "status", "seconds"]].to_string(index=False))
real = sweep[(sweep.budget <= 8) & (sweep.n_routes >= 2) & (sweep.day_minutes >= 240)]
tight = sweep[(sweep.day_minutes <= 240) & (sweep.budget >= 15)]
print(f"\\nAt the real operating point (budget <= 8, 2+ route slots, 4+ h days) mean MILP gain: {real.gain_pct.mean():.1f}%")
print(f"When time is scarce (budget >= 15, days <= 4 h) mean MILP gain: {tight.gain_pct.mean():.1f}% (some runs hit the time limit; gains are lower bounds on the optimum)")
"""
)
md(
    """
**Gate B result.** At the budget the data supports (about 4 inspections per month), the MILP and the ranked+batched plan collect the same prize:
routing has nothing to optimize because the budget binds long before the working day does. The MILP only pays off when time is scarce
(larger budgets with short route slots or few team-days), where it gains roughly 4-11% in prize. So the recommendation is to ship a ranked,
randomized list with simple batching, and keep the MILP for scale-up scenarios. The full decision-card formulation (all stores x 65 days x 2 teams)
is infeasible under the size-limited Gurobi license and unnecessary; candidate pruning plus route slots replaces it.
"""
)

# --------------------------------------------------------------------------- 6 evaluation
md("## 6. Evaluation, equity and power")
code(
    """
# Policy metrics for the planned schedule vs baselines (model-based expected values; assumed)
sel_by_cycle = [list(schedule[schedule.cycle == c].cand_index) for c in sorted(schedule.cycle.unique())]
minutes = summary.route_minutes.sum()
rng = np.random.default_rng(cfg.seed)
cand = inst["cand"]
from tobacco_inspect.eval import baselines
def rows_for(name, picks):
    return {"policy": name, **{k: round(v, 3) for k, v in pipeline.policy_metrics(picks, inst, cfg, minutes).items()}}
policies = {
    "planned (Thompson + random share + MILP)": sel_by_cycle,
    "random": [list(baselines.random_baseline(len(cand), cfg.capacity.cycle_budget, rng)) for _ in range(cfg.capacity.cycles)],
    "prior_violators_first": [list(baselines.prior_violators_first(cand, cfg.capacity.cycle_budget, rng))] * cfg.capacity.cycles,
    "status_quo_followup": [list(baselines.status_quo_followup(cand, cfg.capacity.cycle_budget, rng)) for _ in range(cfg.capacity.cycles)],
}
print(pd.DataFrame([rows_for(k, v) for k, v in policies.items()]).to_string(index=False))
print("Expected values use the calibrated p_i (assumed truth). Cost per detected violation uses the $116 lower-bound cost per check.")
"""
)
code(
    """
out = pipeline.report(cfg, schedule=schedule, scores=scores)
print(out["equity"])
cov = out["coverage"]
print(f"\\n{(cov.inspections > 0).sum()} of {len(cov)} tracts have a scheduled inspection this quarter; "
      f"a per-tract floor (min_per_tract) is arithmetically infeasible at {cfg.capacity.budget_inspections} checks per quarter.")
print("\\nWhy-us examples:")
print(out["why_us"][["cycle", "store", "address", "why_us"]].head(4).to_string(index=False, max_colwidth=130))
"""
)
md(
    """
**Gate C: how much random sampling is needed to learn anything?** The reserved random share doubles as the project's only unbiased
data going forward. The table uses the Synar Allegheny rate as the base rate and Pittsburgh's observed volume.
"""
)
code(
    """
city_per_year = fy[fy.fy.between(2022, 2025)].city_up_checks.mean()
print(f"City checks per year (FY2022-25 mean): {city_per_year:.0f}")
print(experiments.power_table(0.26, city_per_year).to_string(index=False))
print("\\nFor reference, Synar itself used n = 100 completed outlets in Allegheny (95% CI half-width about 9 points).")
"""
)

# --------------------------------------------------------------------------- 7 limitations
md(
    """
## 7. What this does and does not establish

| Claim | Status |
|---|---|
| Prior history and outlet type predict violations better than random (PA-wide) | **Supported**, observed-sample replay (selection-biased) |
| The model beats FDA's follow-up rule | **Supported at PA level**, observed-sample; at the very top of the ranking it is about equal to prior-violators-first |
| Pittsburgh-specific lift | **Not testable**: 57 violations over four test years |
| FDA targeting beat random historically | **Partly**: above Synar's band in several years through 2023, indistinguishable in 2024-25 (cigarette-only caveat) |
| Routing optimization adds value at real capacity | **No**: budget binds (Gate B); it matters only when time is scarce |
| Full 3-index MILP (stores x days x teams) | **Infeasible/unneeded** at this scale and license |
| Stackelberg MILP | **Not built**; used as rationale for randomization only |
| Deterrence benefit of enforcement | **Assumed** (lambda, delta, rho); never claimed |
| Cost per prevented violation | **Not estimable** |
| Period effects (FY2013, 2019, 2022) | **Unexplained**: Synar shows purchaser age moves rates 0-21%; OCE has no purchaser attributes |

**Human checkpoints before any use:** (1) read Gate A and the Synar comparison; (2) review the top-20 stores and tract coverage for fairness
before a route sheet is issued; (3) confirm every figure's evidence label; (4) ask DOH about purchaser mix by year, who selects stores, and
the 44 unplaced FDA locations; (5) have a second person check the transcribed Synar tables against the PDF.
"""
)

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {
    "name": "tobacco-inspect",
    "display_name": "tobacco-inspect",
    "language": "python",
}
nbf.write(nb, OUT)
print("wrote", OUT)
