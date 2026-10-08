"""Build per-retailer features: school proximity (NCES), youth sites, ACS tract context, store type.

Per docs/decision-card.md, features describe store behavior and youth exposure, not demographic
proxies (equity feedback-loop concern). ACS values are attached for exposure weighting and equity
*reporting*; their margins of error are carried along and flagged, never hidden.

Outputs
- data/interim/schools_pgh.csv      public (NCES EDGE) + private (PSS) schools near Pittsburgh
- data/interim/youth_sites.csv      OSM libraries, community centres, childcare, playgrounds, parks
- data/interim/acs_tracts.csv       Allegheny tract estimates with margins of error
- data/processed/location_features.csv   one row per license in the retailer universe
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tobacco_inspect.data import geocode, ingest, synar

PGH_BBOX = (-80.35, 40.30, -79.75, 40.60)  # lon/lat box around the city plus a margin
UTM17N = "EPSG:32617"


# --------------------------------------------------------------------------- schools and sites
def load_schools(config) -> pd.DataFrame:
    cfg = config.raw["data"]
    paths = ingest.fetch_nces_schools(
        config.path("raw"), cfg["nces_public_school_year"], cfg["nces_private_school_year"]
    )
    pub = ingest.read_zipped_shapefile(paths["public"], PGH_BBOX)
    pri = ingest.read_zipped_shapefile(paths["private"], PGH_BBOX)
    schools = pd.concat(
        [
            pd.DataFrame(
                {
                    "school_id": pub["NCESSCH"],
                    "school_name": pub["NAME"],
                    "sector": "public",
                    "year": pub["SCHOOLYEAR"],
                    "lon": pub["LON"].astype(float),
                    "lat": pub["LAT"].astype(float),
                }
            ),
            pd.DataFrame(
                {
                    "school_id": pri["PPIN"],
                    "school_name": pri["NAME"],
                    "sector": "private",
                    "year": pri["SCHOOLYEAR"],
                    "lon": pri["LON"].astype(float),
                    "lat": pri["LAT"].astype(float),
                }
            ),
        ],
        ignore_index=True,
    )
    out = config.path("interim") / "schools_pgh.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    schools.to_csv(out, index=False)
    return schools


YOUTH_TAGS = {
    "amenity": ["library", "community_centre", "childcare", "kindergarten", "youth_centre"],
    "leisure": ["playground", "park", "sports_centre", "pitch"],
}


def load_youth_sites(config, *, refresh: bool = False) -> pd.DataFrame:
    """Non-school youth sites from OpenStreetMap (cached); empty if Overpass is unreachable."""
    cache = config.path("interim") / "youth_sites.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)
    try:
        import osmnx as ox

        ox.settings.cache_folder = str(config.path("raw") / "osmnx_cache")

        feats = ox.features_from_bbox(
            bbox=(PGH_BBOX[0], PGH_BBOX[1], PGH_BBOX[2], PGH_BBOX[3]), tags=YOUTH_TAGS
        )
    except Exception as exc:  # network/Overpass failures must not break the pipeline
        print(f"youth sites unavailable ({exc}); continuing without them")
        return pd.DataFrame(columns=["site_type", "site_name", "lon", "lat"])
    feats = feats.to_crs("EPSG:4326")
    cent = feats.to_crs(UTM17N).geometry.centroid.to_crs("EPSG:4326")

    def kind(row):
        for key in ("amenity", "leisure"):
            if key in row and pd.notna(row[key]):
                return f"{key}:{row[key]}"
        return "other"

    sites = pd.DataFrame(
        {
            "site_type": feats.apply(kind, axis=1).values,
            "site_name": feats["name"].values if "name" in feats else None,
            "lon": cent.x.values,
            "lat": cent.y.values,
        }
    )
    sites.to_csv(cache, index=False)
    return sites


# --------------------------------------------------------------------------- ACS
def _moe_sum(moes: list[float]) -> float:
    return float(np.sqrt(np.sum(np.square(moes))))


def parse_acs_tracts(path: Path) -> pd.DataFrame:
    """Turn the Census Reporter JSON into tract rows: youth, poverty, minority shares + MOE."""
    blob = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    male_u18 = ["B01001003", "B01001004", "B01001005", "B01001006"]
    female_u18 = ["B01001027", "B01001028", "B01001029", "B01001030"]
    for geoid, tables in blob["data"].items():
        b1, b17 = tables["B01001"], tables["B17001"]
        est, err = b1["estimate"], b1["error"]
        total, total_moe = est["B01001001"], err["B01001001"]
        u18_cols = male_u18 + female_u18
        u18 = sum(est[c] for c in u18_cols)
        u18_moe = _moe_sum([err[c] for c in u18_cols])
        pov_n, pov_tot = b17["estimate"]["B17001002"], b17["estimate"]["B17001001"]
        pov_moe, tot_moe = b17["error"]["B17001002"], b17["error"]["B17001001"]
        share = u18 / total if total else np.nan
        # Minority = everyone but non-Hispanic White alone (B03002003), over the B03002 total.
        b3 = tables["B03002"]
        race_tot, race_tot_moe = b3["estimate"]["B03002001"], b3["error"]["B03002001"]
        nhw, nhw_moe = b3["estimate"]["B03002003"], b3["error"]["B03002003"]
        minority = race_tot - nhw
        minority_moe = _moe_sum([race_tot_moe, nhw_moe])

        # Census ratio MOE for a proportion (numerator is a subset of the denominator).
        def prop_moe(num, den, num_moe, den_moe):
            if not den:
                return np.nan
            p = num / den
            inner = num_moe**2 - (p**2) * den_moe**2
            inner = inner if inner >= 0 else num_moe**2 + (p**2) * den_moe**2
            return float(np.sqrt(inner) / den)

        rows.append(
            {
                "tract_geoid": geoid.split("US")[-1],
                "acs_total_pop": total,
                "acs_total_pop_moe": total_moe,
                "acs_under18": u18,
                "acs_under18_moe": u18_moe,
                "acs_youth_share": share,
                "acs_youth_share_moe": prop_moe(u18, total, u18_moe, total_moe),
                "acs_poverty_universe": pov_tot,
                "acs_poverty_n": pov_n,
                "acs_poverty_rate": pov_n / pov_tot if pov_tot else np.nan,
                "acs_poverty_rate_moe": prop_moe(pov_n, pov_tot, pov_moe, tot_moe),
                "acs_minority_n": minority,
                "acs_minority_share": minority / race_tot if race_tot else np.nan,
                "acs_minority_share_moe": prop_moe(minority, race_tot, minority_moe, race_tot_moe),
            }
        )
    df = pd.DataFrame(rows)
    df["acs_youth_share_unreliable"] = df["acs_youth_share_moe"] > 0.5 * df["acs_youth_share"]
    df["acs_minority_share_unreliable"] = (
        df["acs_minority_share_moe"] > 0.5 * df["acs_minority_share"]
    )
    df["acs_release"] = blob["release"]["name"]
    return df


# --------------------------------------------------------------------------- distances
def _proj_xy(df: pd.DataFrame) -> np.ndarray:
    gdf = geocode._points(df).to_crs(UTM17N)
    return np.c_[gdf.geometry.x, gdf.geometry.y]


def proximity_features(
    retailers: pd.DataFrame, sites: pd.DataFrame, prefix: str, radii: list[int]
) -> pd.DataFrame:
    """Nearest-site distance and site counts within each radius (meters, UTM 17N)."""
    out = pd.DataFrame(index=retailers.index)
    ok = retailers["lon"].notna()
    cols = {f"{prefix}_nearest_m": np.nan}
    cols.update({f"{prefix}_within_{r}m": np.nan for r in radii})
    for col, val in cols.items():
        out[col] = val
    if sites.empty or not ok.any():
        return out
    xr, xs = _proj_xy(retailers.loc[ok]), _proj_xy(sites)
    dist = np.sqrt(((xr[:, None, :] - xs[None, :, :]) ** 2).sum(-1))
    out.loc[ok, f"{prefix}_nearest_m"] = dist.min(axis=1)
    for r in radii:
        out.loc[ok, f"{prefix}_within_{r}m"] = (dist <= r).sum(axis=1)
    return out


def build_features(config) -> pd.DataFrame:
    cfg = config.raw["data"]
    radii = [int(r) for r in cfg["school_radii_m"]]
    processed = config.path("processed")
    universe = pd.read_csv(
        processed / "retailer_universe.csv", dtype={"tract_geoid": str, "zip5": str}
    )

    schools = load_schools(config)
    acs = parse_acs_tracts(
        ingest.fetch_acs_tracts(config.path("raw"), cfg["state_fips"], cfg["county_fips"])
    )
    acs.to_csv(config.path("interim") / "acs_tracts.csv", index=False)
    sites = load_youth_sites(config)

    feats = universe[
        [
            "license_id",
            "location_key",
            "tract_geoid",
            "in_city_limits",
            "postal_pittsburgh",
            "license_type",
            "retail_license",
            "lon",
            "lat",
        ]
    ].copy()
    feats = feats.join(proximity_features(universe, schools, "school", radii))
    feats = feats.join(
        proximity_features(universe, schools[schools["sector"] == "public"], "public_school", radii)
    )
    if not sites.empty:
        feats = feats.join(proximity_features(universe, sites, "youth_site", radii))
    feats["outlet_type"] = universe["trade_name"].map(synar.classify_outlet)
    chain_counts = (
        universe["legal_name"].str.upper().map(universe["legal_name"].str.upper().value_counts())
    )
    feats["legal_name_licenses_in_scope"] = chain_counts
    feats["chain_flag"] = chain_counts >= 3
    feats = feats.merge(acs, on="tract_geoid", how="left")
    feats["features_note"] = (
        "descriptive snapshot; no violation history (kept in retailer_universe)"
    )
    feats.to_csv(processed / "location_features.csv", index=False)
    return feats
