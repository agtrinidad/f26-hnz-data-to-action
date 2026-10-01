"""Metrics: expected violations per inspector-hour, high-youth-exposure coverage,
route unpredictability, cost per detected violation.

"Expected" values use the (population-calibrated) p_i, so they are model-based and labeled
"assumed" unless computed from observed outcomes. Cost per PREVENTED violation is not
estimable (no deterrence data).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def expected_violations(selected, p) -> float:
    return float(np.asarray(p)[np.asarray(selected, dtype=int)].sum())


def violations_per_hour(selected, p, plan_minutes: float) -> float:
    """Expected violations found per inspector-hour (travel + service time)."""
    return expected_violations(selected, p) / max(plan_minutes / 60.0, 1e-9)


def cost_per_detected(selected, p, cost_per_check: float) -> float:
    ev = expected_violations(selected, p)
    return float(cost_per_check * len(selected) / ev) if ev > 0 else float("nan")


def high_exposure_coverage(selected, h, quantile: float = 2 / 3) -> float:
    """Share of selected stores in the top third of exposure h_i (universe-wide threshold)."""
    h = np.asarray(h)
    thr = np.quantile(h, quantile)
    sel = np.asarray(selected, dtype=int)
    return float((h[sel] >= thr).mean()) if len(sel) else float("nan")


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 1.0


def unpredictability(cycles: list[list[int]]) -> dict[str, float]:
    """1 - mean Jaccard overlap of consecutive cycles, and entropy of selection frequency."""
    overlaps = [jaccard(cycles[i], cycles[i + 1]) for i in range(len(cycles) - 1)]
    flat = pd.Series([i for c in cycles for i in c]).value_counts(normalize=True)
    return {
        "mean_overlap": float(np.mean(overlaps)) if overlaps else float("nan"),
        "unpredictability": float(1 - np.mean(overlaps)) if overlaps else float("nan"),
        "selection_entropy_bits": float(-(flat * np.log2(flat)).sum()) if len(flat) else 0.0,
        "distinct_stores": int(flat.shape[0]),
    }
