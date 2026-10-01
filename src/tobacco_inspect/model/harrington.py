"""Harrington-style state-dependent enforcement ("targeted" vs "untargeted" firms).

Retailers with recent violations are "targeted": they face more scrutiny; historically
compliant retailers are "untargeted". The enforcement state follows FDA's real schedule of
escalating penalties, which counts violations in 12/24/36-month windows (HHS-OIG
OEI-01-20-00240, Exhibit 3), instead of an invented state space.

The deterrence EFFECT (how much an inspection changes behavior) is an ASSUMPTION encoded in
`prize.lambda_deterrence` and `harrington.state_weights` (docs/assumptions.md); it is not
identified by any data we hold. Results that depend on it are labeled "assumed".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_WEIGHTS = (0.25, 0.6, 0.8, 1.0, 1.0)  # by escalation depth 0..4
FOLLOWUP_DAYS = 365  # OIG: penalties consider violations in 12-month intervals


def escalation_depth(viol_36m) -> np.ndarray:
    """Violations in the trailing 36 months, capped at 4 (depth of the FDA penalty ladder)."""
    return np.clip(np.asarray(viol_36m, dtype=int), 0, 4)


def targeted(viol_24m) -> np.ndarray:
    """Harrington's "targeted" group: at least one violation in the last 24 months."""
    return np.asarray(viol_24m) >= 1


def recency_factor(days_since_check, followup_days: int = FOLLOWUP_DAYS) -> np.ndarray:
    """Share of the follow-up window already elapsed, capped at 1 (time since past inspection)."""
    return np.clip(np.asarray(days_since_check, dtype=float) / followup_days, 0.0, 1.0)


def deterrence_gain(frame: pd.DataFrame, weights=DEFAULT_WEIGHTS) -> np.ndarray:
    """delta_deterrence_i in [0, 1]: recency of the last check x weight of the penalty depth.

    Targeted stores that have gone a full follow-up window without a check score highest; stores
    never in trouble keep a small recency credit (the proposal: risk rises with time since the
    past inspection).
    """
    depth = escalation_depth(frame["viol_36m"])
    w = np.asarray(weights, dtype=float)[depth]
    return w * recency_factor(frame["days_since_check"])
