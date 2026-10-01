# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- Optimization stage: leakage-safe history features, calibrated risk model, Harrington state, Thompson sampling, prizes, team-orienteering MILP with ranked+batched comparator, OSM travel times, baselines, metrics, equity audit, simulation, `fit`/`solve`/`report` commands, annotated notebook 02, ADR 0005, APA source catalog, results memo; Synar 2025 report transcribed and used as the random-sample benchmark; single-store dedupe (392 licenses = 345 locations).
- Scope fixed to City of Pittsburgh limits (`data.scope`): in-city universe (467), in-city FDA checks (911), city columns in the fiscal-year table, B proxy 11.
- FDA OCE national compliance-check files (FY2011-26): PA statewide fiscal-year table, 49k PA undercover checks, follow-up timing, reconciliation with the Pittsburgh export; non-PA rows (4, South Pittsburg TN) now excluded; B proxy 28 -> 19.
- FDA Data Dashboard PA exports: statewide tobacco warning-letter series vs Pittsburgh; `openpyxl` dependency.
- Data acquisition and enrichment (2026-09-30): PA license universe, Census geocoding and tract/city flags, FDA-to-license matching, NCES/OSM/ACS features, capacity proxies, `refresh` command, offline tests; log in docs/process/02_Data_Acquisition_Memo.md.
- Repository scaffold: package skeleton, config loader, single-team orienteering MILP (toy),
  tests, CI, issue/PR templates, docs, report skeleton, submission packager.
