"""Build per-retailer features: school proximity (NCES), youth density (ACS), violation history.

Per docs/decision-card.md, features describe store behavior and youth exposure,
not demographic proxies (equity feedback-loop concern). ACS margins of error are treated as noise.

TODO: implement.
"""


def build_features(config):
    raise NotImplementedError
