"""Download and clean source data (`tobacco-inspect refresh`).

Sources (see docs/data-sources.md): PA Revenue active tobacco license list (data.pa.gov, daily),
FDA Tobacco Compliance Check outcomes (monthly; supplied as a file), Census TIGER boundaries,
NCES EDGE/PSS school locations, ACS 5-year tract estimates.
Raw files land in data/raw (git-ignored); cleaned files in data/interim.

The text-normalization helpers here are the single definition of `location_key` and
`retailer_entity_key` (moved from notebooks/01_EDA_Preprocessing.ipynb, unchanged in behavior).
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

USER_AGENT = "tobacco-inspect/0.1 (CMU 94-867 student project)"
TIMEOUT = 120


# --------------------------------------------------------------------------- normalization
def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper().str.replace(r"\s+", " ", regex=True)


def normalize_address(series: pd.Series) -> pd.Series:
    """Conservative: case/whitespace/punctuation only. No suffix substitutions."""
    return (
        normalize_text(series)
        .str.replace(r"[.,]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


_SUFFIXES = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "ROAD": "RD",
    "DRIVE": "DR",
    "LANE": "LN",
    "COURT": "CT",
    "PLACE": "PL",
    "HIGHWAY": "HWY",
    "PARKWAY": "PKWY",
    "SQUARE": "SQ",
    "TERRACE": "TER",
    "WAY": "WAY",
}
_DIRECTIONS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
_ORDINALS = {
    "FIRST": "1ST",
    "SECOND": "2ND",
    "THIRD": "3RD",
    "FOURTH": "4TH",
    "FIFTH": "5TH",
    "SIXTH": "6TH",
    "SEVENTH": "7TH",
    "EIGHTH": "8TH",
    "NINTH": "9TH",
    "TENTH": "10TH",
}


def match_address(series: pd.Series) -> pd.Series:
    """Aggressive address standardization used ONLY for cross-source matching.

    `location_key` stays conservative (notebook 01); this key is a lookup helper that must never
    be used to merge FDA entities, because it can collapse distinct source strings.
    """
    tokens = normalize_address(series).str.replace(r"[#]", " ", regex=True)
    tokens = tokens.str.replace(r"\s+(STE|SUITE|UNIT|APT|FL|FLOOR|RM|ROOM)\b.*$", "", regex=True)
    repl = {**_SUFFIXES, **_DIRECTIONS, **_ORDINALS}

    def fix(s):
        if pd.isna(s):
            return s
        return " ".join(repl.get(tok, tok) for tok in s.split())

    return tokens.map(fix)


def zip5(series: pd.Series) -> pd.Series:
    return series.astype("string").str.extract(r"(\d{5})", expand=False)


def add_location_keys(
    df: pd.DataFrame, name_col: str, street_col: str, zip_col: str
) -> pd.DataFrame:
    """Add normalized fields plus `location_key` and `retailer_entity_key` (notebook 01 rule)."""
    out = df.copy()
    out["retailer_name_normalized"] = normalize_text(out[name_col])
    out["street_address_normalized"] = normalize_address(out[street_col])
    out["zip5"] = zip5(out[zip_col])
    out["location_key"] = out["street_address_normalized"] + "|" + out["zip5"]
    out["retailer_entity_key"] = out["retailer_name_normalized"] + "|" + out["location_key"]
    return out


# --------------------------------------------------------------------------- downloads
def download(url: str, dest: Path, *, refresh: bool = False, params: dict | None = None) -> Path:
    """Download `url` to `dest` unless it is already cached. Returns the path."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0 and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True
    )
    resp.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(1 << 20):
            fh.write(chunk)
    tmp.replace(dest)
    return dest


def _stamp() -> str:
    return date.today().strftime("%Y%m%d")


def fetch_pa_licenses(raw_dir: Path, dataset: str, county: str = "ALLEGHENY", *, refresh=False):
    """Active Cigarette/OTP licenses for one county from data.pa.gov (Socrata, no key needed)."""
    existing = sorted(Path(raw_dir).glob(f"pa_licenses_{county.lower()}_*.csv"))
    if existing and not refresh:
        return existing[-1]
    dest = Path(raw_dir) / f"pa_licenses_{county.lower()}_{_stamp()}.csv"
    return download(
        f"https://data.pa.gov/resource/{dataset}.csv",
        dest,
        refresh=True,
        params={"$where": f"county='{county}'", "$limit": 50000},
    )


def fetch_boundaries(raw_dir: Path, state_fips: str, year: int) -> dict[str, Path]:
    base = f"https://www2.census.gov/geo/tiger/GENZ{year}/shp"
    out = {}
    for kind in ("tract", "place"):
        name = f"cb_{year}_{state_fips}_{kind}_500k.zip"
        out[kind] = download(f"{base}/{name}", Path(raw_dir) / "boundaries" / name)
    return out


def fetch_nces_schools(raw_dir: Path, public_year: str, private_year: str) -> dict[str, Path]:
    base = "https://nces.ed.gov/programs/edge/data"
    files = {
        "public": f"EDGE_GEOCODE_PUBLICSCH_{public_year}.zip",
        "private": f"EDGE_GEOCODE_PRIVATESCH_{private_year}.zip",
    }
    return {k: download(f"{base}/{v}", Path(raw_dir) / v) for k, v in files.items()}


def read_zipped_shapefile(path: Path, bbox: tuple[float, float, float, float] | None = None):
    """Read the (first) shapefile inside a zip as a GeoDataFrame, optionally bbox-filtered.

    `bbox` is (minx, miny, maxx, maxy) in the layer CRS (NAD83 lon/lat for NCES and Census files).
    """
    import geopandas as gpd

    with zipfile.ZipFile(path) as zf:
        shp = [n for n in zf.namelist() if n.lower().endswith(".shp")]
    if not shp:
        raise ValueError(f"no shapefile found in {path}")
    return gpd.read_file(f"zip://{Path(path).as_posix()}!{shp[0]}", bbox=bbox)


_ACS_TABLES = ["B01001", "B17001", "B03002"]


def fetch_acs_tracts(raw_dir: Path, state_fips: str, county_fips: str) -> Path:
    """ACS 5-year tract estimates and margins of error for one county via Census Reporter.

    Census Reporter serves the Census Bureau's ACS tables without an API key and includes the
    margin of error per estimate. The release (vintage) is recorded in the output JSON.
    """
    # _v2: adds B03002 (race/ethnicity); the older cache lacks it and download() would reuse it
    dest = Path(raw_dir) / f"acs5_latest_{state_fips}{county_fips}_tracts_v2.json"
    geo = f"140|05000US{state_fips}{county_fips}"
    return download(
        "https://api.censusreporter.org/1.0/data/show/latest",
        dest,
        params={"table_ids": ",".join(_ACS_TABLES), "geo_ids": geo},
    )


# --------------------------------------------------------------------------- cleaning
def clean_pa_licenses(path: Path) -> pd.DataFrame:
    """Parse the data.pa.gov license export into one row per license with lat/lon."""
    df = pd.read_csv(path, dtype=str)
    geo = df["georeferenced_latitude_longitude"].astype("string")
    coords = geo.str.extract(r"POINT \(\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)")
    df["lon"] = pd.to_numeric(coords[0], errors="coerce")
    df["lat"] = pd.to_numeric(coords[1], errors="coerce")
    df = add_location_keys(df, "trade_name", "street_address", "postal_code")
    df["match_street"] = match_address(df["street_address"])
    df["license_id"] = [
        hashlib.md5("|".join(map(str, row)).encode()).hexdigest()[:10]
        for row in zip(df["account"], df["license_type"], df["location_key"], strict=True)
    ]
    df["license_retail"] = df["license_type"].str.contains("Retail", na=False)
    df["license_vending_or_other"] = ~df["license_retail"]
    df["postal_city"] = normalize_text(df["city"])
    df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
    return df.drop(columns=["georeferenced_latitude_longitude"])


def refresh(config) -> None:
    """Download every source into data/raw and write cleaned tables to data/interim."""
    from tobacco_inspect.data import features, geocode, synar  # local import avoids a cycle

    synar.write_tables(config.path("interim"))
    geocode.build_retailer_universe(config)
    write_oce_outputs(config)
    features.build_features(config)


# --------------------------------------------------------------------------- FDA dashboard exports
def load_fda_pa_tobacco(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Tobacco rows from the FDA Data Dashboard exports filtered to Pennsylvania.

    Files (manual downloads, data/raw): `fda-pa-compliance-actions.xlsx` (warning letters etc.) and
    `fda-pa-inspections.xlsx` (establishment inspections). These cover all FDA product types and
    carry no street address. The inspections file's tobacco rows are manufacturers/vape makers,
    not retailer compliance checks, so only the warning letters are used for retail context.
    """
    raw_dir = Path(raw_dir)
    actions = pd.read_excel(raw_dir / "fda-pa-compliance-actions.xlsx", dtype=str)
    actions = actions[actions["Product Type"].eq("Tobacco")].copy()
    actions["action_date"] = pd.to_datetime(actions["Action Taken Date"], errors="coerce")
    actions["year"] = actions["action_date"].dt.year
    inspections = pd.read_excel(raw_dir / "fda-pa-inspections.xlsx", dtype=str)
    inspections = inspections[inspections["Product Type"].eq("Tobacco")].copy()
    return {"warning_letters": actions, "establishment_inspections": inspections}


def statewide_vs_pittsburgh(
    actions: pd.DataFrame, pittsburgh_records: pd.DataFrame
) -> pd.DataFrame:
    """PA tobacco warning letters per year next to Pittsburgh FDA records and warning letters."""
    pa = actions.groupby("year").size().rename("pa_tobacco_warning_letters")
    pgh = pittsburgh_records.copy()
    pgh["year"] = pgh["decision_date_parsed"].dt.year
    by_year = pgh.groupby("year").agg(
        pgh_records=("year", "size"),
        pgh_violations=("underage_sale_violation", "sum"),
    )
    if "Outcome" in pgh:
        wl = pgh[pgh["Outcome"].eq("Warning Letter")].groupby("year").size()
        by_year["pgh_warning_letters"] = wl
    out = pd.concat([pa, by_year], axis=1).fillna(0).astype(int).reset_index(names="year")
    out["pgh_wl_share_of_pa"] = (
        out["pgh_warning_letters"] / out["pa_tobacco_warning_letters"]
    ).round(3)
    return out


# --------------------------------------------------------------------------- FDA OCE checks
OCE_PATTERN = "OCE_FY*.zip"


def load_oce(raw_dir: Path, state: str | None = "PA") -> pd.DataFrame:
    """FDA retail compliance-check records (Office of Compliance and Enforcement), all fiscal years.

    `data/raw/OCE_FY<year>.zip` are national files in the same schema as the Pittsburgh export
    (fiscal year = Oct-Sep, by decision date). Filtered to `state` (None keeps every state).
    Adds parsed dates, the underage-sale outcome, keys (notebook-01 rule) and `fy`.
    """
    frames = []
    for path in sorted(Path(raw_dir).glob(OCE_PATTERN)):
        fy = int(re.search(r"FY(\d{4})", path.name).group(1))
        # chunked: the national files are large and a one-shot read has crashed pandas on Windows
        chunks = pd.read_csv(path, dtype=str, encoding="utf-8-sig", chunksize=20000)
        for chunk in chunks:
            if state:
                chunk = chunk[chunk["State"].eq(state)]
            frames.append(chunk.assign(fy=fy))
    if not frames:
        raise FileNotFoundError(f"no {OCE_PATTERN} files in {raw_dir}")
    out = pd.concat(frames, ignore_index=True)
    out = add_location_keys(out, "Retailer Name", "Street Address", "Zip")
    out["decision_date_parsed"] = pd.to_datetime(out["Decision Date"], errors="coerce")
    out["inspection_date_parsed"] = pd.to_datetime(out["Inspection Date"], errors="coerce")
    out["underage_sale_violation"] = (out["Sale to UP"] == "Yes").astype("int8")
    out["up_involved"] = out["UP Involved"].eq("Yes")
    out["postal_pittsburgh"] = out["City"].str.upper().str.contains("PITTSBURGH", na=False)
    return out


def oce_by_fiscal_year(oce: pd.DataFrame, city_keys: set | None = None) -> pd.DataFrame:
    """Records, UP-involved checks and violations per fiscal year, statewide and Pittsburgh."""
    up = oce[oce["up_involved"]]
    pgh = up[up["postal_pittsburgh"]]
    table = (
        pd.DataFrame(
            {
                "records": oce.groupby("fy").size(),
                "up_checks": up.groupby("fy").size(),
                "violations": up.groupby("fy")["underage_sale_violation"].sum(),
                "pgh_up_checks": pgh.groupby("fy").size(),
                "pgh_violations": pgh.groupby("fy")["underage_sale_violation"].sum(),
            }
        )
        .fillna(0)
        .astype(int)
    )
    if city_keys is not None:
        city = up[up["location_key"].isin(city_keys)]
        table["city_up_checks"] = city.groupby("fy").size()
        table["city_violations"] = city.groupby("fy")["underage_sale_violation"].sum()
        table = table.fillna(0).astype(int)
        table["city_violation_rate"] = (table["city_violations"] / table["city_up_checks"]).round(3)
        table["city_share_of_checks"] = (table["city_up_checks"] / table["up_checks"]).round(3)
    table["violation_rate"] = (table["violations"] / table["up_checks"]).round(3)
    table["pgh_violation_rate"] = (table["pgh_violations"] / table["pgh_up_checks"]).round(3)
    table["pgh_share_of_checks"] = (table["pgh_up_checks"] / table["up_checks"]).round(3)
    return table.reset_index()


def followup_intervals(oce: pd.DataFrame) -> pd.DataFrame:
    """Days from each violation record to the next record at the same `location_key`.

    Compares with OIG (median 178 days; 88% followed up within 12 months). Records without a later
    record at the location are censored (right-censored at the last decision date in the data).
    """
    d = oce[oce["up_involved"]].sort_values(["location_key", "decision_date_parsed"]).copy()
    d["next_decision"] = d.groupby("location_key")["decision_date_parsed"].shift(-1)
    v = d[d["underage_sale_violation"] == 1].copy()
    v["days_to_next"] = (v["next_decision"] - v["decision_date_parsed"]).dt.days
    return v[["location_key", "fy", "postal_pittsburgh", "decision_date_parsed", "days_to_next"]]


def write_oce_outputs(config) -> None:
    """Write the fiscal-year table and a compact PA undercover-check file (if OCE zips exist)."""
    raw = config.path("raw")
    if not list(raw.glob(OCE_PATTERN)):
        print("OCE_FY*.zip not found in data/raw; skipping statewide FDA tables")
        return
    oce = load_oce(raw)
    locs = config.path("interim") / "fda_locations.csv"
    city_keys = None
    if locs.exists():
        fl = pd.read_csv(locs, dtype={"location_key": str})
        city_keys = set(fl.loc[fl["city_scope"].eq("in_city"), "location_key"])
    oce_by_fiscal_year(oce, city_keys).to_csv(
        config.path("interim") / "oce_pa_by_fiscal_year.csv", index=False
    )
    cols = [
        "Retailer Name",
        "Street Address",
        "City",
        "Zip",
        "up_involved",
        "Sale to UP",
        "Product Type",
        "Outcome",
        "decision_date_parsed",
        "inspection_date_parsed",
        "fy",
        "location_key",
        "retailer_entity_key",
        "underage_sale_violation",
        "postal_pittsburgh",
    ]
    out = oce.loc[oce["up_involved"], cols]
    out.to_csv(config.path("processed") / "oce_pa_checks.csv.gz", index=False, compression="gzip")
