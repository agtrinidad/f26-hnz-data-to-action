# 4. Thompson sampling instead of a full RL stack

Status: accepted

## Context
Retailers can adapt to a predictable schedule (Stackelberg logic), and the model needs exploration
because labels exist only where we inspected. Full RL (Stable-Baselines3, PyTorch) is a heavy
dependency stack for a municipal tool.

## Decision
Use a Beta-Binomial posterior per store, sampled each planning cycle (Thompson sampling), plus a
reserved random-sample share of inspections. Implement in numpy/scipy. Gymnasium-based RL is a
stretch item only.

## Consequences
Randomized coverage, exploration and unbiased retraining data with a small dependency footprint;
matches the Week 2 bandit material. The prior and exploration weight become tunable parameters to
document.
