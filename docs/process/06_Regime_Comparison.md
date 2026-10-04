# Memo 06: One compliance regime, two implementations (budget-capped vs census floor)

**Project:** Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA
**Date:** 2026-10-01. **Scope:** City of Pittsburgh limits. **Companions:** [memo 03](03_Implementation_Results.md) (the targeted plan),
[memo 04](04_Census_Inspection_Scenario.md) (the census priced), [memo 05](05_Mathematical_Formulation.md), [notebook 04](../../notebooks/04_regime_comparison.ipynb) and its
[executed HTML copy](06_Regime_Notebook_Executed.html), [ADR 0007](../adr/0007-two-implementations-one-regime.md), [assumptions](../assumptions.md).

Written for the project team and for anyone deciding whether to fund a city-wide sweep. It can be read without the code. Every number is reproduced by
`uv run tobacco-inspect regime` (writes `outputs/regime_*.csv`) and by the notebook.

---

## 1. The short answer

The proposal was to treat enforcement as a compliance census of Pittsburgh sellers, keep it responsive to need, and contrast it with today's budget-constrained implementation.

**It holds up as a regime design and not as an efficiency claim.** Notebook 03 already showed that a census catches no more violations per check than random sampling and fewer than
targeting. That still holds. What the census adds is coverage, learning and legitimacy, and a different job for the optimizer. Whether it also improves *compliance* is unknown, and the
answer turns on one number nobody has: the shape of how enforcement visibility changes seller behavior.

| Question | Answer | Label |
|---|---|---|
| Can need-responsiveness survive a census? | Yes: need sets *when* each store is checked and *whether it is checked again*, not whether it is covered | design |
| More violators per dollar? | No. Targeting is cheaper per violator at every budget below the census; the census step is the costliest per added violator (about $836 vs $206 to $333 along the targeted path) | simulated, cost assumed |
| What does it uniquely buy? | Every store and the whole highest-need decile checked with certainty; the city rate to within a standard error of about 2.3 points; an unbiased label for every store | exact / simulated |
| Better compliance? | **Unknown.** Under any assumed deterrence it lowers the violation rate more in total (about 7 to 8 times the capped plan), but per dollar it wins only if visibility deters *convexly* (break-even shape about 1.17) | assumed |
| Is a smarter second pass worth it? | Only if stores differ in ways the model misses (break-even hidden heterogeneity about 0.64); otherwise the model's own ranking is as good | simulated |
| Cannot be claimed | That a census reduces underage sales; that a store that passed once is compliant | none |

**Recommendation (ADR 0007).** Keep the capped targeted plan as the default until funding and authority are confirmed. Propose a one-year census-floor *learning pilot* with randomized
timing and a randomized second pass, because it measures the three unknowns that decide the default. Then choose.

---

## 2. What changed in the framing

Notebook 03 asked "what would a census cost and catch?" and answered in check counts. The proposal changes the question to "what regime are we running?" That shifts four things:

1. **From a scenario to a design.** Both options share the risk model and the need score; they differ in the constraint (a cap on checks vs a guarantee of coverage). We compare them on one cost-versus-outcome path.
2. **From detections to exposure.** A regime succeeds if the violation rate falls. Violations *found* fall when deterrence works, so earlier simulations scored the wrong thing for this purpose.
3. **From certainty of the model to humility about it.** The targeted line in memo 04 assumed the model's probabilities were exact. The observed replay lift (1.47) is below the model's own (1.67), so the truth is less spread than predicted, or noisier.
4. **From "optimize the route" to "what do we learn?"** At about four checks a month, routing has nothing to optimize (memo 03, Gate B). A coverage guarantee gives the optimization layer real work (a labor problem, memo 04) and gives the *data* real work: an unselected label for every store.

A census also raises a tension the original framing hides. Memo 05 wants every store's probability of being checked strictly between 0 and 1 so sellers cannot predict the schedule (Stackelberg logic).
A census sets it to 1. The design keeps unpredictability where it can: random dates and sequence, a randomized (Thompson) second pass, and no fixed list.

## 3. Findings

### 3.1 The model is not the truth (new)
- The model's top-decile lift is 1.67; the replay observed 1.47 (interval 1.23 to 1.77). Two explanations cannot be separated with today's data: an overconfident model (slope 0.69 when there is no hidden spread), or hidden store-level
  differences (up to sigma 1.74 would alone explain the gap).
- We calibrate the slope to the observed lift for each hidden-sigma value (0, 0.5, 1.0, 1.5) and report across them. The baseline is sigma 0, the conservative case for the second pass.

### 3.2 What each step up buys (frontier; `outputs/regime_frontier.csv`)

| Policy | Checks | Distinct violators | Bottom-up cost | Highest-need decile covered |
|---|---|---|---|---|
| Targeted | 44 (today's city volume) | 16.3 | $3,285 | 100% |
| Targeted | 86 | 30.9 | $6,298 | 100% |
| Targeted | 276 | 79.1 | $19,651 | 100% |
| Census floor | 345 | 88.0 | $27,096 | 100% |
| Census + adaptive second pass (25%) | 431 | 100.1 | $33,363 | 100% |
| Simple random (for contrast) | 276 | 70.4 | $19,684 | 80% |

- Marginal dollars per added violator along the targeted path rise from about $206 to $333; the step to the census is $836 (commissioning is one-time and falls on this step); second passes add at about $340 to $526.
- A targeted list covers the whole highest-need decile with about 34 checks; random sampling reaches it only at full coverage.
- The capped regime is priced as the running contracted program, with no commissioning cost. If it is charged commissioning too, the capped checks cost about $134 each instead of $75 (the function has a switch).

### 3.3 What first-pass labels are worth (`outputs/regime_second_pass.csv`)
Second pass of 86 checks, baseline truth:

| Rule | Violations in 2nd pass | Repeat violators | New distinct violators |
|---|---|---|---|
| Random | 21.7 | 6.2 | 15.5 |
| Model's p only (labels ignored) | 31.1 | 11.4 | 19.8 |
| Thompson posterior (randomized) | 26.6 | 14.0 | 12.6 |
| Posterior mean | 28.0 | 21.7 | 6.3 |
| Violators first (FDA follow-up rule) | 25.0 | 24.1 | 0.9 |

- When hidden heterogeneity is small, ranking by the model alone is as good or better. Updating on first-pass outcomes overtakes it at about sigma 0.64.
- The rule should follow the objective: re-checking violators serves FDA escalation (repeat violators) and nearly never finds new ones.

### 3.4 Does the regime change compliance? (assumed response; `outputs/regime_response_grid.csv`, `regime_shape_sweep.csv`)
Reduction is the fall in the city's mean violation probability versus no enforcement, averaged over the year.

| Assumed response | Capped: reduction | Census floor: reduction | Capped per $1k | Census per $1k |
|---|---|---|---|---|
| Store-specific, 25% for 3 months | 0.9 pts | 6.9 pts | 0.25 | 0.21 |
| Store-specific, 50% for 6 months | 3.0 pts | 23.2 pts | 0.85 | 0.70 |
| Plus linear visibility (gamma 0.3) | 2.4 pts | 19.5 pts | 0.66 | 0.58 |

- No response in the grid gives the census an efficiency edge: the capped plan is about 20% ahead per dollar because its checks are better aimed, and the census costs about the same per check once commissioning is counted.
- The visibility shape decides it. At exponent 0.5 (first checks matter most) the capped plan is 2.7 times as cost-effective; at 2 (a credibility threshold) the census is 1.5 times as cost-effective. Break-even is about 1.17.
- Timing the first pass risk-first gains about a point of reduction only for a long (6-month) strong response, and nothing for a 3-month one.

### 3.5 Who is checked (`outputs/regime_equity.csv`)
- Budget-capped: about 86% of stores unchecked in a year; 26.0% of checks in the highest-poverty quartile, which holds 21.7% of stores.
- Majority-minority tracts (27 of 94; 25.2% of stores): the capped regime sends 32.2% of expected checks there, 1.39 times the per-store rate of other tracts; the census floor sends 26.6%, a ratio of 1.07. The capped skew comes from the risk score, which uses no demographics but favors outlet types and school-adjacent areas that correlate with these tracts. Descriptive only; this does not show that the checks are unwarranted.
- Census floor: every store checked; 22.4% of checks in that quartile. (ACS poverty has wide margins; 42% of retail licenses sit in tracts with unreliable youth data, so gaps are indicative.)

## 4. Decisions made, with the alternatives rejected

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D1 | Amend through ADR 0007; leave ADR 0006's evidence in place | Replace 0006; or a separate analysis with no ADR | The team accepted 0006; two ADRs that disagree on the default would mislead |
| D2 | Census-optimized = census floor + need-weighted adaptive second pass | Pure uniform census; or a light-touch tier for low-need stores | A uniform design makes need cosmetic; a light-touch tier needs cost and effect assumptions with no data |
| D3 | Score regimes on violation exposure | Score on violations found | Detections fall when deterrence works |
| D4 | One response model (`simulate.effective_p`) for every analysis; months as the unit | Keep notebook 02's cycle-based delta/rho and notebook 03's fixed 3-month window | They disagreed; the 3-month window and `memory = 3` cycles only happened to match |
| D5 | Truth = compressed and optionally noised model, calibrated to the observed lift, swept over hidden sigma | Model is truth (optimistic); or noise only | Noise-only made first-pass labels look far more valuable than the data justify (see section 5) |
| D6 | Baseline hidden sigma = 0 | A "central" sigma | No data identify sigma; the baseline should not manufacture value for the second pass |
| D7 | Capped regime priced without commissioning; census with it | Charge both, or neither | Today's program is contracted and trained; a switch is provided |
| D8 | Visibility deterrence (`gamma`) with a shape (`gamma_power`) | Linear only | In a linear world both regimes tie per dollar, hiding the actual crux |
| D9 | Staged recommendation: default unchanged, pilot a learning census | Adopt the census now; or reject it | Funding and authority unconfirmed; the decisive unknowns are measurable by the pilot |
| D10 | Computation in `pipeline.regime`, notebook consumes it | Notebook-only code | Every cited number then traces to `outputs/regime_*.csv` |

## 5. Corrections and surprises (what changed during the work)

- **A first truth model overstated the value of labels.** Adding logit noise only (sigma 1.74) to match the observed lift implied huge hidden differences between stores, so first-pass labels looked very valuable.
  The lift is just as well explained by an overconfident model with no hidden spread. We now calibrate for each sigma and report the range. The headline finding for the second pass changed from "adaptive wins" to "it depends on hidden heterogeneity".
- **A cost signal was an artifact.** Scattered targeted lists first looked about 70% more expensive per check than the census. That came entirely from charging commissioning to the small program. Without it, per-check bottom-up cost is about $71 to $75 for every partial policy (the census is about $78 because it carries commissioning). We did not report it.
- **Adaptive is not better on every objective.** An adaptive second pass finds more repeat violators and violations but *fewer new distinct violators* than a random second pass.
- **The census does not win per dollar even though it lowers the violation rate more in total.** This held in every linear-response case; only a convex visibility effect reverses it.
- **Notebook 03 hardcoded constants** ($116, $400, 1.5 lift, the $1,159,731 award); they now come from config. The census outputs (`outputs/census_*.csv`) are byte-identical after the change.
- **Memo 05 section 7, item 7** said the optimizer "earns its keep" in the census scenario, but memo 04 splits a single tour and does not use the MILP. Reworded.
- **The `stratified` row of memo 04's capture table has the same exact value as simple random sampling** (proportional strata add nothing to the expectation); only its simulation differs.

## 6. Limits

- Every deterrence number is assumed: store-specific effect and memory, general deterrence and its shape. A check's effect on behavior is not identified by any of our data.
- Hidden store-level heterogeneity is not identified; results are shown across a range.
- Truth is built from the model's own calibrated probabilities (calibrated to Synar's 26% Allegheny rate, interval 17% to 35%); the identities hold for any probabilities, the levels do not.
- Purchaser availability, store hours, license turnover (licenses expire each February) and penalties are not modeled.
- The capped regime visits each store at most once a year; its repeat-violator count is zero by construction and should not be read as a regime difference.
- The census year is one snapshot of the license file.

## 7. How to learn the unknowns (the pilot)

Randomize which routes are checked in which month, and randomize the second pass. A second-pass check of stores last checked early versus late in the year is then a dose-response in
time since last check: the first real evidence on the store-specific effect and its memory. The first pass also reveals how much store outcomes vary beyond the model (hidden
heterogeneity) and gives the unbiased city rate. Whether visibility effects are convex needs a design with variation across places or times in how many stores are checked; the
pilot alone cannot show it, which is a reason to keep that claim out of any funding case.

## 8. Human checkpoints

1. Agree the second-pass objective: repeat violators (FDA escalation), new violators, or exposure near schools.
2. Replace assumed costs with DOH or contractor figures (this inherits memo 04's list).
3. Confirm funding and authority for a city-wide pilot, and the share of the FDA contract's targets it would use.
4. Confirm whether census data can serve the Synar random-sample requirement (unverified), and whether Allegheny County Health Department rather than the state owns enforcement in the city (unverified).
5. Decide whether a one-year learning pilot is worth about $27,000 to $33,000 base-case (about $13,000 to $66,000 across the bands in memo 04).
6. Confirm each figure's label before reuse.

## 9. Reproduce and inspect

```
uv run tobacco-inspect regime                       # writes outputs/regime_*.csv (about 20 seconds)
uv run python scripts/build_notebook_04.py          # regenerates notebooks/04_regime_comparison.ipynb
uv run pytest                                       # 88 tests
```
Key files: `src/tobacco_inspect/eval/regime.py` (truth model, frontier, second pass, year simulation, equity), `eval/simulate.py` (`effective_p`, the shared response model),
`pipeline.regime`, `config/default.yaml` (`regime:` section).
