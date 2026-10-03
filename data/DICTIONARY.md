# Data dictionary

Column meanings for the committed tables. Sources and retrieval notes are in
[docs/data-sources.md](../docs/data-sources.md); unmeasured parameters are listed in
[docs/assumptions.md](../docs/assumptions.md). Evidence labels: **observed** (real records),
**simulated** (computed on an assumed truth), **assumed** (a number no data identifies).

Keys used across files: `license_id` identifies one tobacco license, `location_key` one normalized street
address (a location can hold several licenses), `tract_geoid` an 11-digit Census tract.

## Core pipeline tables

### `data/processed/risk_scores.csv` (one row per scored license)
| Column | Meaning |
|---|---|
| `p_raw`, `p` | Predicted probability that a check at this store finds a sale to a minor, before and after calibration to the Synar random-sample rate (`calibration_shift` is the offset applied). Modeled |
| `outlet_type` | Store category (Synar taxonomy: e.g. convenience, pharmacy, vape shop) |
| `fda_observed` | Whether any FDA check at this location is on record. Unobserved stores have no history, not a clean one |
| `n_prior_checks`, `n_prior_viol` | Prior FDA checks and violations at the location |
| `viol_12m`, `viol_24m`, `viol_36m` | Violations in the trailing 12, 24, 36 months |
| `days_since_check`, `days_since_viol` | Recency of the last check and last violation |
| `severity_points` | FDA penalty-schedule points accumulated (escalation ladder) |
| `site`, `youth`, `severity` | Exposure components in [0, 1]: proximity to schools and youth sites, tract youth share (shrunk when the ACS margin is large), and capped historical severity |
| `h` | Exposure score: weighted sum of `site`, `youth`, `severity` (weights in `config/default.yaml`, `prize.h_weights`) |
| `deterrence` | Follow-up-due term: higher when a repeat check is overdue under the escalation rules |
| `targeted` | Whether the store is in the targeted (need-ranked) pool rather than the random share |
| `prize` | Selection score `h * p + lambda * deterrence` (unit-free; `lambda` is `prize.lambda_deterrence`) |

### `data/processed/retailer_universe.csv` and `data/interim/licenses_clean.csv`
Active PA Department of Revenue tobacco licenses for Allegheny County, cleaned, geocoded and flagged
(`in_city_limits`, `postal_pittsburgh`) with the FDA match (`fda_*` columns: `fda_match_tier` and
`fda_match_distance_m` describe how the FDA record was joined; `fda_records`, `fda_violations`,
`fda_first_decision`, `fda_last_decision` summarize it). `coord_source` records where each coordinate
came from. `retailer_universe_postal.csv` is the wider postal-Pittsburgh reference set. Scope for all
analysis is `in_city_limits`.

### `data/processed/location_features.csv`
Model inputs per license: distances to the nearest school and youth site and counts within 300 m and
1,000 m (`school_*`, `public_school_*`, `youth_site_*`), `chain_flag`, and the tract's ACS fields.
`acs_youth_share_unreliable` flags tracts where the margin of error makes the share untrustworthy.

### `data/processed/oce_pa_checks.csv.gz`, `fda_city_checks.csv.gz`
Pennsylvania undercover checks from the FDA OCE national files (49k rows), and the Pittsburgh subset. Used
for training and backtesting. Observed, but FDA chose whom to inspect, so they are not a random sample.

## Interim tables (`data/interim/`)
| File | Contents |
|---|---|
| `acs_tracts.csv` | ACS 2020-2024 tract population, under-18 and poverty with margins of error (`*_moe`) |
| `schools_pgh.csv`, `youth_sites.csv` | School locations (NCES) and OSM youth sites (libraries, community centres, childcare, playgrounds, parks) |
| `fda_locations.csv`, `fda_scope_unknown.csv`, `match_review.csv` | FDA address aggregation, 44 locations needing manual placement, and matches under review |
| `geocode_cache.csv` | Census Geocoder results keyed by address |
| `oce_pa_by_fiscal_year.csv`, `pittsburgh_fda_records_by_year.csv`, `pa_tobacco_warning_letters_by_year.csv` | Yearly counts and violation rates for context |
| `synar_2025_*.csv`, `synar_history_2016_2025.csv` | Hand-transcribed Synar tables (source page numbers in the `pages` column; history is chart-read and approximate). Random-sample benchmark; cigarettes only |
| `travel_time_matrix_<hash>.csv.gz` | OSM drive times in minutes, cached per point set |

## Outputs (`outputs/`, small, committed)

**Schedule and audit**
| File | Contents |
|---|---|
| `schedule_summary.csv` | Per cycle: stores, routes, route minutes, prize, solver and status |
| `schedule_route_sheets.csv` | The stop-by-stop plan: cycle, route, team, date, stop, store, address, `p`, `h`, `prize`, `random_share_pick` |
| `why_us.csv` | Route sheets plus the plain-language reason a store was chosen (`why_us`, recent violations, prior checks) |
| `coverage_by_tract.csv`, `equity_summary.json` | Where inspections land by tract, poverty and youth share |
| `risk_model_summary.json` | Model fit and calibration summary |

**Evaluation (simulated or backtested)**
| File | Contents |
|---|---|
| `gate_a_backtest.csv` | Backtest by fiscal year and scorer: AUC and top-fraction lift with 95% bounds (`lift_lo`, `lift_hi`). Observed sample |
| `gate_b_sweep.csv` | Optimizer versus ranked-and-batched heuristic across budgets and day lengths |
| `simulation_policies.csv`, `simulation_kappa.csv` | Policy comparison under assumed store reactions (`delta` deterrence strength, `rho` response) |

**Census scenario and regime comparison (assumed costs; simulated violators)**
| File | Contents |
|---|---|
| `census_*.csv` | Calendars, routes, capture and line-by-line cost of checking every store |
| `regime_*.csv` | Cost-versus-outcome frontier, second pass, response grids, visibility shape and equity for both regimes |
| `valuation_*.csv` | Marginal cost over today's program, break-even tables, what-ifs, robustness and opportunity cost. `valuation_opportunity.csv` carries a `label` column |

Store-level files (`risk_scores`, `schedule_route_sheets`, `why_us`) name licensed businesses taken from
public records. Scores are a screening aid for prioritizing inspections, not a finding about any business.
