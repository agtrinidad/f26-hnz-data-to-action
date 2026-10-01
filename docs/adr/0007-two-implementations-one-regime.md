# 7. Frame the work as two implementations of one need-responsive regime, and stage the decision

Status: accepted (2026-10-01). Amends [ADR 0006](0006-census-as-a-scenario.md); evidence in [memo 06](../process/06_Regime_Comparison.md) and
[notebook 04](../../notebooks/04_regime_comparison.ipynb).

## Context
The team proposed framing the project as a nuanced compliance census of Pittsburgh tobacco sellers, because a full sweep is not extreme in cost (base case about $27,000,
28 team-days, memo 04), while staying responsive to need and while affecting a real compliance regime. The analysis would contrast a "current budget-constrained
implementation" with a "census-optimized implementation."

ADR 0006 had already priced the census and concluded it is not more efficient per check than targeting; it kept the census as a scenario and left the default plan unchanged.
That conclusion stands. What it did not do is judge the two designs as *regimes* (what each does for coverage, learning, equity and compliance) rather than as check-count policies.

## Decision
1. **Frame** the analysis and the recommendation as two implementations of one need-responsive regime, compared on a shared cost-versus-outcome path:
   - *Budget-capped*: about four checks a month, highest need first, a random share, each store at most once a year (the existing pipeline).
   - *Census floor*: every store once a year at random dates with the riskiest first, then a need-weighted second pass updated with the first pass's outcomes.
2. **Need responsiveness is preserved, not diluted:** under the census floor, need decides *when* a store is checked and *whether it is checked again*, never whether it is covered.
   A uniform one-check-per-store design with need only cosmetic was rejected.
3. **Score regimes on violation exposure** (the fall in the violation rate across all stores), not on violations found. Detections fall when deterrence works, so they reward the
   absence of deterrence.
4. **Treat the model as not the truth.** Truth is the model's probability compressed and optionally noised, calibrated to the observed replay lift (1.47). Results are reported across the
   unidentified hidden heterogeneity; the baseline is the conservative case (none).
5. **Price the capped regime as today's running program** (no one-time commissioning); the census pays commissioning. Both bottom-up and top-down costs are shown.
6. **Do not claim** that a census is more efficient per violator, that it reduces underage sales, or that one passed check shows a store is compliant.
7. **Stage the decision.** The default plan remains the capped targeted plan until DOH confirms funding, authority and unit costs (ADR 0006 unchanged on this point). The recommended
   next step is a one-year census-floor *learning* pilot with randomized timing, after which the default is decided on measured evidence.

## Why
- The two designs differ in constraint (a cap vs a coverage guarantee), not in logic, so one frontier compares them honestly; the earlier notebooks sampled it at five points.
- Under a linear deterrence response the capped plan is modestly ahead per dollar, and the census reduces the violation rate far more in total. Cost-effectiveness favors the census only if
  the visibility effect is convex (break-even shape about 1.17). No data identify that shape, so the choice rests on an unknown that a randomized-timing pilot can measure.
- A smarter second pass is worth building only if stores differ in ways the model misses (break-even hidden sigma about 0.64); otherwise the model's ranking is as good. That too is
  learnable from the first pass.
- A census measures attempts, not compliance: one purchase is a coin flip. It supports a city rate and coverage, not store-level verdicts.
- Equity: the census treats tracts proportionally and leaves no store unchecked; the capped plan leaves about 86% unchecked in a year and sends a somewhat larger share to the highest-poverty quartile.

## Alternatives considered
- *Replace ADR 0006.* Rejected: its evidence and cost model are the foundation here, and the team accepted it on 2026-09-30.
- *Adopt the census as the default now.* Rejected: funding, authority, purchaser supply and unit costs are unconfirmed, and the compliance benefit is assumed.
- *Add a light-touch (non-undercover) tier for low-need stores.* Deferred: needs cost and effectiveness assumptions with no data behind them.
- *Score on detections.* Rejected (see decision 3).

## Consequences
- New scenario command `tobacco-inspect regime`, `pipeline.regime`, `eval/regime.py`, notebook 04, memo 06, outputs `outputs/regime_*.csv`.
- `simulate.effective_p` is now the one response model (adds `gamma`, `gamma_power`); `simulate.run` also reports exposure. Memory and window are in months in every analysis.
- Config gains `regime:` (observed lift, floor months, second-pass share), `census.targeted_lift` and `census.award_dollars`; the $116 and 1.5 constants are read from config.
- Revisit when: DOH confirms the funding path and authority; a pilot or other evidence identifies the visibility response; actual unit costs replace the assumed ones.
