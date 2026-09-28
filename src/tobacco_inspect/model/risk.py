"""Predict violation probability p_i (regularized logistic regression, calibrated).

Predict-then-optimize: p_i enters the MILP as a plain coefficient (ADR 0003).
Caveat: FDA data covers only inspected stores (selection bias); Synar is a state-level
calibration check, not retailer-level labels.

TODO: implement.
"""


def fit_risk_model(features):
    raise NotImplementedError
