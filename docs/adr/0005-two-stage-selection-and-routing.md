# 5. Selection first, routing second; no 3-index MILP and no Stackelberg MILP

Status: accepted (2026-09-30), supersedes the 3-index formulation in docs/decision-card.md

## Context
The decision card formulated team orienteering with weekdays: stores x days x teams. Real capacity turned out to be
about 11 inspections a quarter for the City of Pittsburgh (about 4 a month), with 40 team-days available a month and about
15 stops per team-day. The budget binds, not time. The full model also exceeds the size-limited pip Gurobi license
(about 2,000 variables) and the data say nothing about how retailers respond to a schedule.

## Decision
1. Choose stores by prize (risk x exposure + deterrence term) with Thompson-sampled risk, a reserved random share and
   at-most-once per horizon.
2. Route the chosen stores with a route-slot team-orienteering MILP (`solve_team_orienteering`) over a pruned candidate set
   (top 30 by sampled prize plus random picks). HiGHS is the automatic fallback.
3. Keep a ranked+batched heuristic (`plan_ranked_batched`) as the comparator and the default recommendation when time is not scarce.
4. Do not build a Stackelberg MILP. Use the Stackelberg and bounded-rationality idea as the rationale for randomization and test it
   by simulation with assumed behavioral parameters.
5. Replace the per-tract coverage floor with a coverage audit: about 94 tracts against about 11 checks a quarter makes a floor arithmetically infeasible.

## Consequences
- Gate B (scripts and notebook 02): at 4 to 8 stores a month the MILP and the heuristic collect identical prize; the MILP gains
  roughly 4-11% only when time is scarce (budget 15+ with 4-hour or shorter days or one or two route slots).
- The system is simple to hand over: a ranked, randomized list works without a solver.
- Simulation results depend on assumed deterrence (delta) and exploitation (rho); they must always be labeled as such.
- If the real budget is later much larger (statewide scale), the same code applies with larger candidate pools and HiGHS.
