"""Baselines to beat: random assignment, nearest-neighbor routing, prior-violators-first, and the
status-quo follow-up rule (FDA re-inspects retailers with a violation in the last 12 months).

Every function returns indices into the candidate table (0-based rows of the frame passed in).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def random_baseline(n: int, budget: int, rng: np.random.Generator) -> np.ndarray:
    """Simple random sample of `budget` stores (the Synar-style draw)."""
    return rng.choice(n, size=min(budget, n), replace=False)


def prior_violators_first(frame: pd.DataFrame, budget: int, rng: np.random.Generator) -> np.ndarray:
    """Stores with the most recent/most violations first; ties broken at random."""
    score = (
        frame["viol_36m"].to_numpy() * 1000
        + frame["n_prior_viol"].to_numpy() * 10
        - frame["days_since_viol"].to_numpy() / 1000
        + rng.random(len(frame)) * 1e-3
    )
    return np.argsort(-score)[:budget]


def status_quo_followup(frame: pd.DataFrame, budget: int, rng: np.random.Generator) -> np.ndarray:
    """Retailers with a violation in the last 12 months first (longest since last check first),
    then the rest at random: the follow-up practice OIG documents (88% re-inspected in 12
    months)."""
    due = frame["viol_12m"].to_numpy() > 0
    score = due * 1000 + due * frame["days_since_check"].to_numpy() / 10 + rng.random(len(frame))
    return np.argsort(-score)[:budget]


def nearest_neighbor(
    travel: np.ndarray, service: np.ndarray, day_minutes: float, budget: int, start: int = 0
) -> list[int]:
    """Greedy nearest-neighbor tour from the depot (node 0) ignoring prizes entirely.

    `travel` includes the depot at row/col 0; returns candidate node indices (1..n-1).
    """
    n = travel.shape[0]
    left, tour, clock, cur = set(range(1, n)), [], 0.0, start
    while left and len(tour) < budget:
        nxt = min(left, key=lambda j: travel[cur, j])
        if clock + travel[cur, nxt] + service[nxt] + travel[nxt, 0] > day_minutes:
            break
        clock += travel[cur, nxt] + service[nxt]
        tour.append(nxt)
        left.discard(nxt)
        cur = nxt
    return tour
