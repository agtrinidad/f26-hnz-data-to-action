# Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA

CMU 94-867 *From Data to Action* (Fall 2026) group project.
Team: Abigail Torbatian (atorbati@andrew.cmu.edu), Avery Trinidad (agtrinid@andrew.cmu.edu),
Anastasia Harouse (aharouse@andrew.cmu.edu).

**Decision question.** How can the PA Department of Health prioritize, schedule and execute retail
tobacco inspections in Pittsburgh to maximize collective compliance under a limited inspection
budget? We model it as a budgeted prize-collecting TSP (team orienteering with weekdays and time
budgets), with a predicted-risk prize, randomized coverage (Thompson sampling), and
Harrington-style escalation. Full statement: [docs/decision-card.md](docs/decision-card.md).

> **Status: scaffold.** The repository structure, config, CI and a toy optimization test exist.
> The data pipeline, risk model and full scheduling model are stubs (`NotImplementedError`).
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

Exploration notebooks live in `notebooks/` (run in numeric order). Currently every subcommand
exits with "not implemented yet".

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
