"""Prize r_i = h_i * p_i + lambda * delta_deterrence_i.

h_i is an exposure proxy for the externality of a violation: proximity to vulnerable sites
(schools, plus OSM youth sites such as libraries, community centres, playgrounds), tract youth
share (shrunk where the ACS margin of error is large) and historical severity of past penalties.
No per-store sales volume or health-cost data exists, so h_i is a proxy, not a dollar figure.

Weights live in config (`prize.h_weights`, `prize.site_mix`). "school_proximity" in the weights is
the combined vulnerable-site proximity score. NOTE: historical severity partly double counts the
prior violations already inside p_i; it is kept because the config defines it and is covered by
the sensitivity analysis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEVERITY_POINTS = {
    "Warning Letter": 1.0,
    "Civil Money Penalty": 2.0,
    "Civil Money Penalty Archived": 2.0,
    "Civil Money Penalty not available": 2.0,
    "No-Tobacco-Sale Order": 4.0,
}


def proximity_score(nearest_m, within_300m, scale_m: float, cap: int) -> np.ndarray:
    """Blend of distance decay and counts of sites within 300 m, in [0, 1]."""
    near = np.exp(-np.nan_to_num(nearest_m, nan=1e6) / scale_m)
    count = np.minimum(np.nan_to_num(within_300m, nan=0.0), cap) / cap
    return 0.5 * near + 0.5 * count


def shrink_youth_share(share, moe) -> np.ndarray:
    """Empirical-Bayes shrinkage of tract youth share toward the city median using the ACS MOE."""
    share, moe = np.asarray(share, dtype=float), np.asarray(moe, dtype=float)
    ok = ~np.isnan(share)
    med = np.nanmedian(share)
    se2 = (np.nan_to_num(moe, nan=np.nanmedian(moe)) / 1.645) ** 2
    tau2 = max(np.nanvar(share) - np.nanmean(se2[ok]), 1e-4)
    b = tau2 / (tau2 + se2)
    out = med + b * (np.where(ok, share, med) - med)
    return out


def _unit(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    lo, hi = np.nanmin(x), np.nanmax(x)
    return np.zeros_like(x) if hi == lo else (x - lo) / (hi - lo)


def exposure_h(features: pd.DataFrame, config, severity_points=None) -> pd.DataFrame:
    """Return the h_i components and combined h_i (columns: site, youth, severity, h)."""
    w = config.prize["h_weights"]
    mix = config.prize.get("site_mix", {"school": 0.7, "youth_site": 0.3})
    school = proximity_score(features["school_nearest_m"], features["school_within_300m"], 300.0, 3)
    if "youth_site_nearest_m" in features:
        yscore = proximity_score(
            features["youth_site_nearest_m"], features["youth_site_within_300m"], 150.0, 5
        )
    else:
        yscore = np.zeros(len(features))
    site = mix["school"] * school + mix["youth_site"] * yscore
    youth = _unit(shrink_youth_share(features["acs_youth_share"], features["acs_youth_share_moe"]))
    if severity_points is None:
        severity_points = np.zeros(len(features))
    sev = np.minimum(np.asarray(severity_points, dtype=float), 8.0) / 8.0
    h = w["school_proximity"] * site + w["youth_density"] * youth + w["historical_severity"] * sev
    return pd.DataFrame(
        {"site": site, "youth": youth, "severity": sev, "h": h}, index=features.index
    )


def compute_prizes(config, h: np.ndarray, p: np.ndarray, deterrence: np.ndarray) -> np.ndarray:
    """r_i = h_i * p_i + lambda * delta_deterrence_i (unit-free risk score)."""
    lam = float(config.prize["lambda_deterrence"])
    return np.asarray(h) * np.asarray(p) + lam * np.asarray(deterrence)
