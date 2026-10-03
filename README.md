# Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA

CMU 94-867 *From Data to Action* (Fall 2026) group project.
Team: Abigail Torbatian (atorbati@andrew.cmu.edu), Avery Trinidad (agtrinid@andrew.cmu.edu),
Anastasia Harouse (aharouse@andrew.cmu.edu).


> **Reconciliation note (2026-10-01, updated 2026-10-03).** A review against the final-report draft found two issues. (1) Windows-style absolute paths are now rejected cross-platform (fixed). (2) The 11-visit quarterly budget is rounded up to 4 stores in each of three cycles, so the saved schedule holds 12 visits. An exact 4/4/3 allocation was tried and reverted on 2026-10-03: every other analysis (Gate B, policy simulation, census and regime scenarios, notebooks 02 to 04) assumes a uniform 4 per cycle, and one internally consistent convention matters more than one store. The 12-visit schedule is the documented convention (about 48 checks a year against a 44-a-year proxy).

**Scope.** City of Pittsburgh limits (Census place polygon), not the wider postal Pittsburgh area.

**Decision question.** How can the PA Department of Health prioritize, schedule and execute retail
tobacco inspections in Pittsburgh to maximize collective compliance under a limited inspection
budget? We model it as a budgeted prize-collecting TSP (team orienteering with weekdays and time
budgets), with a predicted-risk prize, randomized coverage (Thompson sampling), and
Harrington-style escalation. Full statement: [docs/decision-card.md](docs/decision-card.md).

> **Status: data and optimization stages implemented.** `tobacco-inspect run-all` refreshes data, fits the risk model,
> plans monthly cycles and writes route sheets, "why us" reasons and an equity audit. Start with the plain-language
> [implementation memo](docs/process/03_Implementation_Results.md); sources are catalogued in
> [APA format](docs/data-sources-apa.md); the annotated notebook is `notebooks/02_risk_and_schedule.ipynb`. A separate scenario asks what checking *every*
> licensed location in a year would cost and capture: [census memo](docs/process/04_Census_Inspection_Scenario.md) and
> `notebooks/03_census_vs_sampling.ipynb`. The two options compared as implementations of one need-responsive regime (budget-capped vs census floor):
> [regime memo](docs/process/06_Regime_Comparison.md), [ADR 0007](docs/adr/0007-two-implementations-one-regime.md) and `notebooks/04_regime_comparison.ipynb`.
> See the checklist below.

## Setup

Requires Python 3.11-3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev          # add --extra should for statsmodels/matplotlib/folium
uv run pytest
```

**Solver.** Gurobi is the primary solver (course-provided). `gurobipy` installs from PyPI with a
size-limited license that covers small instances; for full-size runs use your academic license
(set `GRB_LICENSE_FILE`; never commit `gurobi.lic`). To run without Gurobi, install the
`fallback` extra (`uv sync --extra fallback`) and set `solver: appsi_highs` in
`config/default.yaml`.

## Running (target execution order)

All commands read `config/default.yaml`; all paths are relative to the repo root.

```bash
uv run tobacco-inspect refresh    # 1. download + clean sources -> data/raw, data/interim
uv run tobacco-inspect fit        # 2. risk model p_i           -> data/processed
uv run tobacco-inspect solve      # 3. schedule                 -> outputs/
uv run tobacco-inspect report     # 4. route sheets + audits    -> outputs/
uv run tobacco-inspect run-all    # 1-4 in order
```

Exploration notebooks live in `notebooks/` (run in numeric order). All four steps are implemented. Outputs land in `data/processed/` and `outputs/`.

## Repository layout

| Path | Contents |
|---|---|
| `src/tobacco_inspect/` | Package: `config`, `data/`, `routing/`, `model/`, `eval/`, `cli` |
| `config/default.yaml` | Capacity, solver, prize weights, coverage floors (edit here, not in code) |
| `data/` | `raw/` (git-ignored), `interim/`, `processed/` (small, committed so the zip runs offline) |
| `notebooks/` | Analysis notebooks (outputs stripped) |
| `tests/` | pytest suite |
| `docs/` | Decision card, data sources, runbook, assumptions, LLM log |
| `scripts/package_submission.py` | Builds the Gradescope zip; `--check` verifies portability |

## License

MIT, see [LICENSE](LICENSE).
