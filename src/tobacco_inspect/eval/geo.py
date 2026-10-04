"""Geographic clustering of the license universe (pure functions, no plotting).

Stores are clustered on projected coordinates so `eps_m` is a real distance. Each cluster is
summarised by risk mass (`prize`) and by the share of stores with no FDA history, the stores a
census sweep would label for the first time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

UTM17N = "EPSG:32617"  # Pittsburgh


def project_xy(df: pd.DataFrame) -> np.ndarray:
    """Return an (n, 2) array of UTM easting/northing metres from `lon`/`lat` columns."""
    import geopandas as gpd

    pts = gpd.GeoSeries(gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326").to_crs(UTM17N)
    return np.column_stack([pts.x.to_numpy(), pts.y.to_numpy()])


def one_row_per_location(df: pd.DataFrame, weight_col: str = "prize") -> pd.DataFrame:
    """Collapse licenses to physical locations (467 licenses -> 345 locations).

    A location is one inspection target however many licenses it holds, so prize, p and h take
    the maximum; observed status is true if any license there has FDA history.
    """
    g = df.groupby("location_key", sort=False)
    out = g.agg(
        lon=("lon", "first"),
        lat=("lat", "first"),
        tract_geoid=("tract_geoid", "first"),
        trade_name=("trade_name", "first"),
        fda_observed=("fda_observed", "max"),
        p=("p", "max"),
        h=("h", "max"),
        **{weight_col: (weight_col, "max")},
    )
    return out.reset_index()


def cluster_stores(df: pd.DataFrame, eps_m: float = 400.0, min_samples: int = 4) -> pd.Series:
    """DBSCAN cluster id per row (-1 = noise), indexed like `df`."""
    from sklearn.cluster import DBSCAN

    labels = DBSCAN(eps=eps_m, min_samples=min_samples).fit_predict(project_xy(df))
    return pd.Series(labels, index=df.index, name="cluster")


def hotspot_table(
    df: pd.DataFrame,
    weight_col: str = "prize",
    eps_m: float = 400.0,
    min_samples: int = 4,
    unobserved_flag: float = 0.5,
) -> pd.DataFrame:
    """One row per cluster (noise excluded), ranked by summed `weight_col`."""
    d = df.copy()
    d["cluster"] = cluster_stores(d, eps_m, min_samples)
    d = d[d["cluster"] >= 0]
    if d.empty:
        return pd.DataFrame(
            columns=[
                "cluster",
                "stores",
                "prize_sum",
                "prize_mean",
                "mean_p",
                "mean_h",
                "share_unobserved",
                "tracts",
                "lon",
                "lat",
                "flag_unobserved",
                "rank",
            ]
        )
    g = d.groupby("cluster")
    out = pd.DataFrame(
        {
            "stores": g.size(),
            "prize_sum": g[weight_col].sum(),
            "prize_mean": g[weight_col].mean(),
            "mean_p": g["p"].mean(),
            "mean_h": g["h"].mean(),
            "share_unobserved": 1.0 - g["fda_observed"].mean(),
            "tracts": g["tract_geoid"].nunique(),
            "lon": g["lon"].mean(),
            "lat": g["lat"].mean(),
        }
    ).reset_index()
    out["flag_unobserved"] = out["share_unobserved"] >= unobserved_flag
    out = out.sort_values("prize_sum", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def local_zscores(df: pd.DataFrame, weight_col: str = "prize", band_m: float = 600.0) -> pd.Series:
    """Getis-Ord Gi*-style z-score per row: how unusual is the prize mass within `band_m`?

    Binary distance-band weights (self included); z computed against the global mean/variance
    with the standard finite-population variance term. Needs only numpy.
    """
    xy = project_xy(df)
    x = df[weight_col].to_numpy(dtype=float)
    n = len(x)
    d2 = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)
    w = (d2 <= band_m**2).astype(float)
    wsum = w.sum(1)
    xbar, s = x.mean(), x.std(ddof=0)
    if s == 0:
        return pd.Series(np.zeros(n), index=df.index, name="gi_z")
    denom = s * np.sqrt((n * (w**2).sum(1) - wsum**2) / (n - 1))
    z = (w @ x - xbar * wsum) / np.where(denom == 0, np.nan, denom)
    return pd.Series(np.nan_to_num(z), index=df.index, name="gi_z")


def tract_summary(df: pd.DataFrame, weight_col: str = "prize") -> pd.DataFrame:
    """Per-tract retailer count, prize mass and mean risk, joinable on `tract_geoid`."""
    g = df.groupby("tract_geoid")
    out = pd.DataFrame(
        {
            "retailers": g.size(),
            "prize_sum": g[weight_col].sum(),
            "prize_mean": g[weight_col].mean(),
            "share_unobserved": 1.0 - g["fda_observed"].mean(),
        }
    ).reset_index()
    return out
