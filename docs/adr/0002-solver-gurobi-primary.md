# 2. Gurobi as the primary solver, HiGHS as fallback

Status: accepted (team decision, 2026-09-28)

## Context
Gurobi is the solver provided and taught in the course (Weeks 1-2), and the team has academic access.
The project roundtable warned that a proprietary solver is a licensing risk if a city inherits the
tool; a few hundred nodes is small enough for open-source solvers (HiGHS, CBC, OR-Tools).

## Decision
Model in Pyomo. `solver: gurobi` is the default in `config/default.yaml`. HiGHS is supported
(`solver: appsi_highs`, `fallback` extra) and exercised by the smoke test when Gurobi is unavailable.
No Gurobi-specific features (callbacks, `gurobipy` model API) in the core model.

## Consequences
- Fast development and course alignment now; the solver can be swapped by config later.
- Handoff notes in the runbook state that Gurobi needs a license outside academia.
- Benchmark Gurobi vs HiGHS on the real instance and record solve times in the report.
- Stretch item `gurobi-machinelearning` would tie the model to Gurobi; we predict then optimize instead (ADR 0003).
