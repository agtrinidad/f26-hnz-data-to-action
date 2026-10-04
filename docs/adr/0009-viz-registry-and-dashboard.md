# 9. Figures as a registry; one export path for CLI, dashboard and tests

Status: accepted (2026-10-03). Extends the layering in the README; routing is no longer the headline (full sweeps are feasible, ADR 0006-0008), so geography is used to find clusters, not routes.

## Context
No figure was ever saved: all plotting lived in notebook-generator strings, so nothing could be reused in the final report or deck.

## Decision
1. Every figure is a function `fn(data, config, **params) -> matplotlib Figure` registered by name in `viz/registry.py`, with an optional table function giving the data behind it. Adding a figure is one decorated function.
2. The CLI (`viz`), the Streamlit dashboard and the tests all go through the registry. The dashboard holds no figure logic.
3. matplotlib only (no kaleido or browser), so PNGs are identical on any machine. Style (palette, font, size, dpi) is in `config/default.yaml` under `viz:` and matches the class deck (Heinz red, Open Sans, bold title, red footer rule).
4. Geographic analysis lives in `eval/geo.py` as pure functions: DBSCAN on projected coordinates (`eps_m` 400 and `min_samples` 4 are ASSUMED, adjustable in the dashboard), clusters ranked by summed prize, and flagged when at least half the stores have no FDA history (the stores a census labels first). Maps are location-level (345), not license-level (467).
5. Figures read only committed CSVs; tract polygons are optional (`data/raw/boundaries`), and figures that need them are skipped when absent.

## Consequences
streamlit is an optional extra. Generated PNGs under `outputs/figures/` are git-ignored; report-ready copies go to `docs/deliverable/figures/`. Cluster results are descriptive and depend on the radius; they do not change the recommendation.
