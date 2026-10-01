# Methodology memo 02: data acquisition and enrichment

> **Erratum (section 12):** the Pittsburgh export contained 4 non-PA rows (South Pittsburg, TN; FDA spells the city "S PITTSBURGH"). The code now
> drops them: 1,812 records, 748 locations, 867 entities (not 1,816 / 749 / 868). Capacity proxy B is now 19
> (not 28). Numbers quoted in sections 1-8 predate this fix and differ by 1-2 units.
>
> **Scope decision (section 13, 2026-09-30):** the project is scoped to the City of Pittsburgh limits. B is now 11 per quarter.

Audit trail for everything done to acquire, clean, geocode, match and enrich the retailer universe.
Companion to `EDA_Preprocessing_Methodology_Memo.docx` (notebook 01). Run date: 2026-09-30.
Reproduce with `uv run tobacco-inspect refresh` (online first run; cached afterwards). To force
a fresh download, delete the relevant file in `data/raw/`.

No risk model, routing or optimization was built in this stage.

## 1. Preflight
- The original FDA export `Pittsburgh Inspections.csv` is not in the working tree. `data/raw/` holds
  the notebook-01 outputs `pittsburgh_inspections_cleaned.csv` (1,816 rows, all 17 source columns
  plus keys) and `pittsburgh_retailer_master.csv` (868 rows). `load_fda_history()` prefers the original
  export if present and otherwise uses the cleaned file. A test confirms 1,816 records, 749
  locations, 868 entities (skips if the raw files are absent).
- The repo code was changed so `location_key` / `retailer_entity_key` are defined once, in
  `src/tobacco_inspect/data/ingest.py` (same rule as notebook 01).

## 2. Sources pulled (retrieved 2026-09-30)
| Source | How | Landing | Notes |
|---|---|---|---|
| PA Revenue active Cigarette/OTP licenses | data.pa.gov Socrata dataset `ut72-sft8` (CSV, `county='ALLEGHENY'`) | `data/raw/pa_licenses_allegheny_20260930.csv` | 1,737 licenses; refreshed daily by PA DOR; expiry 2027-02-28; includes lat/lon for all but 23 rows; license numbers partly masked |
| Census cartographic boundaries 2023 | `www2.census.gov/geo/tiger/GENZ2023/shp` tract + place (PA) | `data/raw/boundaries/` | Pittsburgh city = place GEOID 4261000 |
| NCES EDGE public schools 2023-24 | `nces.ed.gov/programs/edge/data/EDGE_GEOCODE_PUBLICSCH_2324.zip` | `data/raw/` | shapefile read with bbox around Pittsburgh |
| NCES private schools (PSS) 2021-22 | `EDGE_GEOCODE_PRIVATESCH_2122.zip` | `data/raw/` | older vintage than public; check for a newer file |
| ACS 2020-2024 5-year, tables B01001, B17001, Allegheny tracts | Census Reporter API (keyless) | `data/raw/acs5_latest_42003_tracts.json` | Census Data API needs a free key; `acs_source: census_api` is reserved for that |
| Youth sites (libraries, community centres, childcare, playgrounds, parks, sports) | OpenStreetMap via osmnx, bbox around Pittsburgh | `data/interim/youth_sites.csv` (4,171 sites) | OSM completeness is uneven; definition of "vulnerable site" needs team sign-off |
| Census Geocoder (batch) | `geocoding.geo.census.gov` `Public_AR_Current` | `data/interim/geocode_cache.csv` | used for FDA addresses and 23 licenses lacking coordinates; cache keyed by `location_key` |

Not obtained: the FDA compliance database search (`accessdata.fda.gov`) blocks automated access
(returns an "excessive requests" page), so PA statewide counts per year could not be pulled. The
WPRDC "Allegheny County Tobacco Vendors" page returned a 2015 CSV (last modified 2017) only;
downloaded metadata but not used because it is superseded by the daily state list. Both remain
manual/optional steps.

## 3. Cleaning (licenses)
1. Parse the `POINT (lon lat)` text to numeric coordinates.
2. Normalize text/address with the notebook-01 rule; add `match_street`, an aggressively
   standardized street used only for cross-source lookup (suffixes, directions, ordinals, unit
   suffixes removed). `location_key` itself stays conservative.
3. Flag retail vs vending/wholesale/itinerant licenses (`license_retail`).
4. Stable `license_id` = first 10 hex chars of md5(account | license type | location_key).
5. Fill 23 missing coordinates via the Census Geocoder (4 resolved inside the Pittsburgh scope).

## 4. Geography
- Point-in-polygon joins (no network): census tract (2023 boundaries, Allegheny) and Pittsburgh
  city limits (Census place 4261000). Coordinates are NAD83 lon/lat; distances computed in UTM 17N.
- **Scope finding.** 884 Allegheny licenses carry a postal city of PITTSBURGH, but only 463 of them
  lie inside the city limits; 4 more in-city licenses have another postal city. The universe file
  keeps both flags (`postal_pittsburgh`, `in_city_limits`) and includes both groups (888 rows). Same
  issue in FDA data: of 674 geocoded FDA locations, 370 are inside city limits (54%). The project must
  decide its scope (city limits vs postal Pittsburgh); it changes the budget proxy (see section 7).

## 5. FDA matching
- FDA locations (749) are geocoded with the Census Geocoder: 674 matched, 75 not (kept, flagged).
- Tier 1 `address`: same ZIP5 and same `match_street`. Tier 2 `proximity`: within 75 m and name
  similarity >= 0.55 (difflib ratio after removing LLC/INC/etc.). A location may match several
  licenses (multi-tenant); history is attached to every matched license (not split).
- Result (Pittsburgh scope, 888 licenses): 390 licenses matched an FDA location (369 by address, 21
  by proximity). In city limits: 392 retail licenses, 188 (48%) with any FDA record, 74 with at
  least one recorded violation.
- `data/interim/match_review.csv` (543 rows) lists: 343 FDA locations with no current license (164 in
  city limits, 44 not geocoded; expected for closed stores over a 15-year history, but
  also possible match failures), 48 proximity matches, and 152 locations matching multiple licenses.
  These need human review; entity-level resolution (name changes) is deliberately not attempted.
- Sanity check: OIG reports PA retailer coverage in the 75-89% band (2010-2019). Our current-license
  coverage (48-50%) is lower. Plausible reasons: our export only includes undercover (UP involved)
  checks, turnover of stores since 2019, name/address mismatches, and scope. Not resolved.

## 6. Enrichment features (`data/processed/location_features.csv`, one row per license)
- Schools (public + private): nearest distance and counts within 300 m and 1,000 m; public-only
  versions; youth-site distance and counts. 31.6% of in-city retail licenses have a school within 300 m.
- ACS tract: total population, under-18 count and share, poverty rate, each with a margin of error;
  `acs_youth_share_unreliable` flags MOE > 50% of the estimate (42% of in-city retail licenses sit in
  such tracts). All 467 in-city licenses have a tract (96 tracts).
- Store type from trade-name keywords (heuristic, 53% "other") and `chain_flag` (same legal name on
  >= 3 licenses in scope). Both are rough and should be treated as features to audit.
- No violation history is joined into features (kept separate, in `retailer_universe.csv`) to keep a
  clean line against leakage.

## 7. Capacity proxies (Phase 0)
- Public evidence is tabulated in `docs/sources/README.md`. Pittsburgh FDA records per decision year
  are in `data/interim/pittsburgh_fda_records_by_year.csv`.
- 2023: 101 records (49 in city limits), 2024: 110 (62). 2025 (26) and 2026 (30) are incomplete by
  decision-date lag. Hence B per quarter ~ 25-28 (postal) or ~12-16 (city only).
- `config/default.yaml` updated: `horizon_weeks: 13`, `budget_inspections: 28`, each parameter tagged
  SOURCED / PROXIED / ASSUMED. The previous 200 per week was about the statewide annual volume.

## 8. Data-quality flags raised (for human review before modeling)
1. Observed violation rate by decision year is unstable: 0-2% (2011-13, 2019), 9-19% (2014-18),
   26-48% (2021-24). Possible causes: recording/publication changes, sampling of repeat-violator
   follow-ups, or the UP-involved filter. Until explained, do not pool years naively.
2. 2020 has 4 records and 2025-26 are sparse (COVID and reporting lag): do not treat as low activity.
3. Only 175 of 1,816 records have inspection dates (see memo 01): all timing uses decision dates.
4. OIG's median follow-up interval after a violation is 178 days; our median repeat interval is 497
   days: reconcile before engineering "time since last inspection".
5. ACS margins of error are large in many tracts; OSM youth-site coverage is uneven; NCES private
   schools are a 2021-22 vintage.

## 9. Tests and checks run
- `pytest`: 18 passed (9 existing + 9 new offline tests: key rules, address standardization, name
  similarity, store classifier, proximity math, ACS parsing, geocode cache round trip, notebook-01
  count parity).
- `ruff check src tests`: clean. `scripts/package_submission.py --check`: OK (new data ~2 MB).
- `tobacco-inspect refresh` runs end to end online and again from cache.

## 10. Open human actions
- Decide scope: city limits vs postal Pittsburgh (affects universe size and B).
- Review `data/interim/match_review.csv`; decide how to treat FDA locations with no current license.
- Export PA statewide FDA records per year from the FDA database (manual) to test the 10,000/yr claim.
- File a PA Right-to-Know request to DOH for Pittsburgh/Allegheny inspection counts; ask the
  instructor/DOH who selects stores.
- Approve the definition of "vulnerable site" (schools only vs plus OSM youth sites).
- Optionally obtain a free Census API key and re-pull ACS via the Census Data API.

## 11. Addendum: FDA Data Dashboard exports for PA (added 2026-09-30, later in the day)
Four manually downloaded files were added to `data/raw/`: `fda-pa-inspections.xlsx` (12,553 rows),
`fda-pa-citations.xlsx` (7,988), `fda-pa-compliance-actions.xlsx` (6,380), `fda-pa-483s.xlsx` (97).
They cover every FDA product type, carry no street address, and the code reads them with `openpyxl`
(new dependency, added with `uv add openpyxl`; `uv.lock` updated).
- **Inspections:** only 34 rows are Tobacco, all "Tobacco Post-Market Activities" at manufacturers,
  vape makers and cigar shops (e.g. one in Sewickley). These are not retailer compliance checks, so
  they cannot supply statewide inspection counts. **Not used.** The 10,000/yr claim remains untested.
- **Citations and 483s:** no tobacco rows (program areas are foods, drugs, devices, etc.). **Not used.**
- **Compliance actions:** 6,065 Tobacco rows, all Warning Letters (2011 to Sept 2026), 3,845 distinct
  firms, name only (no address/city), so no store-level join to the license universe. No civil money
  penalty rows appear in this extract. Used for statewide yearly context only:
  `data/interim/pa_tobacco_warning_letters_by_year.csv`, built by `ingest.statewide_vs_pittsburgh`.
- **Result:** statewide warning letters per year: 181 (2011), 591-911 (2014-15), about 350-500
  (2016-19), 81 (2020), 92 (2021), 562 (2022), 325-395 (2023-25), 228 so far in 2026. Pittsburgh
  warning letters in our export: 0-2 in 2011-13, 13-26 in 2014-18, **1 in 2019 (statewide 500)**, 13-19
  in 2022-24, **2 in 2025 (statewide 366)**.
- **Interpretation (hypotheses, not confirmed):** (a) the near-zero Pittsburgh violation years 2013
  and 2019 are not a statewide pattern, so they look like Pittsburgh-specific coverage or export gaps
  rather than real compliance; (b) the 2025-26 Pittsburgh drought is not explained by statewide
  activity, which continued, so it is either reporting lag, a Pittsburgh coverage gap or an export
  filter effect. This strengthens flag 8.1 above: do not train on pooled years or treat sparse years
  as low violation rates until explained. Pittsburgh was 2-6% of PA warning letters in active years,
  versus about 1% of the statewide inspection volume implied by the 10,000/yr figure, which
  suggests Pittsburgh is inspected more heavily, has a higher violation rate, or the 10,000 figure
  includes non-undercover inspections. Not resolvable with these files.
- **Still missing:** statewide retailer compliance-check counts (the FDA compliance-check database
  export, `accessdata.fda.gov/scripts/oce/inspections`, not the Data Dashboard) and civil money
  penalty records, which are published in the same compliance-actions dashboard under another
  action type if filtered for. Ask the team to re-export with all action types and Tobacco only.

## 12. Addendum: FDA OCE national compliance-check files (added 2026-09-30, evening)
`data/raw/OCE_FY2011.zip` through `OCE_FY2026.zip` (16 files, same 17-column schema as the Pittsburgh export, one
CSV per federal fiscal year, Oct-Sep, decisions through 2026-08-31). Read with `ingest.load_oce()`, chunked (a one-shot
`read_csv` of these files segfaulted pandas on this Windows machine; chunked reads work). Filtered to State = PA:
64,001 records (49,032 with an underage purchaser involved); 8 exact duplicate rows were left in place (not removed).
Outputs: `data/interim/oce_pa_by_fiscal_year.csv` (statewide and Pittsburgh counts, rates) and
`data/processed/oce_pa_checks.csv.gz` (49,032 PA undercover checks, 1.6 MB, for later modeling). `refresh` writes both.

**Findings**
1. **Reconciliation.** OCE reproduces the Pittsburgh export exactly: 1,812 PA records with UP involved match on
   retailer, address and decision date; the export's other 4 rows are South Pittsburg (no H), **TN**, spelled "S PITTSBURGH" in the FDA data. The postal-city
   filter also caught East/West Pittsburgh (2, 1) and an "E PITTSBURGH" row. So the export is complete relative to
   FDA's own database, and the 2013 and 2019 near-zero violation rates are in FDA's data, not an export artifact.
2. **Statewide volume is far below 10,000.** PA undercover checks per fiscal year: 2012: 3,776; 2015: 5,681; 2018:
   3,609; 2022: 1,752; 2023: 2,330; 2024: 3,471; 2025: 2,988 (2023-25 mean about 2,930). The "approximately
   10,000 per year" figure is a funding/capacity statement, not what appears in this database (which may also
   not list every check). The 2020-21 collapse (1,924 then 60 checks) is COVID.
3. **Pittsburgh share and capacity.** Pittsburgh-postal undercover checks: FY2022 54, FY2023 76, FY2024 123, FY2025
   46 (mean 75/yr), about 3-4% of statewide checks (1.5% in FY2025-26). That gives B of about 19 per quarter
   (postal scope) or about 10 (city limits only, 54%). Config updated to 19.
4. **Pittsburgh is not statewide-typical.** Violation rates (undercover checks): PA 12-21% in most years; Pittsburgh
   0% (2013), 1.3% (2019), then 39%, 30%, 30% in FY2022-24. FY2019 Pittsburgh had 230 checks and 3 violations while PA
   had 747 violations in 4,620 checks. These swings point to inspector/team/period effects or procedural changes
   rather than store risk, which a store-level model cannot see. A year (or team) effect must be modeled or the
   2013 and 2019 periods excluded. Needs a human question to DOH/subcontractor.
5. **Follow-up timing resolves flag 8.4.** Median days from a violation to the next record at the same address:
   PA 266, Pittsburgh 247. Share of violations (older than a year) re-checked within 12 months: PA 58%, Pittsburgh
   73%, against OIG's 88% national (2010-2019). The earlier 497-day median was for all record pairs, not
   violation-conditioned; the two are consistent. Prior-violators-first re-inspection is real practice but less
   complete in PA than the OIG national figure.
6. **Outcome mix (PA):** 56,615 no violation, 5,989 warning letters, 1,390 civil money penalties (792 + 405 archived
   + 193 not available), 7 no-tobacco-sale orders. Civil money penalty and NTSO outcomes are now available to
   build the real escalation state (Harrington) from data.

**Implications for the project**
- Training data can come from all of PA (49k undercover checks, 18.8k distinct locations), not just Pittsburgh
  (1.8k). That needs address-level geocoding outside Pittsburgh, or chain/name-pattern features that do not.
  Not done yet.
- The risk model needs period (fiscal year) effects; pooled-year baselines will mislead (finding 4).
- Capacity proxies should use observed checks (about 75/yr, 19/quarter), which makes routing even less likely to
  matter (Gate B).

## 13. Scope decision: City of Pittsburgh limits only (2026-09-30)
Decision by the team: scope to the City of Pittsburgh (resolves open item 10.1). Implemented as `data.scope:
city_limits` in `config/default.yaml` (`postal` restores the wider postal-Pittsburgh scope). Definition: the point
lies inside the Census place polygon for Pittsburgh city (GEOID 4261000, 2023 boundaries). Postal city name is not used.

**What changed in the pipeline**
- `retailer_universe.csv` now holds only in-city licenses: 467 (392 retail; the rest vending, wholesale, stamping,
  itinerant). The wider 888-row postal universe is kept for reference in `data/interim/retailer_universe_postal.csv`.
- Every FDA location gets `city_scope` = `in_city`, `outside_city` or `unknown` (`data/interim/fda_locations.csv`).
  Geocoded locations use the polygon; locations the Census Geocoder could not place inherit the flag of an address-
  matched license; the rest stay `unknown`. Result for 748 FDA locations: 379 in city, 325 outside, 44 unknown.
  The 44 are excluded from the city scope and listed in `data/interim/fda_scope_unknown.csv` for manual placement.
- New `data/processed/fda_city_checks.csv.gz`: the FDA undercover checks at in-city locations. 911 checks, 379
  locations, 444 retailer entities, 120 violations (13.2%), 91 census tracts.
- `oce_pa_by_fiscal_year.csv` gained `city_up_checks`, `city_violations`, `city_violation_rate`,
  `city_share_of_checks` (city limits, per fiscal year, from the national OCE files).
- `match_review.csv` is restricted to in-scope rows: 164 FDA locations with no license, 73 locations matching several
  in-city licenses, 28 proximity matches. `location_features.csv` has 467 rows.
- Capacity: city checks per fiscal year: FY2022 39, FY2023 42, FY2024 71, FY2025 22, mean about 44 a year, so
  `budget_inspections: 11` per quarter (earlier 28, then 19, were postal-scope values).

**Consequences to carry forward**
1. City-limits history is small: 911 checks and 120 violations over 15 years; recent years are 22-71 checks. The
   Pittsburgh-only model will have very little data per year. Options: pool PA data for the risk model with
   a Pittsburgh scoring layer (needs geocoding outside the city), or a simple shrinkage model on city data.
2. City violation rates remain unstable (0% FY2013, 1.6% FY2019, 44% FY2022, 31% FY2023, 34% FY2024,
   14% FY2025): period effects are still the main finding.
3. In-city license coverage: 188 of 392 retail licenses (48%) have any FDA record; 74 have at least one violation.
4. 44 unknown-scope FDA locations could change these counts slightly (up to about 6% of locations).
5. At about 11 checks per quarter in a roughly 55 square mile city, routing is unlikely to matter (Gate B).
