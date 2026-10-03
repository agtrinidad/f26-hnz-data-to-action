"""Generate notebooks/04_regime_comparison.ipynb.

Run: uv run python scripts/build_notebook_04.py
Compares two implementations of one compliance regime (budget-capped vs census floor). It reuses
the cost, capture and calendar work of notebook 03 and the risk model of notebook 02, and adds
only a cost-vs-outcome frontier, the value of first-pass labels, one shared response model, and an
equity run on both regimes. The computation is `pipeline.regime` (src/tobacco_inspect/eval/regime.py
holds the pieces); the same call writes outputs/regime_*.csv via `tobacco-inspect regime`.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

from _nb import cells, code, md

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "04_regime_comparison.ipynb"

# --------------------------------------------------------------------------- title
md(
    """
# 04 · One compliance regime, two implementations

**Question.** Notebook 02 builds a plan that spends a small, fixed budget on the highest-need stores. Notebook 03 asks what it would cost
to check every store. Here we treat both as *implementations of the same regime* and compare them on what a program owner cares about:
what each costs, who gets checked, what we learn, and what each could do for compliance.

- **Budget-capped (today):** about four checks a month, highest need first, a reserved random share, each store at most once a year.
- **Census floor:** every store is checked once a year (random dates; need decides the order), then a second pass is spent by need,
  updated with what the first pass found.

Both use the same risk model and the same need score. The difference is the constraint: a cap on checks, or a guarantee of coverage.

**What is new here, and what is reused.** This notebook does not recompute the census cost, the exact capture formulas, the calendars or the
Synar precision comparison; those live in notebook 03 and memo 04, and the results are cited. It adds five things they cannot show:

| New here | Why notebooks 02 and 03 could not show it |
|---|---|
| 1. A cost-versus-outcome path from today's volume to the census | Notebook 03 sampled five budget fractions; it never priced the steps between them |
| 2. The model is not the truth | Notebook 03's targeted line assumed the model's own probabilities were exact (it said so); here the truth is calibrated to the observed replay lift |
| 3. What first-pass labels are worth for the second pass | The Thompson update exists in the code but no earlier analysis used observed outcomes |
| 4. One response model, scored on *exposure* | Earlier simulations counted detections, which fall when deterrence works; the regime's goal is a lower violation rate, so we measure that |
| 5. Equity for both regimes | `eval/equity.py` was run on the targeted plan only, while notebook 03 asserted "equal treatment" |

**Evidence labels.** *observed* (real records), *simulated* (a synthetic year), *assumed* (a parameter no data identifies). Every deterrence number
below is assumed: nothing in our data shows that a check, or the certainty of a check, changes a retailer's behavior.
"""
)

code(
    """
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tobacco_inspect import pipeline
from tobacco_inspect.config import load_config
from tobacco_inspect.eval import regime as R

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.max_columns", 40, "display.width", 170)
cfg = load_config()
res = pipeline.regime(cfg, write=False)  # same call as `tobacco-inspect regime`, which writes outputs/regime_*.csv
p, N, truths, TRUTH = res["p"], res["N"], res["truths"], res["truth"]
fr, E2 = res["frontier"], res["second_pass_checks"]
RG = cfg.raw["regime"]
LIFT, FLOOR, SHARE = RG["observed_lift"], RG["floor_months"], RG["second_pass_share"]
B_CYCLE = cfg.capacity.cycle_budget
print(f"{N} retail locations; city rate (model, Synar-calibrated) {p.mean():.3f}")
print(f"Budget-capped: {B_CYCLE} checks a month = {B_CYCLE * 12} a year. Census floor: {N} checks in months 1-{FLOOR}, then a second pass of {E2} ({SHARE:.0%} of N) in months {FLOOR + 1}-12.")
"""
)

# --------------------------------------------------------------------------- 1 the regime
md(
    """
## 1. The regime on one page

| Design choice | Budget-capped | Census floor |
|---|---|---|
| Which stores are checked in a year | the highest-need few (Thompson draw around the model's probability, times exposure `h`), plus a random share | all of them, then the highest-need again |
| Role of need | selects *whether* a store is checked | sets *when* (risk-first order) and *how often* (second pass) |
| Predictability | high-need stores are likely, not certain; dates random | every store certain once; dates and sequence random; second pass randomized (Thompson) |
| Repeat checks of the same store | none within the year | second pass; violators can be re-checked |
| What it learns | outcomes at selected stores only (biased sample) | an unselected label for every store, and a city rate with a known error |
| Optimization problem | which stores (selection, notebook 02) | who goes when (partition, notebook 03) |

**A caution on the word "census."** One undercover purchase is a single coin flip with probability *p_i*. A census therefore measures *attempts*, not
compliance: a store that passes once is not shown to be compliant, and one that fails is not shown to be a habitual seller. What a census can support is a
city-level rate, coverage, and a first label; store-level conclusions need repeat checks. This is why the census floor is paired with a second pass.
"""
)

# --------------------------------------------------------------------------- 2 truth
md(
    """
## 2. The model is not the truth

Notebook 03's targeted line assumed each store sells with exactly the model's probability. The model's own top-decile lift is about 1.7, but the lift
observed when the model is replayed on past checks is about 1.5 (Gate A, interval 1.2 to 1.8). Two things could explain the gap, and the data cannot
separate them:

- the model is **overconfident**: true risk is less spread out than predicted (`slope` below 1);
- stores differ in ways the model cannot see: **hidden heterogeneity** (`sigma` above 0).

We calibrate the slope so the model's top-decile lift equals the observed lift *for each* level of hidden heterogeneity, and report results across the
range. This matters because first-pass labels are only worth something if stores differ in ways the model misses.
"""
)
code(
    """
own = R.realized_lift(p, R.Truth())
rows = [{"hidden sigma": s, "slope (1 = model is right)": round(t.slope, 2), "top-decile lift": round(R.realized_lift(p, t), 2)} for s, t in truths.items()]
print(f"Model's own top-decile lift: {own:.2f}.  Observed replay lift: {LIFT}.  Largest hidden sigma consistent with it: {res['max_sigma']:.2f}")
print(pd.DataFrame(rows).to_string(index=False))
q0 = TRUTH.draws(p, 300, np.random.default_rng(0)).mean(axis=0)
fig, ax = plt.subplots(figsize=(4.6, 3.6))
ax.scatter(p, q0, s=8, alpha=0.5)
ax.plot([0, p.max()], [0, p.max()], "k--", lw=0.8, label="model is the truth")
ax.set_xlabel("model probability"); ax.set_ylabel("true probability (slope-calibrated)"); ax.legend(fontsize=8)
ax.set_title("Baseline truth: an overconfident model, no hidden spread")
plt.tight_layout()
"""
)
md(
    """
**Baseline used below: hidden sigma = 0.** It is the conservative choice for the census floor's second pass (labels add no information the model lacks),
so any benefit we report for adaptive second passes is not manufactured by the assumption. Section 4 sweeps sigma to show where the answer flips.
"""
)

# --------------------------------------------------------------------------- 3 frontier
md(
    """
## 3. What each step up in effort buys

Walk the budget from today's volume to the census and beyond. Costs are bottom-up from the real routes of the selected stores (notebook 03's cost model).
Today's program is already contracted and trained, so the capped rows carry no one-time commissioning cost; the census does (training, 2,000 dollars in the base case, plus overhead).
Top-down costs (116 to 400 dollars per check) are in the table for comparison.
"""
)
code(
    """
cols = ["policy", "checks", "distinct_violators", "events", "coverage_stores", "coverage_top_decile", "se_rate", "team_days", "cost_bottom_up", "cost_topdown_low", "cost_topdown_high"]
print(fr[cols].round({"distinct_violators": 1, "events": 1, "coverage_stores": 2, "coverage_top_decile": 2, "se_rate": 3, "cost_bottom_up": 0, "cost_topdown_low": 0, "cost_topdown_high": 0}).to_string(index=False))
print("\\nse_rate: standard error of the city violation rate; blank for targeted lists because a selected sample cannot estimate it without reweighting.")
"""
)
code(
    """
fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.2))
style = {"random": ("tab:gray", "o", "-"), "targeted": ("tab:blue", "s", "-"), "targeted_model_p": ("tab:blue", "s", ":"),
         "census_floor": ("k", "*", "-"), "census_floor+adaptive_second_pass": ("tab:red", "^", "-"), "census_floor+random_second_pass": ("tab:orange", "v", "--")}
label = {"targeted": "targeted (calibrated truth)", "targeted_model_p": "targeted (model is truth: optimistic)", "random": "simple random",
         "census_floor": "census floor", "census_floor+adaptive_second_pass": "census + adaptive 2nd pass", "census_floor+random_second_pass": "census + random 2nd pass"}
for pol, (c, m, ls) in style.items():
    d = fr[fr.policy == pol].sort_values("checks")
    if pol.startswith("census_floor") and pol != "census_floor":
        d = pd.concat([fr[fr.policy == "census_floor"], d])
    ax[0].plot(d.cost_bottom_up / 1000, d.distinct_violators, color=c, marker=m, ls=ls, label=label[pol])
    ax[1].plot(d.cost_bottom_up / 1000, d.coverage_top_decile, color=c, marker=m, ls=ls)
ax[0].set_xlabel("bottom-up cost for the year (thousand dollars)"); ax[0].set_ylabel("distinct violators caught (expected)"); ax[0].legend(fontsize=7)
ax[0].set_title("Violators caught for the money (simulated)")
ax[1].set_xlabel("bottom-up cost for the year (thousand dollars)"); ax[1].set_ylabel("share of highest-need decile checked"); ax[1].set_title("Coverage of the highest-need stores")
plt.tight_layout()
"""
)
code(
    """
print("Marginal cost along the targeted -> census -> adaptive second pass path (bottom-up, simulated):")
print(res["marginal"].round(1).to_string(index=False))
tg = fr[fr.policy == "targeted"].sort_values("checks")
cen = fr[fr.policy == "census_floor"].iloc[0]
print(f"\\nA targeted list of {int(tg.checks.max())} checks (the largest tried, {tg.checks.max() / N:.0%} of stores) is expected to catch {tg.distinct_violators.max():.0f} distinct violators; the census catches {cen.distinct_violators:.0f} with {int(cen.checks)} checks.")
print(f"Targeting covers the whole highest-need decile with about {int(round(0.1 * N))} checks; random sampling needs the whole census to cover it.")
"""
)
md(
    """
**Reading the path.** Targeting is the cheaper way to catch violators at every budget below the census, as notebook 03 found. Two things the path adds:

1. The marginal cost per added violator *rises* as the targeted list grows (the easy, high-need stores go first), and the step from a large targeted list to the
   census carries the one-time commissioning cost, so it is the most expensive step per added violator.
2. The census's gains are not violators per dollar; they are the rows on the right: complete coverage of the highest-need stores with certainty,
   a city rate with a known error, and a first label for every store.
"""
)

# --------------------------------------------------------------------------- 4 second pass
md(
    """
## 4. What the first pass is worth: choosing the second pass

After the first pass every store has one outcome. We update each store's Beta posterior with it (`thompson.update`, unused by earlier notebooks) and
spend the second pass (`E2` checks) five ways. The objective matters, so we score three:

- **second-pass violations** detected;
- **repeat violators**: stores that sold in *both* passes. This is what FDA's escalating penalties act on;
- **new distinct violators**: stores caught for the first time in the second pass.
"""
)
code(
    """
sp = res["second_pass"]
base = sp[sp.hidden_sigma == 0.0].set_index("policy")
print(f"Second pass of {E2} checks, baseline truth (hidden sigma 0). Gain is versus a random second pass, paired across the same simulated years; se in the last column.")
print(base[["second_pass_events", "repeat_events", "new_distinct", "gain_vs_random", "gain_se"]].round(2).to_string())
"""
)
code(
    """
fig, ax = plt.subplots(1, 3, figsize=(12.5, 3.8), sharex=True)
for pol in R.SECOND_PASS_POLICIES:
    d = sp[sp.policy == pol].sort_values("hidden_sigma")
    for a, col in zip(ax, ["second_pass_events", "repeat_events", "new_distinct"], strict=True):
        a.plot(d.hidden_sigma, d[col], marker="o", label=pol)
for a, t in zip(ax, ["violations detected in the second pass", "repeat violators (sold in both passes)", "new distinct violators"], strict=True):
    a.set_title(t, fontsize=9); a.set_xlabel("hidden store-level heterogeneity (sigma)")
ax[0].legend(fontsize=7)
plt.tight_layout()
piv = sp.pivot(index="hidden_sigma", columns="policy", values="second_pass_events")
x = R.crossing(piv.index.to_numpy(), (piv["posterior_mean"] - piv["static_model"]).to_numpy())
print(f"Hidden sigma at which updating on first-pass outcomes starts to beat ranking by the model alone (violations detected): about {x:.2f}  (largest consistent with the observed lift: {res['max_sigma']:.2f})")
"""
)
md(
    """
**What this says.**

- *If* stores differ in ways the model cannot see, labels from the first pass are valuable and the adaptive rules pull ahead on violations detected. *If not*
  (sigma near 0), the model's own ranking is as good or better, and the first pass's value is the base rate and the unbiased label, not a smarter second pass.
  Today's data cannot tell which world we are in; the first pass itself would, by showing how much store outcomes vary beyond the model.
- Re-checking violators finds the most repeat violators and almost no new ones. It serves the FDA escalation goal and not the goal of reaching new violators.
  The Thompson posterior rule sits between the two and keeps the selection unpredictable. The rule should follow the objective the program owner chooses.
"""
)

# --------------------------------------------------------------------------- 5 response
md(
    """
## 5. Does the regime change compliance? A shared response model

Earlier simulations counted *violations found*. That is the wrong score for a regime: if deterrence works, violations found go down. The outcome of a
regime is the **violation rate across all stores**, so we measure `reduction`: the fall in the mean violation probability versus no enforcement, averaged over the year.

The response channels come from `simulate.effective_p` and are **assumed** (nothing in our data identifies them):

- `delta`, `memory`: a check lowers that store's violation probability by a fraction for the next months (store-specific deterrence);
- `gamma`, `gamma_power`: *general* deterrence: every store's probability falls with how visible enforcement is (the share of stores checked in the last six months).
  This is the "everyone is checked" effect a census is meant to create. `gamma_power` is its shape: above 1, only near-universal checking deters (a credibility threshold);
  below 1, the first checks matter most.

(A third channel, `rho`, a store's response to how often it alone has been checked, is in `eval/simulate.py` and was used by notebook 02; it is not needed here.)
"""
)
code(
    """
CAP_COST, CEN_COST = res["cap_cost"], res["cen_cost"]
print(f"Annual cost used: budget-capped {B_CYCLE * 12} checks = ${CAP_COST:,.0f} (running program, no commissioning); census floor + second pass {N + E2} checks = ${CEN_COST:,.0f}")
print("reduction = fall in the city's mean violation probability (fraction). 'per 1k dollars' and 'per 100 checks' are percentage points of reduction.")
print(res["response_grid"].round(3).to_string(index=False))
"""
)
md(
    """
**Reading the grid.** With a response that is linear in checks, the census floor reduces the violation rate roughly seven to eight times more than the capped plan,
because it does about nine times the checking. *Per dollar* the capped plan is modestly ahead (about 20% in these rows): its checks are better aimed, and the census costs about
the same per check once commissioning is counted. No response channel here gives the census an efficiency edge on its own.
The comparison therefore turns on one assumption nobody has data for: **the shape of the visibility effect**. The next cell sweeps it.
"""
)
code(
    """
sweep, x = res["shape_sweep"], res["break_even_power"]
print(sweep.round(3).to_string(index=False))
print(f"\\nBreak-even shape: the census floor is more cost-effective than the capped plan only if gamma_power is above about {x:.2f} (a credibility threshold), under these assumed costs.")
fig, ax = plt.subplots(figsize=(5.4, 3.6))
ax.plot(sweep.gamma_power, sweep["capped_per_1k"], marker="o", label="budget-capped")
ax.plot(sweep.gamma_power, sweep["census_per_1k"], marker="s", label="census floor + 2nd pass")
if not np.isnan(x):
    ax.axvline(x, color="gray", ls=":")
ax.set_xlabel("gamma_power: shape of the visibility effect (1 = linear)"); ax.set_ylabel("percentage points of reduction per 1k dollars"); ax.legend(fontsize=8)
plt.tight_layout()
"""
)
md(
    """
**What this means.** The census earns its cost on compliance only if general deterrence is *convex*: it takes near-universal checking to change behavior
(everyone believes they will be checked). If instead the first checks do most of the work (concave), a small targeted program is the better buy. Our data say
nothing about this shape. That is the single most decision-relevant unknown, and a census can be designed to measure it (section 7).

Two further comparisons, still assumed:
"""
)
code(
    """
print("Does need-based *timing* of the first pass matter? (riskiest stores first)")
print(res["order_table"].round(4).to_string(index=False))
print("\\nSecond-pass rule inside the full year (no response), baseline truth:")
print(res["second_pass_rules"].round(1).to_string(index=False))
a = res["capped_run"]
print(f"\\nBudget-capped: {a['detections']:.1f} detections, {a['distinct_detected']:.1f} distinct, {a['repeat_violators']:.1f} repeat violators (zero by construction: each store at most once a year, no follow-up).")
"""
)
md(
    """
Timing the first pass by need (riskiest stores first) gives them a longer protected stretch of the year. The gain is negligible when protection lasts three months and about a
point of reduction when it lasts six; it costs nothing extra, but it is not a reason to choose a regime. The repeat-violator count for the capped plan is zero only because it
never re-checks; it compares the *second-pass design*, not the regimes.
"""
)

# --------------------------------------------------------------------------- 6 equity
md(
    """
## 6. Who is checked? Equity under both regimes

Notebook 03 asserted "equal treatment by neighborhood" for a census without running the audit, and notebook 02 audited only the targeted plan.
Here `eval/equity.py` runs on both. Poverty and youth share are ACS estimates with large margins (42% of retail licenses sit in tracts with unreliable youth data), so gaps are indicative.
"""
)
code(
    """
print(res["equity"].round(3).set_index("regime").T.to_string())
"""
)
md(
    """
**Reading it.** A census gives every tract its proportional share of checks and leaves no store unchecked; the capped plan leaves most stores unchecked in any one year and
sends a somewhat larger share of its few checks to the highest-poverty quartile, because need correlates with it. Whether that is "fair" is a policy judgment: it is need-responsive,
but it is also uneven treatment of similar sellers. The retailer-side view matters too: a store in a low-need tract that is checked every year by a census bears a cost
that an equal-treatment rule does not justify on need grounds alone, which is one reason the second pass, not the floor, carries the need weighting.
"""
)

# --------------------------------------------------------------------------- 7 verdict
md(
    """
## 7. Verdict, what would change it, and how to learn

| Question | Answer | Label |
|---|---|---|
| Does "a census that stays need-responsive" hold up? | **Yes, as a regime design; no, as an efficiency claim.** Need sets the first-pass order and the second pass; it does not decide whether a store is covered | design |
| Is it more cost-effective at catching violators? | No. Targeting catches more per dollar at every budget below the census; the census step is the costliest per added violator | simulated, cost assumed |
| What does it uniquely buy? | Certain coverage of every store and the whole highest-need decile; a city rate with a known error; an unbiased label for every store; proportional treatment by tract | exact / simulated |
| Does it improve compliance? | **Unknown.** It reduces the violation rate more *in total* under any assumed deterrence, and is more cost-effective only if visibility deters convexly (a credibility threshold) | assumed |
| Is a smarter second pass worth it? | Only if stores differ in ways the model misses; otherwise the model's ranking is as good. The rule should follow the objective (repeat violators vs new violators) | simulated |
| What can we not say? | That a census reduces underage sales; that a store that passed once is compliant | none |

**Recommendation (staged, because the decisive facts are unknown and the first stage measures them).**
1. Run **one census-floor year** in a defined window, with random dates and a risk-first order, and a **randomized second pass**. It is the cheapest way to learn
   the three unknowns above: the true city rate, how much stores differ beyond the model, and (via randomized timing) whether recently checked stores sell less.
2. **Learn deterrence from the design.** Randomize which routes are checked in which month. A second-pass check of stores last checked early versus late in the year is then a
   dose-response in time since last check. That is the first real evidence on `delta` and `memory`.
3. Then **decide the default**: return to the capped, targeted plan with unbiased labels if the response is weak or concave; keep a coverage guarantee if it is strong and convex.

**What would change this.** Funding and authority (the FDA contract targets, who may run a city census), purchaser availability, real unit costs, whether census data can serve
Synar's random-sample requirement (unverified), and whether Allegheny County Health Department rather than the state owns enforcement in the city (unverified).

**Human checkpoints.** (1) Agree the objective for the second pass: repeat violators, new violators, or exposure near schools. (2) Replace assumed costs with DOH or contractor figures.
(3) Decide whether a one-year learning census is fundable. (4) Check each figure's label before reuse. See memo 06 and ADR 0007 for the decisions and what each depends on.
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
