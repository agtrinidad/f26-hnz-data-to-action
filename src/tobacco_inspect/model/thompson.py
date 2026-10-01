"""Beta-Binomial posterior per store, sampled each planning cycle (Thompson sampling).

Yields randomized coverage (defends against a predictable schedule; Stackelberg logic)
and exploration. Uses a seeded numpy Generator from config.seed.

The Beta prior is centered on the risk model's p_i with strength `kappa` (pseudo-checks). The
store's own history is already inside p_i, so it is not counted twice; `kappa` only sets how much
the sampled rate varies around p_i. Observations from a new cycle update (alpha, beta) directly.
"""

from __future__ import annotations

import numpy as np


def beta_prior_from_p(p, kappa: float):
    """Beta(alpha, beta) with mean p and strength kappa."""
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return kappa * p, kappa * (1 - p)


def update(alpha, beta, checks, violations):
    """Conjugate update after observing `violations` in `checks` new checks per store."""
    return np.asarray(alpha) + violations, np.asarray(beta) + (np.asarray(checks) - violations)


def sample_violation_rates(alpha, beta, rng: np.random.Generator) -> np.ndarray:
    """One posterior draw of each store's violation probability."""
    return rng.beta(alpha, beta)


def random_share_pick(
    n_slots: int, random_share: float, eligible: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Pick the reserved random quota uniformly from `eligible` indices (simple random draw).

    Mirrors Synar's simple-random stratum for Allegheny. At least one slot is reserved when the
    share is positive, even if share * n_slots rounds to zero (small monthly budgets).
    """
    quota = 0 if random_share <= 0 else max(1, int(round(random_share * n_slots)))
    quota = min(quota, n_slots, len(eligible))
    return rng.choice(eligible, size=quota, replace=False) if quota else np.array([], dtype=int)
