# Runbook (for whoever inherits this)

Written for a new maintainer with basic Python. Update as the pipeline gets built.

## Install
```bash
uv sync --extra dev
uv run pytest
```
Gurobi: set `GRB_LICENSE_FILE` to your license, or use the fallback (`uv sync --extra fallback`, then
`solver: appsi_highs` in `config/default.yaml`). Note Gurobi requires a paid license outside academia.

## Routine tasks
| When | Task | Command |
|---|---|---|
| Monthly | Refresh FDA outcomes | `uv run tobacco-inspect refresh` |
| Each March | Refresh the PA license list (licenses expire end of Feb) | `uv run tobacco-inspect refresh` |
| Each planning cycle | Refit and reschedule | `uv run tobacco-inspect fit && uv run tobacco-inspect solve` |
| Each planning cycle | Review the top stores and tract coverage before issuing route sheets | open `outputs/why_us.csv`, `outputs/coverage_by_tract.csv` |
| Each planning cycle | Produce route sheets | `uv run tobacco-inspect report` |

## Changing parameters
Edit `config/default.yaml` (teams, hours, mileage, budget, prize weights, coverage floors). No code
edits are needed. Re-run `pytest` afterward; the loader validates values.

## Outputs
CSV route sheets (primary; inspectors' workflow) and coverage-by-tract tables in `outputs/`.

## Troubleshooting
- `solver 'gurobi' is not available`: no license found. See Install.
- Geocoding or OSM download failures: rerun `refresh`; results are cached in `data/interim`.

## Handoff checklist
Pinned versions (`uv.lock`), model card, assumptions list, tests passing, named DOH owner.

## What the commands produce
| Command | Output |
|---|---|
| `refresh` | Downloads and cleans sources (needs network the first time); writes `data/interim`, `data/processed` |
| `fit` | `data/processed/risk_scores.csv`, `outputs/gate_a_backtest.csv`, `outputs/risk_model_summary.json` |
| `solve` | `outputs/schedule_route_sheets.csv`, `outputs/schedule_summary.csv` (dates skip US federal holidays; they are illustrative) |
| `report` | `outputs/why_us.csv`, `outputs/coverage_by_tract.csv`, `outputs/equity_summary.json` |
| `run-all` | all of the above in order |

The notebook `notebooks/02_risk_and_schedule.ipynb` rebuilds with `uv run python scripts/build_notebook_02.py`; an executed copy is
`docs/process/03_Implementation_Notebook_Executed.html`. Set `FULL = True` in the notebook to rerun the slow experiments (about 15 minutes).
Update the Synar report each spring (new PDF into `data/pdf/`, transcribe tables in `data/synar.py`, a second person checks them).
Public Gurobi pip license is size-limited; the code falls back to HiGHS automatically for larger models.
