"""Generate notebooks/03_census_vs_sampling.ipynb.

Run: uv run python scripts/build_notebook_03.py
The one proposal sentence quoted for context is read from docs/sources/proposed_alternative.md.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "sources" / "proposed_alternative.md"
OUT = ROOT / "notebooks" / "03_census_vs_sampling.ipynb"

paras = [p.strip() for p in SRC.read_text(encoding="utf-8").split("\n") if p.strip()]
CONTEXT = paras[1].split(". ")[0] + "."  # first sentence of paragraph 1, verbatim
assert "over random sampling" in CONTEXT

cells = []


def md(text: str, tags=None):
    c = nbf.v4.new_markdown_cell(text.strip("\n"))
    if tags:
        c.metadata["tags"] = tags
    cells.append(c)


def code(text: str):
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))


# --------------------------------------------------------------------------- title
md(
    """
# 03 · What if we checked every licensed location in a year?

**Question.** Instead of choosing a few stores (notebook 02), suppose DOH checked *every* distinct licensed location in the
City of Pittsburgh once in a year. (1) How would that work be portioned out? (2) What would it cost, line by line? (3) Is it more
effective, in terms of *capture*, than random sampling?
"""
)
md(f"**Context from the Proposed Alternative:**\n\n> {CONTEXT}", ["proposal-quote"])
md(
    """
**Evidence labels:** *observed* (real records), *simulated* (a synthetic year in which each store sells with the model's probability),
*assumed* (a parameter no data identifies: wages, traffic, deterrence). Exact formulas are identities that hold for any probabilities.

**The idea that organizes everything.** A single undercover purchase is a coin flip: store *i* sells to the minor with probability *p_i*.
It is not a fixed "violator or compliant" label. So "capture" must be defined before it can be compared:
- *violations detected*: how many sales our checks witness;
- *distinct violators caught*: how many different stores are caught at least once (what enforcement acts on);
- *coverage*: how many stores (and how many of the riskiest) get checked at all;
- *precision*: how well we learn the city's overall violation rate.

Code is in `src/tobacco_inspect/eval/census.py` and `routing/partition.py`.
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
from tobacco_inspect.eval import census as C
from tobacco_inspect.eval import experiments
from tobacco_inspect.routing import partition as P

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.max_columns", 40, "display.width", 170)
cfg = load_config()
params = C.CostParams.from_config(cfg)
DAY = cfg.capacity.daily_budget_minutes
res = pipeline.census(cfg, write=False, n_sims=300)
cand, p, travel = res["cand"], res["p"], res["travel"]
N = len(p)
LIFT = float(cfg.raw["census"]["targeted_lift"])
LO_PC, HI_PC = params.topdown_per_check["low"], params.topdown_per_check["high"]
AWARD = cfg.raw["census"]["award_dollars"]
"""
)

# --------------------------------------------------------------------------- 1 universe
md("## 1. What is a 'licensed location'?")
code(
    """
uni = pipeline.load_universe(cfg)
retail_locs = uni[uni.retail_license].location_key.nunique()
all_locs = uni.location_key.nunique()
rows = [
    ("licenses inside city limits", len(uni)),
    ("distinct locations, all license types", all_locs),
    ("distinct retail-selling locations (the census universe)", retail_locs),
    ("locations with only vending / wholesale / other licenses", all_locs - retail_locs),
]
print(pd.DataFrame(rows, columns=["count of", "n"]).to_string(index=False))
print("\\nLicenses by type:"); print(uni.license_type.value_counts().to_string())
cand_obs = cand.fda_observed.mean()
print(f"\\nOf the {N} retail locations, {cand_obs:.0%} have at least one FDA record in the data; {int((~cand.fda_observed).sum())} have none")
print(f"Tracts containing a retail location: {cand.tract_geoid.nunique()}")
print(f"Model estimate (population-calibrated): mean p = {p.mean():.3f}; one census is expected to witness about {p.sum():.0f} violations")
"""
)
md(
    """
**Scope used below:** the {N} distinct *retail* locations, because those are where an under-21 purchaser can buy. Vending-only,
wholesale and similar locations are costed as a variant at the end of section 3. The license list is refreshed daily and licenses expire each
February, so "a year" means this snapshot plus normal turnover (not modeled).
""".replace("{N}", "345")
)

# --------------------------------------------------------------------------- 2 portioning
md(
    """
## 2. Portioning the work

Two separate questions: **where** (which stores share a day) and **when** (which days of the year).

### 2a. Where: cut the city into day-long routes
A team works a day (8 hours: 20 minutes at each store, 15 minutes of paperwork, driving). The stores are cut into routes with a standard
"route first, split second" method: draw one good loop through all stores (nearest neighbor then 2-opt), then cut it optimally into pieces
that each fit in a day. Drive times come from the OpenStreetMap network times a traffic factor (assumed).
"""
)
code(
    """
print(res["cost_summary"][["scenario", "stops", "team_days", "team_hours", "drive_hours"]].to_string(index=False))
routes, t, svc = C.build_routes(travel, params, DAY, "base")
mins = np.array([P.route_minutes(r, t, svc) for r in routes])
stops = np.array([len(r) for r in routes])
retries = params.pick("retry_share", "base") * N
onsite = N * params.onsite_minutes
admin = N * params.pick("admin_minutes", "base")
drive = mins.sum() - N * svc[1]
tot = onsite + admin + drive
print(f"\\nBase case: {len(routes)} team-days, {stops.min()}-{stops.max()} stores per route (mean {stops.mean():.1f}), longest route {mins.max():.0f} min of {DAY:.0f}")
print(f"Team time split: on site {onsite/tot:.0%}, paperwork {admin/tot:.0%}, driving {drive/tot:.0%} (driving is only {drive/60:.0f} hours in total)")
print(f"Lower bound on team-days from on-site + paperwork time alone: {np.ceil((onsite + admin)/DAY):.0f}")
"""
)
code(
    """
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
colors = np.zeros(N)
for r, route in enumerate(routes):
    for node in route:
        colors[node - 1] = r
sc = ax[0].scatter(cand.lon, cand.lat, c=colors, cmap="tab20", s=14)
ax[0].scatter([cfg.raw["solve"]["depot"]["lon"]], [cfg.raw["solve"]["depot"]["lat"]], marker="*", s=180, c="k", label="assumed depot")
ax[0].set_title(f"{len(routes)} day-long routes (colors), base case"); ax[0].legend(); ax[0].set_xlabel("longitude"); ax[0].set_ylabel("latitude")
ax[1].hist(stops, bins=range(stops.min(), stops.max() + 2), rwidth=0.85)
ax[1].set_title("Stores per route"); ax[1].set_xlabel("stores"); ax[1].set_ylabel("routes")
plt.tight_layout(); plt.show()
"""
)
md(
    """
**How good is the heuristic?** On random 9-store subsets of the routes the heuristic tour is compared with the *exact* optimal tour
(Held-Karp dynamic programming).
"""
)
code(
    """
gaps = P.heuristic_gap(routes, t, svc, size=9, trials=30)
print(f"Heuristic vs exact on {len(gaps)} subsets: mean excess {np.mean(gaps):.2%}, worst {np.max(gaps):.2%}")
"""
)
md(
    """
### 2b. When: four ways to place the routes on a calendar
All use random placement so no neighborhood learns its day in advance.
- **A. Summer block**: all routes between July 6 and August 21 (the window Synar uses, when youth purchasers are available).
- **B. Quarters**: a quarter of the routes in each quarter, random order.
- **C. Months**: a twelfth each month.
- **D. Risk-staged**: the riskiest routes in the first quarter, the least risky in the last, random inside each quarter.
"""
)
code(
    """
rows = []
for plan, name in {"A": "A summer block", "B": "B quarters", "C": "C months", "D": "D risk-staged"}.items():
    s = C.calendar_summary(res["calendars"][plan])
    rows.append({"plan": name, **s})
print(pd.DataFrame(rows).to_string(index=False))
print(f"\\nWith {cfg.capacity.teams} teams, {len(routes)} team-days fit in about {int(np.ceil(len(routes)/(5*cfg.capacity.teams)))} working weeks of one block.")
sweep = pd.DataFrame([{"teams": k, "working_weeks_for_a_block": int(np.ceil(len(routes) / (5 * k)))} for k in cfg.raw["census"]["teams_options"]])
print(sweep.to_string(index=False))
"""
)
md(
    """
**What risk-staging costs.** Putting the riskiest stores first means routing each risk tier separately, so stops are more scattered:
"""
)
code(
    """
print(C.risk_staged_cost(travel, params, p, DAY).to_string(index=False))
"""
)
md(
    """
**Does the order matter?** Only if a check changes a store's behavior for a while afterwards. Under an **assumed** three-month window the
*total* protection over a repeating year is identical for every calendar; what differs is the profile through the year:
"""
)
code(
    """
months = np.arange(1, 13)
fig, ax = plt.subplots(figsize=(8.5, 3.6))
for plan, label in {"A": "A summer block", "B": "B quarters", "C": "C months", "D": "D risk-staged"}.items():
    cm = C.store_check_months(routes, res["calendars"][plan], N)
    prof = C.monthly_protection(cm, p, memory_months=3)
    ax.plot(months, prof, marker="o", label=f"{label} (mean {prof.mean():.2f})")
ax.set_xlabel("month"); ax.set_ylabel("risk-weighted share of stores checked in last 3 months")
ax.set_title("Assumed 3-month deterrence window: coverage profile through the year"); ax.legend(fontsize=8)
plt.tight_layout(); plt.show()
"""
)
md(
    """
**Reading it.** A summer block is cheapest to organize and mimics Synar, but leaves winter and spring with no recently-checked stores (under the
assumed window). Spreading the routes across the year keeps a steady presence. The window length itself is **assumed**; if checks have no lasting effect,
the calendar does not matter.
"""
)

# --------------------------------------------------------------------------- 3 expense
md(
    """
## 3. The expense breakdown

Two independent views, because neither is certain:
- **Bottom-up (marginal)**: price the actual routes: supervisor and purchaser hours, mileage, retries, data handling, one-time training, overhead.
- **Top-down (fully loaded)**: DOH's award divided by checks: $116 if the funded 10,000 checks happen, about $400 if only the roughly 2,900 published checks do.

Sourced inputs: IRS 2026 mileage rate (72.5 cents Jan-Jun, 76 cents Jul-Dec); a contractor posting offers $15 an hour to under-21 purchasers; BLS reports a mean
of $35.28 an hour for Pittsburgh compliance officers (used as the supervisor proxy). Everything else in the table is **assumed** and varied.
"""
)
code(
    """
comp = res["components"].pivot_table(index="component", columns="scenario", values="dollars", sort=False)[["low", "base", "high"]]
comp.loc["TOTAL"] = comp.sum()
print(comp.round(0).astype(int).to_string())
cs = res["cost_summary"].set_index("scenario")
print("\\nPer check (bottom-up):", {k: f"${v:,.0f}" for k, v in cs.dollars_per_check.items()})
td = C.top_down_cost(N, params)
print(f"Top-down for {N} checks: ${td['low']:,.0f} (at $116) to ${td['high']:,.0f} (at $400)")
"""
)
code(
    """
fig, ax = plt.subplots(figsize=(8, 2.9))
bars = [("bottom-up low", cs.loc["low", "total_dollars"]), ("bottom-up base", cs.loc["base", "total_dollars"]),
        ("bottom-up high", cs.loc["high", "total_dollars"]), ("top-down $116/check", td["low"]), ("top-down $400/check", td["high"])]
ax.barh([b[0] for b in bars], [b[1] for b in bars], color=["#9ecae1"] * 3 + ["#fdae6b"] * 2)
for i, b in enumerate(bars):
    ax.text(b[1], i, f"  ${b[1]:,.0f}", va="center", fontsize=8)
ax.set_xlabel("dollars for one census of %d locations" % N); ax.invert_yaxis(); ax.set_xlim(0, td["high"] * 1.2)
plt.tight_layout(); plt.show()
"""
)
md(
    """
**Why the two views differ.** Bottom-up prices only the extra work in a dense city (little driving: the stores are close together). The award per check also pays for
statewide travel, management, reporting and contractor margin. Treat bottom-up as the *marginal* cost of adding this work to an existing program and
top-down as the *full-cost* price if a new program had to carry it.

**What drives the bottom-up total** (one parameter at a time, others at base):
"""
)
code(
    """
sens = C.cost_sensitivity(travel, params, DAY)
sens["low_to_high"] = sens.apply(lambda r: f"{r.low_value:g} -> {r.high_value:g}", axis=1)
print(sens[["parameter", "low_to_high", "total_at_low", "total_at_high", "swing"]].round(0).to_string(index=False))
"""
)
md(
    "**The follow-up layer.** FDA practice re-checks violators; a census would find many, and re-checking them adds cost."
)
code(
    """
rows = []
for sc in ["low", "base", "high"]:
    rate = params.pick("followup_rate", sc)
    extra, repeats = C.followup_repeats(p, rate)
    per = cs.loc[sc, "dollars_per_check"]
    rows.append({"follow-up rate": rate, "extra checks": round(extra), "repeat violations caught": round(repeats, 1),
                 "extra cost at bottom-up base per check": round(extra * cs.loc["base", "dollars_per_check"]),
                 "extra cost at $116": round(extra * LO_PC), "extra cost at $400": round(extra * HI_PC)})
print(pd.DataFrame(rows).to_string(index=False))
"""
)
md("**Context and scale.**")
code(
    """
fy = pd.read_csv(cfg.path("interim") / "oce_pa_by_fiscal_year.csv")
recent = fy[fy.fy.between(2022, 2025)]
city_year = recent.city_up_checks.mean(); pa_year = recent.up_checks.mean()
award = AWARD
print(f"Recent city volume: about {city_year:.0f} undercover checks a year; a census is {N / city_year:.1f} times that")
print(f"A census is {N / pa_year:.0%} of Pennsylvania's recent published undercover checks ({pa_year:,.0f} a year)")
print(f"As a share of the latest annual DOH award (${award:,}): bottom-up base {cs.loc['base','total_dollars']/award:.1%}; top-down {td['low']/award:.1%} to {td['high']/award:.1%}")
print(f"Current volume at the same per-check prices: ${city_year * LO_PC:,.0f} to ${city_year * HI_PC:,.0f} a year")
inst_all = pipeline.build_instance(cfg, retail_only=False)
ct_all = C.cost_table(inst_all["travel"], params, DAY)
print(f"\\nVariant: every distinct licensed location, any license type ({len(inst_all['cand'])} locations):")
print(ct_all.to_string(index=False))
"""
)

# --------------------------------------------------------------------------- 4 capture
md(
    """
## 4. Is a census more effective than random sampling?

**First, the exact definitions.** With *n* checks and store probabilities p_i (mean p-bar):

| Policy | Violations detected (expected) | Distinct violators caught | Stores covered |
|---|---|---|---|
| Census (every store once) | sum of p_i | sum of p_i | 100% |
| Simple random sample, no repeats | n x p-bar | (n/N) x sum of p_i | n/N |
| Absolute random draws (a store can be picked again) | n x p-bar | sum of 1 - (1 - p_i/N)^n | 1 - (1 - 1/N)^n |
| Model-targeted top n | sum of the top n p_i (if the model is right) | same | n/N, but the riskiest first |

So at the same number of checks, **a census detects the same number of violations per check as any random scheme**. Differences appear in *who* is covered.
"""
)
code(
    """
cap = res["capture"]
show = cap[cap.budget_share_of_N.isin([0.25, 0.5, 1.0])].copy()
show = show[["policy", "budget_checks", "distinct_exact", "distinct_sim", "coverage_exact", "top_decile_covered", "distinct_if_lift"]]
print(show.round(2).to_string(index=False))
print("\\n(distinct_sim is a 300-run Monte Carlo of the exact column; distinct_if_lift replaces the model's own p with the observed replay lift of about 1.5x for the targeted row)")
"""
)
code(
    """
budgets = np.arange(int(0.1 * N), int(3 * N) + 1, 5)
fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.2))
ax[0].plot(budgets, [C.distinct_iid(p, n) for n in budgets], label="absolute random (repeats allowed)")
nn = budgets[budgets <= N]
ax[0].plot(nn, [C.distinct_srs(p, n) for n in nn], label="simple random, no repeats")
ax[0].plot(nn, [C.distinct_targeted(p, n) for n in nn], label="targeted (if the model is right)")
ax[0].plot(nn, [min(C.distinct_targeted(p, n), LIFT * n * p.mean()) for n in nn], ls="--", label="targeted, observed lift 1.5x")
ax[0].scatter([N], [C.distinct_census(p)], c="k", zorder=5, label="census")
ax[0].set_xlabel("checks in the year"); ax[0].set_ylabel("distinct violators caught (expected)"); ax[0].legend(fontsize=7); ax[0].set_title("Capture by budget (simulated truth)")
ax[1].plot(budgets, [C.coverage_iid(N, n) for n in budgets], label="absolute random")
ax[1].plot(nn, nn / N, label="simple random / targeted")
ax[1].axhline(1, c="grey", lw=0.6); ax[1].set_xlabel("checks in the year"); ax[1].set_ylabel("share of stores checked at least once"); ax[1].legend(fontsize=8)
ax[1].set_title("Coverage by budget (exact)")
plt.tight_layout(); plt.show()
"""
)
code(
    """
cen, iid = C.distinct_census(p), C.distinct_iid(p, N)
print(f"At the census budget ({N} checks): census catches {cen:.1f} distinct violators; absolute random catches {iid:.1f} ({iid/cen-1:+.0%}) and covers {C.coverage_iid(N, N):.0%} of stores")
print(f"Random draws needed to catch as many distinct violators as one census: {C.iid_budget_for_distinct(p, cen)/N:.2f} x N = {C.iid_budget_for_distinct(p, cen):.0f} checks")
for q in (0.9, 0.95, 0.99):
    print(f"Random draws needed to cover {q:.0%} of stores: {C.iid_budget_for_coverage(N, q)/N:.2f} x N = {C.iid_budget_for_coverage(N, q):.0f} checks")
dec = max(1, N // 10)
print(f"\\nRiskiest 10% of stores ({dec}): census covers all; a {N//4}-check simple random sample covers {N//4/N:.0%}; targeted covers 100% of them with {dec} checks")
"""
)
md("### Precision and the value of unbiased labels")
code(
    """
se_c, se_n100, se_nN = C.se_rate_census(p), C.se_rate_sample(p, 100), C.se_rate_sample(p, N)
print(f"Standard error of the observed city violation rate: census {se_c:.1%}; {N} random checks {se_nN:.1%}; Synar-sized sample (n=100) {se_n100:.1%}")
print(f"95% interval half-width: census +/-{1.96*se_c:.1%}, n=100 +/-{1.96*se_n100:.1%}")
pw = experiments.power_table(0.26, N)
print("\\nFor reference, years of random-arm data needed at the city's current volume were 8.5 (rate) and 23 (lift) at a 20% share; a census delivers both in one year.")
print(f"\\nStores with no FDA record today: {int((~cand.fda_observed).sum())} of {N} ({(~cand.fda_observed).mean():.0%}). A census gives every one of them a first, unselected label,")
print("which is the fix for the selection bias that limits the risk model (a census is an unbiased training sample of the whole city, once).")
"""
)
md("### Capture per dollar")
code(
    """
rows = []
base_pc, lo_pc, hi_pc = cs.loc["base", "dollars_per_check"], LO_PC, HI_PC
for label, n, distinct in [
    ("census", N, C.distinct_census(p)),
    ("targeted, observed lift 1.5x", N // 4, min(C.distinct_targeted(p, N // 4), LIFT * (N // 4) * p.mean())),
    ("targeted, model's own p (optimistic)", N // 4, C.distinct_targeted(p, N // 4)),
    ("simple random, same budget as targeted", N // 4, C.distinct_srs(p, N // 4)),
    ("absolute random, same budget as census", N, C.distinct_iid(p, N)),
]:
    rows.append({"policy": label, "checks": n, "distinct violators": round(distinct, 1),
                 "checks per violator": round(n / distinct, 2),
                 "$ per violator (bottom-up base)": round(n * base_pc / distinct),
                 "$ per violator ($116)": round(n * lo_pc / distinct), "$ per violator ($400)": round(n * hi_pc / distinct)})
print(pd.DataFrame(rows).to_string(index=False))
extra_checks = N - N // 4
extra_v = C.distinct_census(p) - min(C.distinct_targeted(p, N // 4), LIFT * (N // 4) * p.mean())
print(f"\\nGoing from a targeted quarter-sized program to a full census adds {extra_checks} checks to catch {extra_v:.0f} more distinct violators: {extra_checks/extra_v:.1f} extra checks per extra violator,")
print(f"about ${extra_checks*base_pc/extra_v:,.0f} (bottom-up base) to ${extra_checks*hi_pc/extra_v:,.0f} ($400/check) each")
"""
)
md("### Doing more than one pass")
code(
    """
two = C.distinct_two_pass(p)
extra_f, repeats = C.followup_repeats(p, params.pick("followup_rate", "base"))
print(f"Census + follow-up of violators (rate {params.pick('followup_rate','base'):.0%}): {extra_f:.0f} extra checks, {repeats:.1f} repeat violations caught (these trigger FDA's escalating penalties)")
print(f"Two full passes: {2*N} checks, {two:.1f} distinct violators vs {cen:.1f} for one pass (+{two-cen:.1f}) for {N} extra checks: {N/(two-cen):.0f} checks per extra violator")
"""
)

# --------------------------------------------------------------------------- 5 verdict
md(
    """
## 5. Verdict, limits and what to decide

| Question | Answer | Label |
|---|---|---|
| Can it be done? | About 24 to 37 team-days of work (28 in the base case). One team could finish a summer block in about six weeks | simulated routes, assumed times |
| What would it cost? | Bottom-up about $13,000 to $66,000 (base about $27,000); top-down about $40,000 to $138,000; follow-up adds about 50 to 80 checks | bottom-up assumed, top-down proxied |
| Is it more effective per check than random? | **No**: the same violations per check as any random draw, and fewer than targeting. It beats *repeat-allowed* random draws by about 14% in distinct violators, and *simple* random sampling only by checking more stores | exact |
| What does it uniquely buy? | Every store and every high-risk store covered; the city rate to within about 2.3 points (vs 4.4 for Synar's n = 100); the first unselected labels for the roughly half of stores never inspected; equal treatment by neighborhood; whatever deterrence "everyone is checked" brings | exact / observed / assumed |
| When is it worth it? | When the goal is coverage, measurement and legitimacy rather than violations per dollar. For violations per dollar, targeting wins | judgment |

**Hybrid worth testing:** a one-time census (or a stratified half-census) to learn the true base rate and label every store, then return to a targeted, randomized
list using the unbiased labels.

**Limits.** The capture numbers use the model's own probabilities (population-calibrated to Synar's 26% Allegheny rate, interval 17-35%); the identities hold for any
probabilities, the levels do not. Wages, traffic, paperwork time, retry share, overhead, training and the deterrence window are assumptions. Youth-purchaser availability
(school calendars, legal limits) is not modeled. The FDA contract sets targets with the contractor, so a city census may need FDA approval or separate funding.

**Human checkpoints.** (1) Agree the unit (345 retail locations; 407 with every license type). (2) Replace the assumed cost inputs with DOH or contractor figures. (3) Confirm the
funding and authority path. (4) Decide whether coverage, measurement and unbiased labels are worth the added cost. (5) Confirm each figure's label before reuse.
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
