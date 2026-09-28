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
