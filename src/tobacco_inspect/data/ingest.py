"""Download and clean source data (`tobacco-inspect refresh`).

Sources (see docs/data-sources.md): PA Revenue active tobacco license list (annual, Feb),
FDA Tobacco Compliance Check outcomes (monthly), ACS 5-year, NCES EDGE schools, WPRDC boundaries.
Raw files land in data/raw (git-ignored); cleaned files in data/interim.

TODO: implement. Retailer universe = license list filtered to the City of Pittsburgh.
"""


def refresh(config) -> None:
    raise NotImplementedError("data refresh is not implemented yet")
