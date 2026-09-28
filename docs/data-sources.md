# Data sources

From the project plan. Links were copied from it and are not yet re-verified; check each before use
and record retrieval dates in [data/README.md](../data/README.md).

| Source | URL |
|---|---|
| FDA Tobacco Compliance Check Outcomes | https://www.fda.gov/tobacco-products/compliance-enforcement-training/advisory-and-enforcement-actions-against-industry-selling-tobacco-products-underage-purchasers |
| PA Dept. of Revenue tobacco licensing | https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/tobacco-products/tobacco-products-taxes-licensing |
| Act 57 of 2025 (vape directory, licensing) | https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/tobacco-products/requirements-for-tobacco-products-and-licensing |
| PA DOH FDA compliance program | https://www.pa.gov/agencies/health/programs/healthy-living/tobacco-prevention-and-control/fda-program |
| SAMHSA Synar program | https://www.samhsa.gov/synar/about-synar |
| Open Data Pennsylvania (active license list) | https://data.pa.gov/ |
| Census Geocoder | https://geocoder.census.gov/ |
| ACS 5-year data and API | https://www.census.gov/data/developers/data-sets/acs-5year.html |
| NCES EDGE (school locations) | https://nces.ed.gov/programs/edge/ |
| WPRDC (Pittsburgh open data, boundaries) | https://data.wprdc.org/ |

## Known data limitations (from the roundtable; verify)
- FDA outcomes are address-level (decision date, violation, product) but cover only inspected
  stores, and inspections were not randomly assigned: absence is not compliance.
- Synar is a state-level probability sample of youth purchase attempts: use for calibration, not
  retailer-level labels. Base rate is low, so positives are sparse: use regularized/shrinkage models.
- License list is per location and expires end of February (annual refresh); FDA database updates
  monthly and covers brick-and-mortar stores only.
- ACS block-group estimates carry large margins of error.
