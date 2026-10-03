# Memo 03: Implementation, results and what they mean

**Project:** Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA
**Date:** 2026-09-30. **Scope:** City of Pittsburgh limits. **Companion files:** [memo 02 (data)](02_Data_Acquisition_Memo.md),
[annotated notebook](../../notebooks/02_risk_and_schedule.ipynb) and its [executed HTML copy](03_Implementation_Notebook_Executed.html),
[APA source catalog](../data-sources.md), [ADR 0005](../adr/0005-two-stage-selection-and-routing.md).


> **Reconciliation note (2026-10-01, updated 2026-10-03):** the 11-visit quarterly proxy is rounded up to 4 stores in each of three cycles (12 visits, about 48 checks a year against the 44-a-year proxy). An exact 4/4/3 split was tried and reverted so that this memo, the simulations, the census and regime scenarios and notebooks 02 to 04 share one convention.

Written for the project team and for any reader who has to judge whether the recommendation can be trusted. It is meant to be read
without the code. Every number below is reproduced by `uv run tobacco-inspect run-all` and by the notebook; where a number depends on an
assumption nobody has measured, it says so.

---

## 1. The short version

**What was asked.** Turn the team's Proposed Alternative (a budgeted prize-collecting traveling-salesman approach, Harrington-style
targeting, a vulnerable-site externality proxy, and Stackelberg-style randomization) into working code, test whether it beats the
alternatives, and flag anything that cannot be done with the information we have.

**What was built.** A pipeline that (1) scores every retail license in the city for the chance it sells to a minor, (2) adds an
exposure measure (how close to schools and youth sites) and a "follow-up due" term, (3) draws a randomized monthly list of stores within
the inspection budget, (4) orders the visits into a route using real drive times, and (5) writes route sheets, a plain-language reason for
each store, and an audit of where inspections land.

**Five findings you can rely on (with the caveats in section 6):**
1. **Prior history and store type predict violations.** On Pennsylvania undercover checks in fiscal years 2022 to 2025 (train on earlier
   years, test on the next), the top 10% of the model's ranking contained about 1.5 times as many violations as the average store
   (95% interval about 1.2 to 1.8). A random ranking gives 1.0. FDA's own follow-up rule scored about 1.1 to 1.4. *Observed-sample evidence
   (only inspected stores can be scored).*
2. **The model is not a big improvement at the very top of the list over "prior violators first".** It is better across the whole
   ranking (a measure called AUC is 0.72 against 0.57), because store type matters a lot, but the top slots look similar.
3. **FDA's past targeting beat a random sample in several years, but not recently.** Compared with the state's random Synar survey, FDA
   undercover violation rates were above the Synar band in 2016-2019, 2022 and 2023, and inside it in 2024-2025 (cigarette-only caveat).
4. **Route optimization does not matter at the real budget.** The city's budget is about 4 inspections a month; one team-day fits about
   15 stops. The optimized route and a simple ranked-and-batched route collect identical prize. The optimizer starts to help (about 4 to
   11% more prize) only when time is scarce. So the recommendation is a ranked, *randomized* list with simple batching.
5. **A predictable list is a weakness.** In simulations where stores react to how often they are inspected, repeating the same top stores
   falls below random, while rotating through stores (each at most once per quarter, with randomness and a random share) stays at roughly
   1.2 to 1.4 times random across every assumption tried. *Simulated, with assumed behavior.*

**What cannot be claimed:** that the schedule reduces underage sales (no deterrence data), anything specific to Pittsburgh's lift (57 violations over four test
years, as few as 3 in one year, is too few for stable estimates), a cost per prevented violation, or that the period swings in Pittsburgh's violation rate are store
behavior (they may be inspector or purchaser mix).

---

## 2. How to read the results: labels and plain-language glossary

Every result carries one of three labels:
- **Observed-sample**: from real records, but only for stores that were actually inspected. FDA chose whom to inspect, so these stores are
  not a random picture of all stores.
- **Simulated**: computed on an invented truth (the model's own probabilities), so it shows what a policy does *if the model is right*.
  It cannot prove the model is right.
- **Assumed**: depends on a number nobody has measured (for example how much an inspection deters a store).

| Term | Meaning |
|---|---|
| Undercover check | An FDA-contracted inspection where an under-21 purchaser tries to buy tobacco. "Violation" = a sale was made |
| Violation rate | Violations divided by undercover checks |
| Lift at top 10% | Violation rate among the highest-ranked 10% divided by the average rate. 1.0 = no better than random; 1.5 = 50% more violations |
| AUC | Chance that a randomly chosen violating store is ranked above a randomly chosen compliant one. 0.5 = coin flip, 1.0 = perfect |
| Prize | The score a store earns for being inspected: risk x exposure + a small follow-up term. Unit-free, not dollars |
| Gate | A yes/no test the plan must pass before the next layer is trusted (A: does history predict? B: does routing matter? C: is there enough random data?) |
| Thompson sampling | Each month the plan draws a plausible violation chance for each store (around the model's estimate) so the list changes from month to month |
| Synar | The state's annual random survey of cigarette retailers; the only random baseline we have |
| Fiscal year (FY) | October to September, how the FDA files are organized |

---

## 3. What was done, step by step

Every step lists what, why, and where the result lives. Parameters are in `config/default.yaml`.

### 3.1 Capacity and scope (from memo 02)
- Scope: City of Pittsburgh limits (467 licenses; 392 retail licenses at **345 distinct locations**, because some stores hold two licenses).
- Budget: about 44 city undercover checks a year (FY2022-25) gives **11 per quarter, about 4 per monthly cycle**. Two teams and 20 working
  days a month give 40 team-days, far more than 4 stores need.

### 3.2 Random-sample benchmark: the PA 2025 Synar report
- The PDF was read in full and its tables **transcribed by hand** into `src/tobacco_inspect/data/synar.py` (page numbers recorded),
  written to `data/interim/synar_2025_*.csv`. A built-in check confirms regional totals (1,698 selected, 1,261 completed, 189 violations)
  and outlet-type totals (1,261 / 189). **A second person should still compare the tables with the PDF.** The 2016-2025 history is read off a
  chart, so bounds are approximate.
- Key facts used: Allegheny County 26.0% (95% interval 17.3-34.7, 100 outlets); statewide 15.2%; outlet-type rates (dollar stores 2.9%,
  supermarkets 6.6%, chain convenience/gas 13.9%, tobacco shops 22.3%, independent convenience 23.7%).
- Limits: cigarettes only, summer 2025 only, small county sample.

### 3.3 History features without peeking into the future (`model/history.py`)
For each undercover check, features use only records at the same address decided at least **30 days earlier**: number of earlier checks and
violations, share that were violations, violations in the last 12, 24 and 36 months, days since the last check and since the last violation,
chain size (how many Pennsylvania addresses share the retailer's name), last year's statewide violation rate, and **outlet type** following
Synar's definitions (chain convenience/gas, independent convenience, dollar store, pharmacy, supermarket, tobacco shop, and so on).
- Why decision dates: inspection dates are missing for about 90% of FDA records.
- Leak protection is tested: changing a future record leaves earlier rows' features unchanged.
- Result: 49,032 undercover checks with 7,217 violations form the training table.

### 3.4 Risk model (`model/risk.py`)
- A regularized logistic regression (a plain, auditable statistical model). Strength of regularization chosen by holding out the last
  fiscal year in time, then refit on everything.
- **Prior-shift calibration:** FDA's stores are not a random sample, so the model's average (16.3%) is rescaled to Synar's Allegheny rate
  (26.0%) by shifting the intercept (+0.61 on the log-odds scale). The ranking is unchanged; only the level moves. Sensitivity range 17.3-34.7%.
- Direction check against Synar's outlet-type rates: the model ranks outlet types the same way (rank correlation 0.94 on the six types
  with a published rate). Pharmacies and dollar stores are lowest; independent convenience stores and tobacco shops highest.

### 3.5 Targeted vs untargeted, and follow-up timing (`model/harrington.py`)
- A store is "targeted" if it had a violation in the last 24 months. Its enforcement state follows FDA's real escalating penalty ladder
  (OIG report): the number of violations in the last 36 months, capped at 4, sets a weight (0.25, 0.6, 0.8, 1.0, 1.0). **These weights and
  the overall strength `lambda = 0.25` are assumed.**
- A recency factor rises to 1 over the 12 months after the last check, carrying the proposal's "greater time since past inspection".

### 3.6 Exposure and the prize (`model/prize.py`)
Exposure h combines (weights from the config): proximity to schools (public and private) and OpenStreetMap youth sites (libraries, community
centres, childcare, playgrounds, parks); tract youth share (shrunk toward the city median where the ACS margin of error is large; 42% of
retail licenses sit in tracts flagged unreliable); and a severity score from past warning letters and penalties. **Prize = h x p + lambda x
follow-up term.** It is a ranking device, not an estimate of dollars of harm. Severity partly double counts violations already in p.

### 3.7 Randomization (`model/thompson.py`)
Each monthly cycle: draw every store's chance from a Beta distribution centered on the model's estimate (strength kappa = 5), reserve at
least one of the four slots (20%) for a simple random pick like Synar's Allegheny design, never revisit a store within the quarter.
kappa was chosen from simulation (section 4.5): at kappa = 20 the draw barely changed the list.

### 3.8 Routing and the optimizer (`routing/distance.py`, `model/orienteering.py`)
- Drive times between 345 store locations and an assumed downtown depot come from the OpenStreetMap drive network (cached).
- `solve_team_orienteering`: choose stores and order them into route slots (team x day) to maximize prize within a day length, a store
  budget and the random-share floor. It uses Gurobi, and falls back to HiGHS automatically if a model exceeds the size-limited license.
- Comparator `plan_ranked_batched`: take the top stores by prize, then batch them by nearest neighbor.
- Dates are illustrative (weekdays, federal holidays skipped).

### 3.9 Baselines and metrics (`eval/`)
Random draw, prior-violators-first, FDA's follow-up rule (re-inspect violators within 12 months), nearest-neighbor routing; metrics for expected
violations, violations per inspector-hour, share of visits in high-exposure areas, unpredictability across cycles, cost per detected violation.

### 3.10 Equity audit (`eval/equity.py`)
Stores are scored without demographics. The audit then checks where inspections land by census tract and whether coverage tracks tract poverty.

### 3.11 Outputs and checks
`data/processed/risk_scores.csv`; `outputs/` holds the backtest, model summary, schedule, reasons, equity files, Gate B sweep and simulations.
51 automated tests pass (unit tests for each module, the leakage guard, solver feasibility including an infeasibility error, and a test that the
notebook's quoted proposal text matches the source exactly); the code passes lint; the whole pipeline runs with one command; the notebook executes
from top to bottom with zero errors in about 30 seconds (slow experiments load saved results).

---

## 4. Results

### 4.1 Gate A: does history predict violations? (observed-sample)
Pennsylvania undercover checks, mean over test years 2022-2025. Lift = violation rate in the top slice divided by the pool average.

| Ranking | AUC | Lift, top 10% (95% interval) | Lift, top 20% (95% interval) |
|---|---|---|---|
| Model | 0.72 | 1.47 (1.23-1.77) | 1.53 (1.35-1.73) |
| Prior violators first | 0.57 | 1.49 (1.23-1.80) | 1.46 (1.29-1.64) |
| Days since last check | 0.58 | 1.47 (1.11-1.65) | 1.32 (1.18-1.54) |
| FDA follow-up rule | 0.52 | 1.37 (1.05-1.63) | 1.14 (1.00-1.35) |
| Random | 0.49 | 1.01 (0.76-1.23) | 0.94 (0.78-1.11) |

**Reading it:** the model clearly beats random and FDA's follow-up rule over the whole ranking. At the very top it is no better than a simple
"prior violators first" rule. **Pittsburgh-only replay is uninformative:** intervals run from about 0 to 3 because the four test years hold only 174 city checks and 57 violations (3 to 24 a year). Gate A passes at the Pennsylvania level; the Pittsburgh claim rests on assuming Pittsburgh behaves like the state.

### 4.2 Was the status quo already better than random? (observed-sample, with Synar)
Statewide FDA undercover violation rate against Synar's confidence band (Synar bounds approximate):

| FY | FDA rate | Synar band | Position |
|---|---|---|---|
| 2016 | 13.1% | 8-12% | above |
| 2017 | 18.9% | 6-9% | above |
| 2018 | 11.5% | 7-11% | above |
| 2019 | 16.2% | 6-10% | above |
| 2020 | 12.0% | 14-19% | below (COVID, partial year) |
| 2022 | 29.1% | 14-19% | above |
| 2023 | 19.6% | 9-14% | above |
| 2024 | 11.2% | 11-16% | inside |
| 2025 | 17.6% | 13-18% | inside |

Pittsburgh city FDA rates (FY2022-24: 44%, 31%, 34%) sit at or above the top of Synar's Allegheny interval (26%, up to 34.7%); FY2013 and
FY2019 (0% and 1.6%) are far below it. **Caution:** Synar counts cigarette sales only; FDA counts any product and includes follow-up visits.

### 4.3 Gate B: does routing matter? (computed, 24 settings)
| Situation | MILP vs ranked+batched |
|---|---|
| Real budget (4 to 8 stores a month, 2+ route slots, 4-hour or longer days) | identical prize (0.0% gain) |
| Time scarce (15 to 25 stores, 4-hour or shorter days, or 1 to 2 route slots) | 0% to 11% more prize (average about 6%; no gain in some settings) |

Five of the 24 larger runs stopped at the 60-second limit, so those gains are lower bounds. The optimizer also saves little travel: a
four-store cycle takes about 110 minutes either way.

### 4.4 The monthly schedule (one run, seed 867)
Three monthly cycles of four stores each (12 visits) in one route per cycle, about 108 to 113 minutes each, Gurobi, optimal. Each visit has a plain-language reason in
`outputs/why_us.csv` (for example "2 violations in the last 36 months; 607 days since last recorded check; outlet type: convenience gas").
One of four stores per cycle is a random pick. **Equity audit:** the 12 visits fall in 9 of 94 tracts; 20% of inspections are in the highest-poverty
quartile of tracts, which hold 21.7% of retailers; correlation of coverage with tract poverty is about -0.01. With so few visits the audit is
indicative only, and a "minimum one check per tract" rule is impossible (94 tracts, 11 checks).

### 4.5 Policy simulation (simulated truth, assumed behavior)
Violations found per monthly cycle (4 stores per cycle). Columns: deterrence delta (a check cuts a store's violation chance for 3 months) and
exploitation rho (stores cut violations in proportion to how often they were recently inspected). 200 runs of 36 cycles.

| Policy | no response | delta 0.25 | rho 0.5 | rho 0.9 | delta .25 + rho .5 |
|---|---|---|---|---|---|
| Random | 1.02 | 1.01 | 1.01 | 1.01 | 1.01 |
| FDA follow-up rule | 0.70 | 0.59 | 0.60 | 0.52 | 0.55 |
| Prior violators first (same stores each month) | 1.72 | 0.77 | 0.88 | 0.21 | 0.41 |
| Highest prize, fixed list | 1.78 | 0.79 | 0.90 | 0.22 | 0.42 |
| Highest prize, each store at most once | 1.36 | 1.36 | 1.36 | 1.36 | 1.36 |
| Thompson + random share | 1.54 | 1.27 | 1.34 | 1.17 | 1.13 |
| Thompson + random share + at most once (planned) | 1.23 | 1.22 | 1.22 | 1.22 | 1.22 |

**Reading it:** if stores never react, repeating the best list wins. As soon as they react, fixed lists collapse (below random under strong
reaction) while rotating policies keep 1.2 to 1.4 times random. The planned policy trades a little yield when nothing reacts for robustness when stores do.
The truth in these runs is the model's own estimate, so the simulation shows policy logic, not proof the model is correct.

### 4.6 Gate C: how much random data would we need? (computed)
At Pittsburgh's volume (about 44 checks a year), a 20% random arm is about 9 checks a year. To estimate a violation rate within plus or minus 10 points
needs about 74 random checks (8.5 years); to detect a 1.5x targeting lift with 80% power needs about 200 per arm (23 years at 20%, 4.6 years even if every
check were random). **Conclusion: a Pittsburgh-only random arm cannot estimate base rates in any useful time;** it exists for fairness and unpredictability,
and base rates must come from Synar or a pooled state-level design.

---

## 5. What is infeasible or not done, and why

| Item | Status | Why |
|---|---|---|
| Full 3-index model (stores x days x teams) | Not built | Over the size-limited Gurobi license; unnecessary because the budget binds (ADR 0005) |
| Stackelberg game MILP | Not built | No data on how retailers react to schedules; used as the reason to randomize, tested by simulation |
| Per-tract minimum coverage | Dropped (config value 1 to 0) | 94 tracts vs about 11 checks a quarter |
| Pittsburgh-specific lift | Not testable | 57 test violations in four years (3 in FY2025) |
| Deterrence benefit, cost per prevented violation | Not estimable | No behavior-change data |
| Real "community centers" layer | Partial | Only OpenStreetMap, which is uneven |
| Team base (depot) | Assumed | Downtown placeholder |

---

## 6. Corrections and surprises found along the way

Listed so the reader can see what was caught and what changed because of it.
1. **Four rows in the Pittsburgh export were Tennessee** (South Pittsburg, TN). Excluded; counts moved by one or two (memo 02).
2. **Capacity placeholder was wrong by two orders of magnitude** (200 per week); replaced with 28, then 19, then **11 per quarter** as better data arrived (memo 02).
3. **Stores with two licenses appeared twice** (cigarette plus other tobacco); 392 retail licenses are 345 locations; the planner now deduplicates.
4. **A routing heuristic bug** (it could seed a route with a store farther than one day's drive) was caught by a test and fixed; the Gate B sweep was rerun.
5. **The first schedule put a visit on Thanksgiving;** cycle dates now skip federal holidays.
6. **Thompson strength kappa = 20 was too concentrated** (about 11 distinct stores in 36 cycles); changed to 5 after simulation.
7. **Pittsburgh's violation rate swings by period** (0% FY2013, 1.6% FY2019, about 30-44% FY2022-24). Synar shows purchaser age alone moves rates from 0% to 21%,
   and FDA records have no purchaser attributes, so period effects may be purchaser or inspector mix, not store behavior. The model uses last year's statewide
   rate as a covariate but cannot separate this.
8. **The Paul et al. budgeted PCTSP paper has a 2023 erratum** (the guarantee for the rooted version fails). The project uses the problem as a modeling frame and
   solves it exactly, so nothing depends on the guarantee.

## 7. Assumptions register (what is not measured)

See [assumptions.md](../assumptions.md). The ones that matter most: deterrence strength and weights; kappa; random share; service time (20 minutes) and
team count (2); depot location; the 30-day decision lag; the 26% base rate (Allegheny, cigarettes, 100 outlets); the cost per check ($116 to about $400).
Sensitivity checks run: exposure weights and lambda change which stores make the top 11 (overlap with the baseline list is 6 to 11 of 11), so the list is
**not** insensitive to assumed parameters and should be presented as a decision aid with reasons, not an oracle.

## 8. Fairness and misuse

Scores use store behavior, store type and exposure, not neighborhood demographics. Even so, store types and locations correlate with neighborhoods, and
the exposure term favors areas near schools. The "why us?" file explains every selection; inspectors and DOH should be able to contest it. Do not publish
the schedule in advance (section 4.5 shows why). Do not read the score as a harm estimate in dollars.

## 9. Human checkpoints and open questions

1. Read sections 4.1 and 4.2; decide whether Pennsylvania-wide evidence is accepted as support for a Pittsburgh tool.
2. A second person checks the Synar tables against the PDF; confirm the chart-read history bounds.
3. Review the top 20 stores and tract coverage (`outputs/risk_scores` / `coverage_by_tract.csv`) before issuing any route sheet.
4. Confirm each figure's evidence label before using it in a report.
5. Ask the Department of Health or its contractor: who chooses the stores; purchaser age and race mix by year; what changed in Pittsburgh around FY2013, FY2019 and FY2022;
   whether city-level Synar outlet data exist; the team's base location; actual team count and service time.
6. Place the 44 FDA locations whose city could not be determined (`data/interim/fda_scope_unknown.csv`).
7. Replace placeholders in the "Assumed" rows of the assumptions file as real values arrive.

## 10. Reproduce and inspect

```
uv sync --extra dev --extra should --extra fallback
uv run tobacco-inspect run-all            # refresh, fit, solve, report (about 2 minutes online; faster from cache)
uv run pytest                              # 51 tests
uv run python scripts/build_notebook_02.py # regenerates the annotated notebook
```
Key files: `src/tobacco_inspect/` (model, eval, routing, data, pipeline), `config/default.yaml`, `outputs/` (results), `notebooks/02_risk_and_schedule.ipynb`
(each Proposed Alternative paragraph quoted verbatim before the code that implements it), `docs/sources/proposed_alternative.md` (the quoted source text),
`docs/data-sources.md`, `docs/adr/0005-two-stage-selection-and-routing.md`.
