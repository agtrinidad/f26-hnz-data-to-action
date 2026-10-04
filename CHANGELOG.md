# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- Chart builder (2026-10-03): `viz/spec.py` (`ChartSpec` JSON recipe), `viz/datasets.py` (catalog with inferred column roles), `viz/charts.py` and `viz/charts_special.py` (10 chart kinds, facets), `viz/build.py` (validation, `render_spec`), gallery presets in `config/viz_presets.yaml`, dashboard split into `viz/ui/` (Gallery, Builder), `tobacco-inspect viz --spec`, `viz.columns` display names, ADR 0010, tests. `prize_distribution` is now a preset.
- Report figures and dashboard (2026-10-03): `viz/` figure registry (16 deck-styled matplotlib figures: coverage, risk, policy, geography), PNG export via `tobacco-inspect viz`, Streamlit dashboard via `tobacco-inspect dashboard` (PNG, CSV and section-zip downloads), `eval/geo.py` (DBSCAN store clusters, hotspot table, Gi*-style z-scores, tract summary), `viz:` config block, optional `viz` extra, ADR 0009, tests. Final PNGs in docs/deliverable/figures. Dashboard text is editable per figure (title, subtitle, source note) with the defaults prefilled; edits apply to PNG and zip exports.
- Marginal value (2026-10-03): `eval/valuation.py` (marginal cost over today's program, break-even deterrence without a dollar value of a sale, opportunity cost, what-if sweep, lambda robustness), `pipeline.valuation`, `tobacco-inspect value`, `valuation:` config block, memo 07, ADR 0008, tests. Windows-path check and reconciliation notes ported from Abigail Torbatian's upload (her reconciliation docs are in docs/reconciliation-2026-10-01/); her exact 4/4/3 allocator was ported and then reverted so every analysis keeps the uniform 4 stores per cycle.
- Regime comparison (budget-capped vs census floor with a need-weighted second pass): `eval/regime.py` (truth calibrated to the observed lift, cost-vs-outcome frontier, value of first-pass labels, year simulation scored on violation exposure, equity for both regimes), `pipeline.regime`, `tobacco-inspect regime`, notebook 04, memo 06, ADR 0007 (amends 0006), `regime:` config block, tests.
- `simulate.effective_p`: one shared response model (store-specific, frequency and general deterrence with a shape); `simulate.run` also returns exposure.
### Changed
- Census constants ($116, 1.5 lift, award) now read from config; census outputs unchanged. Memo 05 section 7 and the decision card updated.
- Census scenario (check every distinct retail location once a year): route partitioning (`routing/partition.py`), cost model and capture analysis (`eval/census.py`), `tobacco-inspect census`, notebook 03, memo 04, ADR 0006; travel-time matrix cache now keyed by point set.
- Optimization stage: leakage-safe history features, calibrated risk model, Harrington state, Thompson sampling, prizes, team-orienteering MILP with ranked+batched comparator, OSM travel times, baselines, metrics, equity audit, simulation, `fit`/`solve`/`report` commands, annotated notebook 02, ADR 0005, APA source catalog, results memo; Synar 2025 report transcribed and used as the random-sample benchmark; single-store dedupe (392 licenses = 345 locations).
- Scope fixed to City of Pittsburgh limits (`data.scope`): in-city universe (467), in-city FDA checks (911), city columns in the fiscal-year table, B proxy 11.
- FDA OCE national compliance-check files (FY2011-26): PA statewide fiscal-year table, 49k PA undercover checks, follow-up timing, reconciliation with the Pittsburgh export; non-PA rows (4, South Pittsburg TN) now excluded; B proxy 28 -> 19.
- FDA Data Dashboard PA exports: statewide tobacco warning-letter series vs Pittsburgh; `openpyxl` dependency.
- Data acquisition and enrichment (2026-09-30): PA license universe, Census geocoding and tract/city flags, FDA-to-license matching, NCES/OSM/ACS features, capacity proxies, `refresh` command, offline tests; log in docs/process/02_Data_Acquisition_Memo.md.
- Repository scaffold: package skeleton, config loader, single-team orienteering MILP (toy),
  tests, CI, issue/PR templates, docs, report skeleton, submission packager.
