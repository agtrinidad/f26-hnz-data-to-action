# Memo 07: Marginal value, break-even deterrence and what-ifs

**Date:** 2026-10-03. **Scope:** City of Pittsburgh limits. **Plan:** [2026-10-03-marginal-value-plan](../claude-plans/2026-10-03-marginal-value-plan.md).
**Decision record:** [ADR 0008](../adr/0008-marginal-cost-headline.md). **Builds on:** [memo 04](04_Census_Inspection_Scenario.md) (cost), [memo 05](05_Mathematical_Formulation.md), [memo 06](06_Regime_Comparison.md) (regimes).
**Reproduce:** `uv run tobacco-inspect solve && uv run tobacco-inspect report && uv run tobacco-inspect value` (about 20 seconds for `value`; needs `fit` first).
Every number below is in `outputs/valuation_*.csv`. Labels: sourced / proxied / assumed / simulated. Nothing here is evidence that deterrence exists.

## 1. Decisions made

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| V1 | Headline cost is **marginal**: bottom-up cost of the checks DOH adds to a running program. Top-down (award per check) is a sensitivity row | Headline the full cost ($40K to $138K); or show both equally | The decision on the table is whether DOH adds work to a contract that already runs, so the relevant cost is what the extra work costs. Full cost answers a different question (a new funder starting a program) |
| V2 | Compare every census variant with today's capped program (44 city checks a year, no commissioning), and report the **increment** | Report census cost alone | A reader who sees "$27K" assumes it is new money; the increment over today's spend is $23.8K (floor) or $30.1K (floor plus second pass) |
| V3 | Assert **no dollar value of a prevented underage sale** | Pick a value from the literature | None is sourced for this project. The table gives the *price* of each prevented unit, and the reader compares it with their own valuation |
| V4 | Break-even is expressed as "what must the incremental dollars buy" under each assumed response, not as a crossing in the deterrence size delta | Solve for a break-even delta | In every linear response the two regimes scale together, so delta alone never flips the ranking (section 4). The decisive unknown is the visibility *shape* (about 1.17, memo 06) |
| V5 | Opportunity cost is stated as a comparison set and left unanswered | Argue the checks are better spent elsewhere | The data cannot say where a statewide check is worth more |
| V6 | What-if is a structured sweep over teams and day length using existing machinery, labeled as such | Build or call an LLM-driven OptiGuide interface | Same questions answered with fewer moving parts |
| V7 | **Keep the uniform 4 stores per cycle (12 visits a quarter) everywhere**; revert the exact 4/4/3 allocation | Keep 4/4/3 in the saved schedule only; or rerun every analysis with 4/4/3 | One convention across the schedule, Gate B, policy simulation, census and regime scenarios and notebooks 02 to 04. The visit it saves is smaller than the uncertainty in the 44-a-year proxy (section 6) |
| V8 | Reframe the model as a **budgeted selection problem with an optional routing layer** | Keep "prize-collecting routing problem" | Gate B shows the optimizer equals the heuristic at the funded budget; budget binds, time is slack |

## 2. What was executed

1. **Ported Abigail Torbatian's reconciliation patch, then reverted its allocator.** The Windows-path check stays. The exact 4/4/3 split was applied, the schedule was regenerated (4/4/3, 11 visits), and then the split was reverted on request so the whole project uses one convention. The schedule was regenerated again under the uniform 4: 12 visits, 4 stores per cycle, route minutes 113, 112 and 108, 9 of 94 tracts, 20% of inspections in the highest-poverty quartile. The regenerated files are identical to the committed ones, so `outputs/schedule_*.csv`, `why_us.csv`, `coverage_by_tract.csv` and `equity_summary.json` show no change.
2. **Added** `eval/valuation.py`, `pipeline.valuation`, `tobacco-inspect value`, a `valuation:` config block and `tests/test_valuation.py` (8 tests; the 4/4/3 test from the ported patch was dropped with the allocator). The module reuses `regime()` (frontier, response grid, costs) and `build_instance`; it recomputes only the lambda robustness and the what-if sweep.
3. **Checks:** full suite 96 passed (88 before, plus 8 new); `ruff check` clean; census and regime outputs untouched (`value` calls `regime(write=False)`).

## 3. Marginal cost (headline)

`outputs/valuation_marginal.csv`. Base case, bottom-up, compared with today's capped program (44 checks, $3,285). Costs proxied/assumed; violators simulated.

| Option | Checks | Bottom-up total | **Incremental $** | Incremental checks | $ per added check | Added distinct violators | $ per added violator |
|---|---|---|---|---|---|---|---|
| Census floor | 345 | $27,096 | **$23,811** | 301 | $79 | 71.7 | $332 |
| Census floor + adaptive second pass (86) | 431 | $33,363 | **$30,078** | 387 | $78 | 83.8 | $359 |

- **Full-cost sensitivity (not the headline):** the same increments priced at DOH's award per check ($116 to $400) are $34,900 to $120,400 (floor) and $44,900 to $154,800 (floor plus second pass).
- The increment is about 2.6% of the $1,159,731 annual award and about 8 times today's city volume in checks.
- **Not a contradiction with memo 06:** its $836 per added violator is the *last step* of the targeted path into the census; $332 and $359 average over the whole move from 44 checks.

## 4. Break-even deterrence (assumption-driven)

`outputs/valuation_break_even.csv`. Incremental dollars $29,779 (the year simulation prices the capped plan at 48 checks a year, as in memo 06). "Required" is what the census's extra dollars must remove to match the capped plan's average points per dollar; "achieved" is the census's extra reduction in violation exposure. Simulated, response assumed.

| Assumed response | Capped reduction | Census reduction | Required (pts) | Achieved (pts) | Achieved / required | $ per point | $ per prevented violation |
|---|---|---|---|---|---|---|---|
| none | 0% | 0% | 0 | 0 | n/a | n/a | n/a |
| store-specific, 25% for 3 months | 0.9% | 6.9% | 7.4 | 6.0 | 0.81 | $4,974 | $5,655 |
| strong store-specific, 50% for 6 months | 3.0% | 23.3% | 25.3 | 20.2 | 0.80 | $1,474 | $1,676 |
| plus linear visibility (gamma 0.3) | 2.4% | 19.5% | 19.6 | 17.1 | 0.88 | $1,739 | $1,978 |

How to read it:
- The census always lowers exposure more in total, but delivers 80% to 88% of the capped plan's per-dollar rate in every linear case. A prevented violation costs about $1,700 to $5,700 of marginal spend. **If a prevented sale to a minor is worth more than that to DOH, the extra spend pays under that response; if not, it does not.** No response means no benefit at any price.
- "Prevented violation" is a violation-equivalent: reduction times the expected violations in one full pass of checks (88). It is not a count of sales to minors.
- **Why there is no break-even delta:** with a linear response both regimes scale with delta, so the 80% to 88% ratio barely moves. What can reverse the ranking is convex visibility (break-even shape about 1.17; `valuation_restated.csv`) or hidden store heterogeneity (break-even about 0.64, memo 06). The pilot can measure both; neither is known today.

## 5. Opportunity cost, what-ifs and robustness

**Opportunity cost** (`valuation_opportunity.csv`; the funder's comparison set, deliberately unanswered):
- Pittsburgh is about 1.5% of Pennsylvania's roughly 2,900 published checks a year (44 of 2,900). A 345-check census equals 11.9% of the state total and 7.8 times today's city volume.
- The increment ($30,078) buys about 75 to 259 checks statewide at the award-per-check rates, against 387 added city checks at about $78 each. Whether a check is worth more here than elsewhere is not identified by our data.

**What-if** (`valuation_whatif.csv`; a structured sweep, not the OptiGuide tool):

| Question | Answer |
|---|---|
| Census floor with 1, 2, 4 or 8 teams (8-hour day) | 28 team-days; 28, 14, 7 or 4 workdays (1.3, 0.7, 0.3 or 0.2 months); cost unchanged at $27,096 |
| Census floor with a 4-hour day | 61 team-days, $28,868 (+$1,772); 2 teams take 31 workdays (1.5 months) |
| Capped plan: add a third team, or shorten the day to 4 hours | No change. The longest monthly route is 113 minutes and fits in either day; the budget binds, not time (Gate B) |

**Robustness of the prize weight on deterrence** (`valuation_robustness.csv`; deterministic top 11, no Thompson noise). Prior violations enter the score through p, through severity in h and through the deterrence term, so this tests the double-counting concern.

| lambda | Overlap with baseline (of 11) | Distinct tracts | Mean p | Mean h |
|---|---|---|---|---|
| 0 | 6 | 10 | 0.442 | 0.470 |
| 0.25 (baseline) | 11 | 11 | 0.412 | 0.446 |
| 0.5 | 11 | 11 | 0.412 | 0.446 |

Dropping the deterrence term changes 5 of the 11 picks; doubling it changes none. The list is sensitive to whether the term exists, not to its size. The report should show the lambda = 0 row and say so. The hidden-sigma sweep is not rerun: cite `regime_second_pass.csv` and memo 06 (maximum sigma consistent with the observed lift is 1.74).

## 6. Corrections, surprises and known inconsistencies

- **11 vs 12 visits (resolved by convention).** The proxy budget is 11 checks a quarter (44 a year); the plan rounds that up to 4 stores in each of 3 cycles, so every plan-level analysis runs 12 a quarter (48 a year). The frontier's capped row uses the 44-a-year proxy and the year simulation uses 48, which is why the incremental dollars differ slightly between the marginal table ($30,078 over 44 checks) and the break-even table ($29,779 over 48). Both are labeled. State the rounding in the report.
- **Delta cannot flip the ranking** (V4). I started from a break-even-delta design and dropped it after reading the response grid.
- **Per-check cost is nearly flat** (about $78 across the move), so the marginal and average views agree; the difference between the framings is the *baseline subtracted*, not the unit cost.
- **The draft says 345 checks is "about 13%" of PA's published checks**; 345 / 2,900 is 11.9%. Check which published count the draft used before citing either.
- The executed notebook 02 HTML is current: it already shows 12 visits, which matches the convention.

## 7. Limits

- Every deterrence number is assumed; costs are bottom-up under assumed wages, admin time and drive factors (`docs/assumptions.md`).
- The break-even table prices a violation-equivalent, not a youth sale prevented, and ignores penalties, retailer exit, purchaser availability and license turnover.
- The capped what-if reads monthly route minutes from one seeded schedule.
- Opportunity cost uses one statewide count (about 2,900) and an award split that is itself a range.

## 8. Human checkpoints

1. Confirm the marginal headline and that today's capped program (44 checks, no commissioning) is the right baseline.
2. Supply or choose a value for a prevented violation or sale; the table converts it into a go/no-go.
3. Replace assumed cost inputs with DOH or contractor figures (inherits memo 04's list).
4. State the rounding (11 budgeted, 12 planned) in the report, and say whether the 44-a-year proxy or the 48-a-year plan is the baseline for each table.
5. Confirm the statewide published-check count and the 13% vs 11.9% figure.
6. Confirm funding and authority (DOH vs Allegheny County Health Department) and whether census data can serve Synar's random-sample requirement (both unverified).
