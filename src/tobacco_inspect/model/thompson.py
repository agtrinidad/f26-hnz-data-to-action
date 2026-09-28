"""Beta-Binomial posterior per store, sampled each planning cycle (Thompson sampling).

Yields randomized coverage (defends against a predictable schedule; Stackelberg logic)
and exploration. Uses a seeded numpy Generator from config.seed.

TODO: implement.
"""


def sample_violation_rates(alpha, beta, rng):
    raise NotImplementedError
