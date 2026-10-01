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
) -> dict:
    """Simulate `n_cycles` monthly cycles. `policy(cycle, history) -> array of store indices`.

    `history` is the list of previous selections. Returns violations found and selections.
    """
    n = len(p)
    history: list[np.ndarray] = []
    found = np.zeros(n_cycles)
    for c in range(n_cycles):
        sel = np.asarray(policy(c, history), dtype=int)[:budget]
        p_eff = p.copy()
        for prev in history[-memory:]:
            if delta:
                p_eff[prev] *= 1 - delta
        if rho:
            recent = history[-window:]
            freq = np.zeros(n)
            for prev in recent:
                freq[prev] += 1
            freq = freq / max(len(recent), 1)
            p_eff = p_eff * (1 - rho * freq)
        found[c] = (rng.random(len(sel)) < p_eff[sel]).sum()
        history.append(sel)
    return {"found": found, "total": float(found.sum()), "history": history}
