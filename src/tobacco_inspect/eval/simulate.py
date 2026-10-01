"""Labeled cycle simulation: policies vs a synthetic truth ("simulated", with ASSUMED behavior).

Truth: each store has a latent violation probability p_i (the population-calibrated model
output). Each monthly cycle a policy selects stores; violations are Bernoulli(p_eff_i). Two
assumed behavioral channels, both zero by default and varied in sensitivity runs:

- deterrence `delta`: a store inspected in a cycle has its p multiplied by (1 - delta) for the next
  `memory` cycles (Harrington-style effect of enforcement; NOT identified by our data).
- predictability exploitation `rho` (Stackelberg-flavored bounded rationality): stores respond to
  how often they have recently been inspected (their observed inspection frequency f_i over the
  last `window` cycles): p_eff = p * (1 - rho * f_i). A deterministic top-B rule inspects the same
  stores every cycle (f near 1) and so is exploitable; randomized coverage spreads inspections.

Because the truth is built from the same p_i the model uses, simulated lift shows what the policy
logic does *if the model is right*; it is not evidence that the model is right (Gate A is).
"""

from __future__ import annotations

import numpy as np


def effective_p(
    p: np.ndarray,
    history: list[np.ndarray],
    delta: float = 0.0,
    memory: int = 3,
    rho: float = 0.0,
    window: int = 6,
    gamma: float = 0.0,
    gamma_power: float = 1.0,
) -> np.ndarray:
    """Violation probability each store has *now*, given the selections in `history`.

    One response model shared by every simulation (monthly cycles, so `memory` and `window` are
    in months; `census.monthly_protection` uses the same unit). All three channels are ASSUMED.

    - `delta`: p is multiplied by (1 - delta) once per inspection in the last `memory` cycles
      (a store inspected twice in the window compounds).
    - `rho`: p multiplied by (1 - rho * f_i), f_i = a store's own inspection frequency in `window`.
    - `gamma` (general deterrence): every store's p is multiplied by (1 - gamma * c**gamma_power),
      where c is the share of stores inspected at least once in the last `window` cycles, i.e. how
      visible enforcement is across the city. Checked or not, a store reacts to how likely it is
      to be next. `gamma_power` is the shape of that response: 1 linear, > 1 convex (credibility
      threshold: only near-universal checking deters), < 1 concave (the first checks matter most).
    """
    n = len(p)
    p_eff = p.copy()
    if delta:
        for prev in history[-memory:]:
            p_eff[prev] *= 1 - delta
    recent = history[-window:]
    if rho:
        freq = np.zeros(n)
        for prev in recent:
            freq[prev] += 1
        p_eff = p_eff * (1 - rho * freq / max(len(recent), 1))
    if gamma and recent:
        seen = np.unique(np.concatenate(recent))
        p_eff = p_eff * (1 - gamma * (len(seen) / n) ** gamma_power)
    return p_eff


def run(
    policy,
    p: np.ndarray,
    budget: int,
    n_cycles: int,
    rng: np.random.Generator,
    delta: float = 0.0,
    memory: int = 3,
    rho: float = 0.0,
    window: int = 6,
    gamma: float = 0.0,
    gamma_power: float = 1.0,
) -> dict:
    """Simulate `n_cycles` monthly cycles. `policy(cycle, history) -> array of store indices`.

    `history` is the list of previous selections. Returns violations found, selections, and the
    per-cycle mean violation probability across all stores (`exposure`: what deterrence lowers,
    unlike `found`, which falls when deterrence works).
    """
    history: list[np.ndarray] = []
    found = np.zeros(n_cycles)
    exposure = np.zeros(n_cycles)
    for c in range(n_cycles):
        sel = np.asarray(policy(c, history), dtype=int)[:budget]
        p_eff = effective_p(p, history, delta, memory, rho, window, gamma, gamma_power)
        found[c] = (rng.random(len(sel)) < p_eff[sel]).sum()
        exposure[c] = p_eff.mean()
        history.append(sel)
    return {"found": found, "total": float(found.sum()), "history": history, "exposure": exposure}
