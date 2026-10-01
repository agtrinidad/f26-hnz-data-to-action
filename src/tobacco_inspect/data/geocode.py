"""Geocode retailer addresses, assign census tracts, and build the retailer universe.

The universe is the PA Revenue active license list (data.pa.gov, which already carries
coordinates for almost every row). The Census Geocoder fills the gaps and geocodes the FDA
inspection locations. Results are cached in data/interim so reruns are offline.

Outputs
- data/interim/geocode_cache.csv         address-level cache of Census Geocoder results
- data/interim/licenses_clean.csv        Allegheny licenses with tract/city flags
- data/interim/fda_locations.csv         FDA locations (notebook 01 `location_key`) geocoded
- data/interim/match_review.csv          ambiguous / unmatched rows for a human to review
- data/processed/retailer_universe.csv   Pittsburgh-scope licenses + FDA match + history summary
"""

from __future__ import annotations

import io
import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from tobacco_inspect.data import ingest

BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BATCH_SIZE = 1000
GEOCODE_COLUMNS = ["location_key", "street", "city", "state", "zip5", "match", "lon", "lat"]
NAME_NOISE = re.compile(r"\b(LLC|INC|CORP|CO|LTD|LP|THE|OF|AND|STORE|MART|SHOP)\b|[^A-Z0-9 ]")


# --------------------------------------------------------------------------- Census geocoder
def _batch_request(rows: pd.DataFrame) -> pd.DataFrame:
    buf = io.StringIO()
    rows[["location_key", "street", "city", "state", "zip5"]].to_csv(buf, header=False, index=False)
    resp = requests.post(
        BATCH_URL,
        files={"addressFile": ("addresses.csv", buf.getvalue())},
        data={"benchmark": "Public_AR_Current"},
        headers={"User-Agent": ingest.USER_AGENT},
        timeout=ingest.TIMEOUT * 3,
    )
    resp.raise_for_status()
    parsed = pd.read_csv(
        io.StringIO(resp.text),
        header=None,
        dtype=str,
        names=[
            "location_key",
            "input",
            "match",
            "match_type",
            "matched",
            "coords",
            "tiger",
            "side",
        ],
        keep_default_na=False,
    )
    coords = parsed["coords"].str.extract(r"(-?\d+\.\d+),(-?\d+\.\d+)")
    parsed["lon"] = pd.to_numeric(coords[0], errors="coerce")
    parsed["lat"] = pd.to_numeric(coords[1], errors="coerce")
    return parsed[["location_key", "match", "lon", "lat"]]


def geocode_addresses(addresses: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """Geocode rows with columns location_key, street, city, state, zip5; cache by location_key."""
    cache_path = Path(cache_path)
    cache = (
        pd.read_csv(cache_path, dtype={"location_key": str, "zip5": str})
        if cache_path.exists()
        else pd.DataFrame(columns=GEOCODE_COLUMNS)
    )
    todo = addresses.drop_duplicates("location_key")
    todo = todo[~todo["location_key"].isin(cache["location_key"])]
    fresh = []
    for start in range(0, len(todo), BATCH_SIZE):
        chunk = todo.iloc[start : start + BATCH_SIZE]
        res = _batch_request(chunk)
        fresh.append(
            chunk.drop(columns=["lon", "lat"], errors="ignore").merge(res, on="location_key")
        )
    if fresh:
        cache = pd.concat([cache, *fresh], ignore_index=True)[GEOCODE_COLUMNS]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache.to_csv(cache_path, index=False)
    return cache


# --------------------------------------------------------------------------- spatial joins
def _points(df: pd.DataFrame):
    import geopandas as gpd

    ok = df["lon"].notna() & df["lat"].notna()
    gdf = gpd.GeoDataFrame(
        df.loc[ok].copy(),
        geometry=gpd.points_from_xy(df.loc[ok, "lon"], df.loc[ok, "lat"]),
        crs="EPSG:4269",
    )
    return gdf


def assign_geography(df: pd.DataFrame, tracts, place) -> pd.DataFrame:
    """Add tract_geoid and in_city_limits using point-in-polygon joins (no network)."""
    import geopandas as gpd

    out = df.copy()
    out["tract_geoid"] = pd.NA
    out["in_city_limits"] = False
    pts = _points(out)
    if pts.empty:
        return out
    joined = gpd.sjoin(pts, tracts[["GEOID", "geometry"]], how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    out.loc[joined.index, "tract_geoid"] = joined["GEOID"]
    city = gpd.sjoin(pts, place[["geometry"]], how="left", predicate="within")
    city = city[~city.index.duplicated(keep="first")]
    out.loc[city.index, "in_city_limits"] = city["index_right"].notna()
    return out


def _distance_m(a: pd.DataFrame, b: pd.DataFrame) -> np.ndarray:
    """Pairwise distance matrix in meters (rows of a x rows of b) in EPSG:32617."""

    ga = _points(a).to_crs("EPSG:32617")
    gb = _points(b).to_crs("EPSG:32617")
    xa = np.c_[ga.geometry.x, ga.geometry.y]
    xb = np.c_[gb.geometry.x, gb.geometry.y]
    return np.sqrt(((xa[:, None, :] - xb[None, :, :]) ** 2).sum(-1))


# --------------------------------------------------------------------------- FDA history
def load_fda_history(raw_dir: Path) -> pd.DataFrame:
    """FDA compliance-check records (Pittsburgh, UP involved).

    Prefers the original FDA export (`Pittsburgh Inspections.csv`, 7 preamble rows); falls back to
    the notebook-01 cleaned file, which keeps all original columns and the same keys.
    Rows outside Pennsylvania are dropped: the export's "City contains Pittsburgh" filter also
    caught 4 South Pittsburg, TN records (FDA spells it "S PITTSBURGH"; found by reconciling
    with the OCE national files).
    """
    raw_dir = Path(raw_dir)
    original = raw_dir / "Pittsburgh Inspections.csv"
    if original.exists():
        df = pd.read_csv(original, skiprows=7, dtype=str)
        df = ingest.add_location_keys(df, "Retailer Name", "Street Address", "Zip")
        df["decision_date_parsed"] = pd.to_datetime(df["Decision Date"], errors="coerce")
        df["inspection_date_parsed"] = pd.to_datetime(df["Inspection Date"], errors="coerce")
        df["underage_sale_violation"] = df["Sale to UP"].map({"Yes": 1, "No": 0}).astype("int8")
        return df[df["State"].eq("PA")].reset_index(drop=True)
    cleaned = raw_dir / "pittsburgh_inspections_cleaned.csv"
    if not cleaned.exists():
        raise FileNotFoundError(
            "FDA export not found: place 'Pittsburgh Inspections.csv' (or the notebook-01 "
            f"cleaned file) in {raw_dir}"
        )
    df = pd.read_csv(cleaned, dtype=str)
    for col in ("decision_date_parsed", "inspection_date_parsed"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["underage_sale_violation"] = df["underage_sale_violation"].astype(int)
    return df[df["State"].eq("PA")].reset_index(drop=True)


def summarize_fda_locations(fda: pd.DataFrame) -> pd.DataFrame:
    """One row per FDA `location_key` with history counts (descriptive, full-history)."""
    g = fda.sort_values("decision_date_parsed").groupby("location_key")
    return g.agg(
        fda_street=("Street Address", "last"),
        fda_city=("City", "last"),
        fda_state=("State", "last"),
        zip5=("zip5", "last"),
        fda_names=("retailer_name_normalized", lambda s: " | ".join(sorted(set(s)))),
        fda_records=("location_key", "size"),
        fda_violations=("underage_sale_violation", "sum"),
        fda_first_decision=("decision_date_parsed", "min"),
        fda_last_decision=("decision_date_parsed", "max"),
    ).reset_index()


# --------------------------------------------------------------------------- matching
def _name_tokens(name: str) -> str:
    return re.sub(r"\s+", " ", NAME_NOISE.sub(" ", str(name).upper())).strip()


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _name_tokens(a), _name_tokens(b)).ratio()


def match_fda_to_licenses(fda_loc: pd.DataFrame, lic: pd.DataFrame, radius_m: float = 75.0):
    """Match each FDA location to license rows.

    Tier 1 `address`: same ZIP5 and same aggressively standardized street. Tier 2 `proximity`:
    geocoded points within `radius_m` and name similarity >= 0.55. Everything else is unmatched.
    A location can match several licenses (multiple tenants); all are returned.
    """
    fda_loc = fda_loc.copy()
    fda_loc["match_street"] = ingest.match_address(fda_loc["fda_street"])
    rows = []
    lic_idx = lic.reset_index(drop=True)
    dist = None
    ok_f = fda_loc["lon"].notna()
    ok_l = lic_idx["lon"].notna()
    if ok_f.any() and ok_l.any():
        dist = pd.DataFrame(
            _distance_m(fda_loc[ok_f], lic_idx[ok_l]),
            index=fda_loc.index[ok_f],
            columns=lic_idx.index[ok_l],
        )
    for fi, f in fda_loc.iterrows():
        hits = lic_idx[
            (lic_idx["zip5"] == f["zip5"]) & (lic_idx["match_street"] == f["match_street"])
        ]
        for li in hits.index:
            rows.append((f["location_key"], li, "address", np.nan))
        if hits.empty and dist is not None and fi in dist.index:
            near = dist.loc[fi][dist.loc[fi] <= radius_m]
            for li, d in near.items():
                names = f["fda_names"].split(" | ")
                sim = max(name_similarity(n, lic_idx.loc[li, "trade_name"]) for n in names)
                sim = max(
                    sim, max(name_similarity(n, lic_idx.loc[li, "legal_name"]) for n in names)
                )
                if sim >= 0.55:
                    rows.append((f["location_key"], li, "proximity", float(d)))
    links = pd.DataFrame(rows, columns=["location_key", "lic_index", "match_tier", "distance_m"])
    return links, lic_idx


SCOPE_KEEP = {"city_limits": ("in_city",), "postal": ("in_city", "outside_city", "unknown")}


def assign_city_scope(fda_loc: pd.DataFrame, links: pd.DataFrame, scope_lic: pd.DataFrame):
    """Label each FDA location in_city / outside_city / unknown.

    Geocoded locations use the city-limits polygon. Locations the Census Geocoder could not place
    inherit the flag of a license matched by address; if none, they stay `unknown` (reported,
    excluded from the city scope).
    """
    out = fda_loc.copy()
    out["city_scope"] = np.where(
        out["lon"].notna(), np.where(out["in_city_limits"], "in_city", "outside_city"), "unknown"
    )
    unknown = out["city_scope"].eq("unknown")
    if unknown.any() and not links.empty:
        by_addr = links[links["match_tier"].eq("address")].copy()
        by_addr["lic_in_city"] = by_addr["lic_index"].map(
            scope_lic["in_city_limits"].reset_index(drop=True)
        )
        inherit = by_addr.groupby("location_key")["lic_in_city"].max()
        mapped = out.loc[unknown, "location_key"].map(inherit)
        out.loc[unknown & mapped.eq(True).reindex(out.index, fill_value=False), "city_scope"] = (
            "in_city"
        )
        out.loc[unknown & mapped.eq(False).reindex(out.index, fill_value=False), "city_scope"] = (
            "outside_city"
        )
    return out


# --------------------------------------------------------------------------- orchestration
def build_retailer_universe(config) -> pd.DataFrame:
    cfg = config.raw["data"]
    raw, interim, processed = config.path("raw"), config.path("interim"), config.path("processed")
    for d in (interim, processed):
        d.mkdir(parents=True, exist_ok=True)

    lic = ingest.clean_pa_licenses(ingest.fetch_pa_licenses(raw, cfg["pa_license_dataset"]))
    bounds = ingest.fetch_boundaries(raw, cfg["state_fips"], int(cfg["tiger_year"]))
    tracts = ingest.read_zipped_shapefile(bounds["tract"])
    tracts = tracts[tracts["COUNTYFP"] == cfg["county_fips"]]
    place_all = ingest.read_zipped_shapefile(bounds["place"])
    place = place_all[place_all["GEOID"] == cfg["city_place_geoid"]]
    if place.empty:
        raise ValueError(f"place {cfg['city_place_geoid']} not found in boundary file")

    # Fill license coordinates the state file lacks, then geocode FDA locations.
    cache_path = interim / "geocode_cache.csv"
    fda = load_fda_history(raw)
    fda_loc = summarize_fda_locations(fda)
    need = lic[lic["lon"].isna()].assign(
        street=lambda d: d["street_address"], city=lambda d: d["city"], state=lambda d: d["state"]
    )
    fda_addr = fda_loc.rename(
        columns={"fda_street": "street", "fda_city": "city", "fda_state": "state"}
    )
    cache = geocode_addresses(
        pd.concat(
            [
                need[["location_key", "street", "city", "state", "zip5"]],
                fda_addr[["location_key", "street", "city", "state", "zip5"]],
            ]
        ),
        cache_path,
    )
    coords = cache.drop_duplicates("location_key").set_index("location_key")[["lon", "lat"]]
    fill = lic["lon"].isna() & lic["location_key"].isin(coords.index)
    lic.loc[fill, "lon"] = lic.loc[fill, "location_key"].map(coords["lon"])
    lic.loc[fill, "lat"] = lic.loc[fill, "location_key"].map(coords["lat"])
    lic["coord_source"] = np.where(fill, "census_geocoder", "data.pa.gov")
    fda_loc = fda_loc.join(coords, on="location_key")

    lic = assign_geography(lic, tracts, place)
    fda_loc = assign_geography(fda_loc, tracts, place)
    lic["postal_pittsburgh"] = lic["postal_city"].eq("PITTSBURGH")
    lic.to_csv(interim / "licenses_clean.csv", index=False)
    fda_loc.to_csv(interim / "fda_locations.csv", index=False)

    scope = lic[lic["in_city_limits"] | lic["postal_pittsburgh"]].copy()
    links, scope = match_fda_to_licenses(fda_loc, scope)
    fda_loc = assign_city_scope(fda_loc, links, scope)
    fda_loc.to_csv(interim / "fda_locations.csv", index=False)
    fda_loc[fda_loc["city_scope"].eq("unknown")].to_csv(
        interim / "fda_scope_unknown.csv", index=False
    )
    by_lic = links.merge(
        fda_loc[
            [
                "location_key",
                "fda_records",
                "fda_violations",
                "fda_last_decision",
                "fda_first_decision",
                "fda_names",
            ]
        ],
        on="location_key",
    )
    # A license keeps its best tier (address beats proximity); FDA history is summed per location.
    by_lic["tier_rank"] = by_lic["match_tier"].map({"address": 0, "proximity": 1})
    best = by_lic.sort_values(["lic_index", "tier_rank"]).drop_duplicates(
        ["lic_index", "location_key"]
    )
    agg = best.groupby("lic_index").agg(
        fda_location_keys=("location_key", lambda s: " || ".join(s)),
        fda_match_tier=("match_tier", "first"),
        fda_match_distance_m=("distance_m", "min"),
        fda_records=("fda_records", "sum"),
        fda_violations=("fda_violations", "sum"),
        fda_first_decision=("fda_first_decision", "min"),
        fda_last_decision=("fda_last_decision", "max"),
    )
    universe = scope.join(agg)
    universe["fda_observed"] = universe["fda_records"].notna()
    universe["fda_records"] = universe["fda_records"].fillna(0).astype(int)
    universe["fda_violations"] = universe["fda_violations"].fillna(0).astype(int)
    universe["retail_license"] = universe["license_retail"]
    universe.to_csv(interim / "retailer_universe_postal.csv", index=False)

    # Project scope (config data.scope): City of Pittsburgh limits by default.
    in_scope = fda_loc["city_scope"].isin(SCOPE_KEEP[cfg.get("scope", "city_limits")])
    if cfg.get("scope", "city_limits") == "city_limits":
        universe = universe[universe["in_city_limits"]].copy()
    universe.to_csv(processed / "retailer_universe.csv", index=False)
    fda_scope_keys = set(fda_loc.loc[in_scope, "location_key"])
    fda_in_scope = fda[fda["location_key"].isin(fda_scope_keys)].merge(
        fda_loc[["location_key", "city_scope", "tract_geoid"]], on="location_key", how="left"
    )
    keep = [
        "Retailer Name",
        "Street Address",
        "City",
        "Zip",
        "Sale to UP",
        "Outcome",
        "decision_date_parsed",
        "inspection_date_parsed",
        "location_key",
        "retailer_entity_key",
        "underage_sale_violation",
        "city_scope",
        "tract_geoid",
    ]
    fda_in_scope[keep].to_csv(processed / "fda_city_checks.csv.gz", index=False, compression="gzip")

    matched_locs = set(links["location_key"])
    review_fda = fda_loc[~fda_loc["location_key"].isin(matched_locs) & in_scope].assign(
        issue="fda_location_without_license"
    )
    prox = by_lic[by_lic["match_tier"] == "proximity"]
    multi = links.groupby("location_key").filter(lambda g: g["lic_index"].nunique() > 1)
    in_scope_lic = set(universe.index)
    prox = prox[prox["lic_index"].isin(in_scope_lic)].assign(issue="proximity_match_needs_review")
    multi = multi[multi["lic_index"].isin(in_scope_lic)].assign(
        issue="location_matches_multiple_licenses"
    )
    review = pd.concat([review_fda, prox, multi], ignore_index=True, sort=False)
    review.to_csv(interim / "match_review.csv", index=False)
    return universe
