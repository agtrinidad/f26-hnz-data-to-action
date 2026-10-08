# Data sources

Every dataset and document this project used or examined, with the local file it became and the outputs it feeds.
Citations are APA 7th edition. Retrieval dates are 2026-09-30 unless noted; manual-download steps and file
listings are in [data/README.md](../data/README.md), and the processing log is
[process/02_Data_Acquisition_Memo.md](process/02_Data_Acquisition_Memo.md). Items marked **[verify]** were not fully
confirmed (missing author, title, date or DOI) and need a check before citing in a final report.

## Access notes

| Source | Access | Status (2026-09-30) |
|---|---|---|
| FDA tobacco compliance check outcomes (OCE) | Manual download; the FDA site blocks scripted access | Required. A 1,816-record Pittsburgh export is a subset of the national fiscal-year files |
| PA Dept. of Revenue tobacco licenses (Open Data PA) | API, scripted by `tobacco-inspect refresh` | Required; retailer universe |
| PA DOH 2025 Synar report | PDF supplied by the team (`data/pdf/`) | Required; the only random-sample benchmark |
| Census Geocoder, TIGER boundaries, NCES EDGE | Scripted by `refresh` | Required |
| ACS 5-year (2020-2024) | Census Reporter API (the Census API needs a key) | Should |
| OpenStreetMap (OSMnx) | Scripted; the drive graph is cached, git-ignored | Should |
| WPRDC tobacco vendors | Not used (2015 vintage only) | Superseded by the state list |

## Known data limitations

- FDA outcomes are address-level (decision date, violation, product) but cover only inspected stores, and inspections
  were not randomly assigned: absence of a record is not compliance.
- Synar is a state-level probability sample of youth purchase attempts: use it for calibration, not retailer-level
  labels. The base rate is low, so positives are sparse; the model uses regularized or shrinkage estimates.
- The license list is per location and expires at the end of February (annual refresh). The FDA database updates
  monthly and covers brick-and-mortar stores only.
- ACS block-group estimates carry large margins of error.
## A. Datasets used

**Pennsylvania Department of Health, Health Informatics Office, Statistical Support Team.** (2026, May). *2025 annual Synar report* [Report]. Pennsylvania Department of Health. [URL to be added; supplied as a PDF by the team] **[verify URL]**
- Local file: `data/pdf/synar_report_2025.pdf`. Role: the only random-sample benchmark (Allegheny 26.0%, 95% CI 17.3-34.7; statewide 15.2%; outlet-type rates; purchaser attributes). Cigarettes only; summer 2025.
- Feeds: `data/interim/synar_2025_*.csv` and `synar_history_2016_2025.csv` (hand-transcribed, page numbers in the files; chart-read history is approximate), the population-rate calibration in `model/risk.py`, the outlet-type taxonomy in `data/synar.py`.

**Pennsylvania Department of Revenue.** (2026). *Tobacco products tax licenses current daily county revenue* [Data set]. Commonwealth of Pennsylvania, Open Data PA. https://data.pa.gov/d/ut72-sft8 (retrieved September 30, 2026)
- Local file: `data/raw/pa_licenses_allegheny_20260930.csv` (1,737 Allegheny licenses; API: `https://data.pa.gov/resource/ut72-sft8.csv`). Role: retailer universe (denominator).
- Feeds: `data/interim/licenses_clean.csv`, `retailer_universe_postal.csv`, `data/processed/retailer_universe.csv`, `location_features.csv`.

**U.S. Food and Drug Administration. (2026).** *Compliance check inspections of tobacco product retailers* [Data set; fiscal-year files OCE_FY2011 to OCE_FY2026, national]. https://www.accessdata.fda.gov/scripts/oce/inspections/oce_insp_searching.cfm (files supplied by the team, downloaded September 30, 2026) **[verify download page and release date]**
- Local files: `data/raw/OCE_FY2011.zip` to `OCE_FY2026.zip`; the Pittsburgh export titled "Tobacco Compliance Outcomes Through 07/31/2026" is a subset of these (reconciled exactly, memo 02 section 12). Role: outcomes and inspection history (labels, follow-up timing, statewide volume).
- Feeds: `data/processed/oce_pa_checks.csv.gz`, `fda_city_checks.csv.gz`, `data/interim/oce_pa_by_fiscal_year.csv`, the risk model, the backtest.

**U.S. Food and Drug Administration.** (2026). *FDA data dashboard: Compliance actions, inspections, citations and Form 483 records, Pennsylvania* [Data sets]. https://datadashboard.fda.gov/ (team downloads, September 30, 2026) **[verify exact dashboard pages]**
- Local files: `data/raw/fda-pa-compliance-actions.xlsx`, `fda-pa-inspections.xlsx`, `fda-pa-citations.xlsx`, `fda-pa-483s.xlsx`. Role: only the 6,065 tobacco warning letters were usable (no addresses).
- Feeds: `data/interim/pa_tobacco_warning_letters_by_year.csv`.

**U.S. Census Bureau.** (2023). *2023 cartographic boundary files: Census tracts and places, Pennsylvania (cb_2023_42_tract_500k, cb_2023_42_place_500k)* [Shapefiles]. https://www2.census.gov/geo/tiger/GENZ2023/shp/ **[verify publication year]**
- Local files: `data/raw/boundaries/`. Role: tract assignment; City of Pittsburgh limits (place 4261000).

**U.S. Census Bureau.** (n.d.). *Census Geocoder* [Web service, benchmark Public_AR_Current]. https://geocoding.geo.census.gov/geocoder/
- Cache: `data/interim/geocode_cache.csv`. Role: coordinates for FDA addresses and 23 licenses without coordinates.

**U.S. Census Bureau.** (2026). *American Community Survey 5-year estimates, 2020-2024, tables B01001 (sex by age), B17001 (poverty status by sex and age) and B03002 (Hispanic or Latino origin by race), Allegheny County census tracts* [Data set]. Retrieved through Census Reporter. https://censusreporter.org/ (API: `https://api.censusreporter.org/1.0/data/show/latest`) **[verify release year]**
- Local file: `data/raw/acs5_latest_42003_tracts_v2.json` (release recorded in the file as `acs2024_5yr`). Role: tract youth share, poverty and minority share (not non-Hispanic White), with margins of error. Used only in the equity audit, never in scoring.

**National Center for Education Statistics.** (n.d.). *Education Demographic and Geographic Estimates (EDGE): Public school geocodes, 2023-2024* [Data set]. U.S. Department of Education. https://nces.ed.gov/programs/edge/data/EDGE_GEOCODE_PUBLICSCH_2324.zip
- Local file: `data/raw/EDGE_GEOCODE_PUBLICSCH_2324.zip` (256 schools near Pittsburgh).

**National Center for Education Statistics.** (n.d.). *Education Demographic and Geographic Estimates (EDGE): Private school geocodes, 2021-2022 (Private School Survey)* [Data set]. U.S. Department of Education. https://nces.ed.gov/programs/edge/data/EDGE_GEOCODE_PRIVATESCH_2122.zip
- Local file: `data/raw/EDGE_GEOCODE_PRIVATESCH_2122.zip` (95 schools). Older vintage than the public file.

**OpenStreetMap contributors.** (2026). *OpenStreetMap* [Map data, accessed through the Overpass API with OSMnx]. https://www.openstreetmap.org/copyright (Open Database License)
- Local files: `data/interim/youth_sites.csv` (libraries, community centres, childcare, playgrounds, parks, sports centres), `data/raw/osm_pgh_drive.graphml` (drive network, git-ignored), `data/interim/travel_time_matrix_<hash>.csv.gz`.

## B. Context and capacity sources

**U.S. Food and Drug Administration, Center for Tobacco Products.** (2026, June 4). *FDA tobacco retail inspection contracts*. https://www.fda.gov/tobacco-products/retail-sales-tobacco-products/fda-tobacco-retail-inspection-contracts
- Used for: Pennsylvania Department of Health award amounts (latest $1,159,731; total $16,038,592).

**Pennsylvania Department of Health.** (n.d.). *FDA program*. Commonwealth of Pennsylvania. https://www.pa.gov/agencies/health/programs/healthy-living/tobacco-prevention-and-control/fda-program
- Used for: "approximately 10,000" funded compliance checks per year; program ownership since 2010-2011.

**Pennsylvania Department of Health.** (n.d.). *Act 112*. Commonwealth of Pennsylvania. https://www.pa.gov/agencies/health/programs/healthy-living/tobacco-prevention-and-control/act-112
- Used for: scope context (no inspection frequency or data requirements stated).

**Office of Inspector General, U.S. Department of Health and Human Services.** (2023). *FDA could take stronger enforcement action against tobacco retailers with histories of sales to youth and other violations* (Report No. OEI-01-20-00240). https://oig.hhs.gov/oei/reports/OEI-01-20-00240.asp **[verify issue date]**
- Used for: FDA's escalating penalty schedule (Exhibit 3), 88% follow-up within 12 months (median 178 days), national coverage 74%, contractor-set coverage targets. Pages 7-13 of the PDF were read.

**HigherGov.** (n.d.). *Contract record 75F40125D00008: Pennsylvania Department of Health, tobacco retail compliance inspections*. https://www.highergov.com/idv/75F40125D00008
- Used for: contract period (9/30/2025-5/29/2030) and ceiling ($9.9M). Third-party aggregator; not an official record.

**Butler Eagle.** (2022, August). *[Title not captured: article on the Adagio Health tobacco compliance program]*. https://www.butlereagle.com/?p=201517 **[verify title and author]**
- Used for: contractor context only (weak source; not used for any parameter).

**Internal Revenue Service.** (2025). *IRS sets 2026 business standard mileage rate at 72.5 cents per mile, up 2.5 cents* (IR-2025-128). https://www.irs.gov/newsroom/irs-sets-2026-business-standard-mileage-rate-at-725-cents-per-mile-up-25-cents
- Used for: mileage reimbursement in the census cost model (72.5 cents Jan-Jun 2026). A mid-year revision to 76 cents effective July 1, 2026 appeared in search results but was not confirmed on the IRS page **[verify]**.

**U.S. Bureau of Labor Statistics.** (n.d.). *Occupational employment and wage statistics: Pittsburgh, PA metropolitan statistical area (38300), compliance officers (SOC 13-1041)*. U.S. Department of Labor. https://www.bls.gov/oes/2023/may/oes_38300.htm **[verify reference year; a search summary gave $35.28 an hour for both May 2023 and May 2024]**
- Used for: the supervisor wage proxy ($35.28 an hour) in the census cost model. A proxy occupation, not the actual job.

**1 Alpha Consulting.** (n.d.). *Federal tobacco undercover purchaser (under 21)* [Job posting]. https://talents.vaia.com/companies/1-alpha-consulting/federal-tobacco-undercover-purchaser-under-21-152338813/ **[verify: secondary job-board listing]**
- Used for: purchaser wage ($15.00 an hour plus mileage reimbursement; ages 16-20, driver's license and dependable transportation required).

**Western Pennsylvania Regional Data Center.** (2017). *Allegheny County tobacco vendors* [Data set, 2015 vintage]. https://data.wprdc.org/dataset/allegheny-county-tobacco-vendors
- Examined, **not used** (superseded by the daily state list).

**Substance Abuse and Mental Health Services Administration.** (n.d.). *About Synar*. https://www.samhsa.gov/synar/about-synar
- Listed in the project plan; context only (the Pennsylvania report in section A is the data source).

Not citable: a job posting for a Tobacco Adult Supervisor in Allegheny County (page returned 403; known only from a search-result snippet) and search-result summaries of the 2020 Pennsylvania Synar report (16.1% rate; not opened). Neither supports any parameter.

## C. Methods literature cited in the project

Abouk, R., & Adams, S. (2017). Compliance inspections of tobacco retailers and youth smoking. *American Journal of Health Economics, 3*(1), 10-32. https://doi.org/10.1162/AJHE_a_00065

Boeing, G. (2025). Modeling and analyzing urban networks and amenities with OSMnx. *Geographical Analysis, 57*(4), 567-577. https://doi.org/10.1111/gean.70009

Harrington, W. (1988). Enforcement leverage when penalties are restricted. *Journal of Public Economics, 37*(1), 29-53. **[verify DOI]**

Lee, J. G. L., Shook-Sa, B. E., Bowling, J. M., & Ribisl, K. M. (2018). Comparison of sampling strategies for tobacco retailer inspections to maximize coverage in vulnerable areas and minimize cost. *Nicotine & Tobacco Research, 20*(11), 1353-1358. https://doi.org/10.1093/ntr/ntx149

Paul, A., Freund, D., Ferber, A., Shmoys, D. B., & Williamson, D. P. (2020). Budgeted prize-collecting traveling salesman and minimum spanning tree problems. *Mathematics of Operations Research, 45*(2), 576-590. https://doi.org/10.1287/moor.2019.1002
- Note: an erratum (2023, https://doi.org/10.1287/moor.2022.1340) reports that the approximation guarantee does not hold for the rooted version; this project uses the budgeted PCTSP formulation only as a modeling frame and solves it exactly with a MILP, so the guarantee is not relied on.

Tangirala, M. K., McKyer, E. L. J., Goetze, D. D., & McCarthy-Jean, J. (2006). Use of tobacco retailer inspections to reduce tobacco sales to youth: Do inspections increase retailer compliance? *International Journal of Consumer Studies, 30*(3), 278-283. https://doi.org/10.1111/j.1470-6431.2006.00510.x

Stackelberg security games (lecture notes cited in the project plan): https://web2.qatar.cmu.edu/~gdicaro/15382-Spring18/additional/security-games.pdf **[verify author and title; the plan lists this link twice, once labeled Lee et al. (2018)]**

## D. Where each source lands (summary)

| Source | Raw file | Main outputs |
|---|---|---|
| PA DOH 2025 Synar report | `data/pdf/synar_report_2025.pdf` | `data/interim/synar_*.csv`; calibration; outlet types |
| PA DOR licenses | `data/raw/pa_licenses_allegheny_20260930.csv` | `retailer_universe.csv`, `location_features.csv` |
| FDA OCE compliance checks | `data/raw/OCE_FY*.zip` | `oce_pa_checks.csv.gz`, `fda_city_checks.csv.gz`, backtest |
| FDA data dashboard (PA) | `data/raw/fda-pa-*.xlsx` | `pa_tobacco_warning_letters_by_year.csv` |
| Census boundaries, geocoder | `data/raw/boundaries/`, geocoder cache | tract and city flags |
| ACS 2020-2024 | `data/raw/acs5_latest_42003_tracts_v2.json` | `acs_tracts.csv`, youth share, poverty, minority share |
| NCES public and private schools | `data/raw/EDGE_GEOCODE_*.zip` | `schools_pgh.csv`, exposure h_i |
| OpenStreetMap | `data/interim/youth_sites.csv`, drive network cache | exposure h_i, `travel_time_matrix_<hash>.csv.gz` |

## Terms of use and attribution

This is a summary for a class project, not legal advice; check each provider's current terms before reuse.

| Source | Terms to respect | Where it shows up |
|---|---|---|
| OpenStreetMap (youth sites, drive network) | Open Database License (ODbL): attribute "(c) OpenStreetMap contributors"; derived databases are share-alike | `data/interim/youth_sites.csv`, `travel_time_matrix_*.csv.gz` |
| FDA OCE compliance checks and Data Dashboard | U.S. government data; cite the FDA and the retrieval date. FDA states that a store's absence from the data does not mean it is compliant | `data/processed/oce_pa_checks.csv.gz`, `fda_city_checks.csv.gz` |
| PA Dept. of Revenue licenses (Open Data PA) | Published as open data; check the dataset page for its license and cite the dataset ID `ut72-sft8` | `data/interim/licenses_clean.csv`, `data/processed/retailer_universe.csv` |
| Census (TIGER, Geocoder, ACS via Census Reporter) | Public U.S. government data; cite the Census Bureau. Census Reporter terms apply to the API extract | `data/interim/acs_tracts.csv`, `data/raw/boundaries/` |
| NCES EDGE school locations | Public U.S. Department of Education data; cite NCES | `data/interim/schools_pgh.csv` |
| PA DOH 2025 Synar report | Public state report supplied as a PDF; cite the PA Department of Health | `data/pdf/synar_report_2025.pdf`, `data/interim/synar_*.csv` |
| This repository's code | MIT license (see `LICENSE`) | whole repository |
