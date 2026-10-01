# Decision card

Draft from the project proposal and the (LLM-synthesized) roundtable. Confirm each row with the
teaching team / DOH context; items marked ASSUMPTION are not sourced.

| | |
|---|---|
| **Decision** | Which Pittsburgh tobacco retailers to inspect, when, on what route, by which team |
| **Decision maker** | PA Department of Health, Division of Tobacco Prevention & Control (runs the FDA compliance-check contract; ownership since 2010). Class assumption: a DOH-facing tool scoped to Pittsburgh. |
| **Cadence / horizon** | Weekly schedules over a quarter (Mon-Fri only) |
| **Levers** | Which stores, which day, which team, order of visits (later: education visit vs inspection) |
| **Constraints** | Limited resources (budget cap B); daily time budget T (ASSUMPTION 8 h); weekly mileage cap M (ASSUMPTION); weekdays only; each store at most once per horizon; coverage floors (random share; the per-tract minimum was dropped, equity is audited instead, ADR 0005) |
| **Objective** | Maximize total prize: expected compliance leverage (deterrence of sales to minors, exposure near schools, escalation of repeat violators) |
| **Uncertainty** | Violation probability per store (sparse labels, selection bias); ACS margins of error; deterrence effect size (ASSUMPTION) |
| **Data** | See [data-sources.md](data-sources.md) |
| **Scope** | Age-of-sale enforcement. Illicit vape-product enforcement (Act 57 of 2025, Attorney General) is an extension. |

## Formulation (team orienteering with weekdays)

> **Update 2026-09-30 (ADR 0005):** at the capacity the data support (about 11 checks a quarter, about 4 a month) the budget
> binds, not time, so selection comes first and routing second. The 3-index model below is kept for scale-up scenarios only;
> the implemented version uses route slots (team x day) over a pruned candidate set. See
> [process/03_Implementation_Results.md](process/03_Implementation_Results.md).

Maximize sum over teams k, days d, stores i of r[i,d] * y[i,d,k], subject to:

- Each store at most once per horizon: sum over (k,d) of y[i,d,k] <= 1
- Flow conservation and subtour elimination for each (team k, day d)
- Daily time: sum of travel t[i,j] * x[i,j,d,k] + service s[i] * y[i,d,k] <= T
- Weekly mileage <= M; total inspections <= B
- Floors: inspections in stratum S >= m_S (random / stratified coverage)

Prize: `r[i,d] = h_i * p_i + lambda * delta_deterrence_i(state_i)`

- `h_i`: school proximity (NCES), youth density (ACS), historical severity (weights in config)
- `p_i`: predicted violation probability (regularized logistic regression, calibrated)
- `state_i`: Harrington-style enforcement state; a violation raises the next-period prize

Randomization (Stackelberg logic): predictable schedules are exploitable, so store-level
Beta-Binomial posteriors are sampled each cycle (Thompson sampling) and a share of inspections is
reserved for baseline random sampling, which also yields unbiased data to retrain on.

## Two meanings of "agent"
Inspectors are routing agents (team orienteering). Retailers are strategic agents (Stackelberg);
only the latter needs game-theoretic logic.

## Equity and legitimacy
Predict from store behavior and youth-exposure features, not demographic proxies; report coverage
by tract; enforce minimum floors; produce a per-store scoring memo ("why us?").

## Evaluation
Baselines: random, nearest-neighbor, prior-violators-first. Metrics: expected violations per
inspector-hour, coverage in high-youth-exposure areas, route unpredictability, equity gaps, cost per
prevented violation. Tests: backtest (train on year t-1, evaluate on year t, selection-bias caveat
stated) and simulation with synthetic ground truth calibrated to Synar.

## Open questions
How many Pittsburgh retailers are in the license file? (Answered: 467 licenses at 407 locations, 345 retail locations; memo 04.) What are the contract's inspection counts,
team sizes and time limits? Does any local agency share enforcement duties? Who at DOH would own
the tool after the class?

## Scenarios beyond the decision as stated (added 2026-10-01)
The decision above is the budget-capped regime. [Memo 04](process/04_Census_Inspection_Scenario.md) prices a census and [memo 06](process/06_Regime_Comparison.md) compares the two as implementations of one need-responsive regime ([ADR 0007](adr/0007-two-implementations-one-regime.md)). The default remains the capped plan until funding and authority are confirmed.
