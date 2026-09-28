# Notebooks

- Name them in run order: `01_eda.ipynb`, `02_risk_model.ipynb`, `03_schedule.ipynb`, ...
- Strip outputs before committing (`uv run pre-commit install` enables `nbstripout`, or run
  `uv run nbstripout <file>`).
- Use paths relative to the repo root via `tobacco_inspect.config.REPO_ROOT` / `load_config().path(...)`,
  never absolute paths.
- Move reusable logic into `src/tobacco_inspect/`; notebooks should read as narrative and results.
- To run notebooks: `uv sync --extra dev --extra should` and add `jupyterlab` (or use VS Code's Jupyter support).
