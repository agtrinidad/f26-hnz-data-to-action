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
| `census` | Scenario only (not part of `run-all`): `outputs/census_routes.csv`, `census_cost_summary.csv`, `census_cost_components.csv`, `census_capture.csv`, `census_calendars.csv` |
| `value` | Scenario only (needs `fit` and `solve` first): `outputs/valuation_marginal.csv`, `valuation_break_even.csv`, `valuation_opportunity.csv`, `valuation_whatif.csv`, `valuation_robustness.csv`, `valuation_restated.csv` (about 20 seconds) |
| `regime` | Scenario only (not part of `run-all`; needs `fit` first): `outputs/regime_frontier.csv`, `regime_second_pass.csv`, `regime_response_grid.csv`, `regime_shape_sweep.csv`, `regime_equity.csv` (about 20 seconds) |

The notebook `notebooks/02_risk_and_schedule.ipynb` rebuilds with `uv run python scripts/build_notebook_02.py`; an executed copy is
`docs/process/03_Implementation_Notebook_Executed.html`. Set `FULL = True` in the notebook to rerun the slow experiments (about 15 minutes).
Update the Synar report each spring (new PDF into `data/pdf/`, transcribe tables in `data/synar.py`, a second person checks them).
Public Gurobi pip license is size-limited; the code falls back to HiGHS automatically for larger models.

## Figures and dashboard
`uv sync --extra viz`, then `uv run tobacco-inspect viz` (PNG to `outputs/figures`) or `uv run tobacco-inspect dashboard`. Re-run `viz` after any pipeline step to refresh report copies in `docs/deliverable/figures`. Map figures need tract polygons from `refresh`; without them they are skipped. The dashboard's **Report** tab and `viz --report` export the final-report figures listed in `config/report_figures.yaml` (order, captions, alt text); add a figure there by registered name. Plan: `docs/final-report-plan.md`.

### Extending the chart builder
Three extension points, each small:
- **Dataset** (a table the Builder can chart): in `viz/datasets.py`, add
  `@dataset("name", "Label", "one row per ...", needs=("loaded_key",))` on a function
  `fn(data, config) -> DataFrame`. Column roles are inferred; add readable names under `viz.columns`
  in `config/default.yaml`.
- **Chart kind**: in `viz/charts.py`, write `compute(df, spec, config)` and
  `draw(plot, spec, config, ctx)` (finish with `finish(...)` so the deck style and text overrides
  apply), then register `KINDS["name"] = ChartKind(label, fields, compute, draw, options=...)`.
  Facets come free if you draw through `panels()`. The Builder form is generated from `fields` and
  `options`, so there is no UI code to write.
- **Preset** (a Gallery figure): build the chart in the Builder, download the spec JSON, and paste
  it under `spec:` in `config/viz_presets.yaml` with a `section` and `title`.
