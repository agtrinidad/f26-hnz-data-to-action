# 8. Headline the marginal cost of the census regime and assert no dollar value of a prevented sale

Status: accepted (2026-10-03). Extends [ADR 0006](0006-census-as-a-scenario.md) and [ADR 0007](0007-two-implementations-one-regime.md); evidence in [memo 07](../process/07_Marginal_Value_and_Framing.md).

## Context
ADR 0006 priced the census at about $27,000 (range $13,000 to $66,000 bottom-up; $40,000 to $138,000 top-down). The 10-02 critical review noted that readers will take a tenfold spread as sloppiness
and that the benefit side (fewer sales to minors) is missing from every headline.

## Decision
1. **Headline marginal cost.** The decision is whether DOH adds work to a running, contracted program, so the cost that matters is what the additional checks cost, compared with today's capped program (44 checks a year, no commissioning). Base case: about $23,800 for the census floor and $30,100 with a second pass. Top-down (award per check) is a labeled full-cost sensitivity.
2. **Assert no dollar value of a prevented sale.** None is sourced. Report the price of each prevented violation-equivalent under each assumed deterrence response (about $1,700 to $5,700 of marginal spend) and let the reader compare it with their own valuation.
3. **Keep the default unchanged and the pilot staged** (ADR 0007). This ADR changes the cost framing, not the recommendation.
4. **Keep the uniform 4 stores per cycle (12 visits a quarter) everywhere.** An exact 4/4/3 split was tried and reverted so every analysis shares one convention; memo 07 states the 11-budgeted, 12-planned rounding.

## Consequences
- The report leads with the increment and says why. Full cost appears once, as a sensitivity.
- The break-even depends on assumed responses and on the visibility shape (about 1.17); it is not evidence that the census prevents anything.
- Opportunity cost (Pittsburgh is about 1.5% of PA published checks; the census is about 12%) is named but not answered.

## Revisit when
DOH or the contractor supplies real cost figures, a value per prevented sale is agreed, or the pilot measures a store-specific effect and its memory.
