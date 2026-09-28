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
| PA Revenue active cigarette/OTP license list (data.pa.gov) | Annual (licenses expire end of Feb) | | | Retailer universe (denominator) |
| FDA Tobacco Compliance Check outcomes | Monthly | | | Inspected stores only: selection bias |
| SAMHSA / PA Synar survey | Annual | | | State-level calibration only |
| ACS 5-year (Census API) | Annual | | | Block-group margins of error are large |
| NCES EDGE school locations | Annual | | | |
| WPRDC boundaries / Census Geocoder | As needed | | | Tracts, not ZIP codes (MAUP) |
