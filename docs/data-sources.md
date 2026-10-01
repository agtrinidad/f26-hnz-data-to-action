# Data sources

From the project plan. Link check run 2026-09-30 (see Status column); retrieval dates are in [data/README.md](../data/README.md).
APA-formatted catalog with local files and outputs: [data-sources-apa.md](data-sources-apa.md).
Tier and use of each source: see [process/02_Data_Acquisition_Memo.md](process/02_Data_Acquisition_Memo.md).

| Source | URL | Tier / status (2026-09-30) |
|---|---|---|
| FDA Tobacco Compliance Check Outcomes | https://www.fda.gov/tobacco-products/compliance-enforcement-training/advisory-and-enforcement-actions-against-industry-selling-tobacco-products-underage-purchasers | Must. Have 1,816-record export; FDA database blocks scripted access (manual pulls). This URL is the enforcement-actions page, largely redundant |
| PA Dept. of Revenue tobacco licensing | https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/tobacco-products/tobacco-products-taxes-licensing | Documentation only. Reachable |
| Act 57 of 2025 (vape directory, licensing) | https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/tobacco-products/requirements-for-tobacco-products-and-licensing |  |
| PA DOH FDA compliance program | https://www.pa.gov/agencies/health/programs/healthy-living/tobacco-prevention-and-control/fda-program | Documentation; source of the 10,000/yr figure. Verified |
| SAMHSA Synar program | https://www.samhsa.gov/synar/about-synar | Context only; the PA DOH 2025 Synar report (data/pdf) is now the data source and the random-sample benchmark |
| Open Data Pennsylvania (active license list) | https://data.pa.gov/ |  |
| Census Geocoder | https://geocoder.census.gov/ | Must. Batch API used |
| ACS 5-year data and API | https://www.census.gov/data/developers/data-sets/acs-5year.html | Should. API needs a key; pulled via Census Reporter instead (2020-2024) |
| NCES EDGE (school locations) | https://nces.ed.gov/programs/edge/ |  |
| WPRDC (Pittsburgh open data, boundaries) | https://data.wprdc.org/ | Optional. Tobacco vendors dataset is 2015 only; boundaries taken from Census TIGER |

## Known data limitations (from the roundtable; verify)
- FDA outcomes are address-level (decision date, violation, product) but cover only inspected
  stores, and inspections were not randomly assigned: absence is not compliance.
- Synar is a state-level probability sample of youth purchase attempts: use for calibration, not
  retailer-level labels. Base rate is low, so positives are sparse: use regularized/shrinkage models.
- License list is per location and expires end of February (annual refresh); FDA database updates
  monthly and covers brick-and-mortar stores only.
- ACS block-group estimates carry large margins of error.

## Added sources (not in the original list)
- FDA OCE national compliance-check files FY2011-FY2026 (team download): the full source behind the Pittsburgh export; gives PA statewide context and training data.
- Census TIGER cartographic boundaries 2023 (tracts, Pittsburgh city place): needed for tract and city-limits flags.
- NCES Private School Survey (PSS) locations: private schools are not in EDGE public files.
- OpenStreetMap (osmnx): libraries, community centres, childcare, playgrounds, parks as exposure sites.
- OIG report OEI-01-20-00240 and FDA contracts page: program context and capacity proxies ([sources/README.md](sources/README.md)).
