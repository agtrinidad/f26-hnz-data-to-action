# Data

| Dir | Tracked in git? | Purpose |
|---|---|---|
| `raw/` | No (git-ignored) | Downloads exactly as retrieved. Re-created by `tobacco-inspect refresh`. |
| `interim/` | Yes, if small | Cleaned/geocoded tables, cached distance matrix. |
| `processed/` | Yes, if small | Model-ready tables. Needed so the submission zip runs offline. |

Keep the committed total under about 25 MB (checked by `scripts/package_submission.py --check`).

## Sources

Fill in retrieval date and file/version as each is pulled. Full URLs: [docs/data-sources.md](../docs/data-sources.md).

| Source | Refresh cadence | Retrieved | File / version | Notes |
|---|---|---|---|---|
| PA Revenue active cigarette/OTP license list (data.pa.gov `ut72-sft8`) | Daily (licenses expire end of Feb) | 2026-09-30 | `raw/pa_licenses_allegheny_20260930.csv` (1,737 Allegheny rows) | Retailer universe; lat/lon included; `interim/licenses_clean.csv`, `processed/retailer_universe.csv` |
| FDA Tobacco Compliance Check outcomes | Monthly | export through 2026-07-31 (notebook 01) | `raw/pittsburgh_inspections_cleaned.csv` (original export not in repo) | Inspected stores only: selection bias; database blocks scripted access |
| FDA OCE compliance checks, national, FY2011-FY2026 | Monthly | 2026-09-30 | `raw/OCE_FY*.zip` | Same schema as the Pittsburgh export; PA filtered into `interim/oce_pa_by_fiscal_year.csv` and `processed/oce_pa_checks.csv.gz` |
| FDA Data Dashboard PA exports (compliance actions, inspections, citations, 483s) | Monthly | 2026-09-30 | `raw/fda-pa-*.xlsx` | All product types, no addresses; only tobacco warning letters used (`interim/pa_tobacco_warning_letters_by_year.csv`) |
| SAMHSA / PA Synar survey | Annual | not pulled | | State-level calibration only; PA 2020 rate 16.1% (unverified) |
| ACS 5-year (Census Reporter, tracts) | Annual | 2026-09-30 | `raw/acs5_latest_42003_tracts.json` (2020-2024) | Margins of error carried; `interim/acs_tracts.csv` |
| NCES EDGE public schools 2023-24 / PSS private 2021-22 | Annual / biennial | 2026-09-30 | `raw/EDGE_GEOCODE_PUBLICSCH_2324.zip`, `raw/EDGE_GEOCODE_PRIVATESCH_2122.zip` | `interim/schools_pgh.csv` |
| Census TIGER cartographic boundaries 2023 (tract, place) | As needed | 2026-09-30 | `raw/boundaries/cb_2023_42_*_500k.zip` | Tracts, not ZIP codes (MAUP); city = place 4261000 |
| Census Geocoder (batch) | As needed | 2026-09-30 | `interim/geocode_cache.csv` | FDA addresses plus 23 licenses without coordinates |
| OpenStreetMap youth sites (osmnx) | As needed | 2026-09-30 | `interim/youth_sites.csv` | Coverage uneven |
| WPRDC Allegheny tobacco vendors | | not used | 2015 vintage only | Superseded by the state list |

Full processing log: [docs/process/02_Data_Acquisition_Memo.md](../docs/process/02_Data_Acquisition_Memo.md).

## Scope
Project scope is the City of Pittsburgh limits (`data.scope: city_limits`). Key files:
`processed/retailer_universe.csv` (467 in-city licenses), `processed/fda_city_checks.csv.gz` (911 in-city FDA
undercover checks), `processed/location_features.csv`, `interim/retailer_universe_postal.csv` (wider reference
universe), `interim/fda_scope_unknown.csv` (44 locations to place manually).

## Modeling artifacts (added 2026-09-30)
`processed/risk_scores.csv` (probability, exposure, prize per license), `processed/oce_pa_checks.csv.gz` (49k PA undercover checks),
`interim/synar_*.csv` (hand-transcribed Synar tables; check against the PDF in `data/pdf/`), `interim/travel_time_matrix.csv.gz`
(OSM drive times, minutes). Results (git-tracked, small): `outputs/`.
