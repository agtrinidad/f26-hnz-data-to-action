"""Predict violation probability p_i (regularized logistic regression, calibrated).

Predict-then-optimize: p_i enters the MILP as a plain coefficient (ADR 0003).
Caveats: FDA data covers only inspected stores (selection bias), so the raw model estimates
P(violation | inspected). `calibrate_to_population_rate` rescales it to a random-sample base rate
(Synar, Allegheny) so p_i approximates P(violation | store exists).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from tobacco_inspect.model.history import CATEGORICAL, FEATURES, NUMERIC

C_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0)


@dataclass
class RiskModel:
    pipeline: Pipeline
    c: float
    n_train: int
    positives: int

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(frame[FEATURES])[:, 1]

    def coefficients(self) -> pd.Series:
        names = self.pipeline.named_steps["prep"].get_feature_names_out()
        coef = self.pipeline.named_steps["clf"].coef_[0]
        return pd.Series(coef, index=names).sort_values()


def _pipeline(c: float) -> Pipeline:
    prep = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )
    return Pipeline([("prep", prep), ("clf", LogisticRegression(C=c, max_iter=2000))])


def fit_risk_model(train: pd.DataFrame, c_grid=C_GRID) -> RiskModel:
    """Fit on `train` (needs FEATURES, y, fy). C is chosen by validating on the last fiscal year.

    The validation year is held out in time (never shuffled), then the model is refit on all of
    `train` at the chosen C.
    """
    years = sorted(train["fy"].unique())
    if len(years) >= 2:
        fit_part, val_part = train[train["fy"] < years[-1]], train[train["fy"] == years[-1]]
        scores = {}
        for c in c_grid:
            p = (
                _pipeline(c)
                .fit(fit_part[FEATURES], fit_part["y"])
                .predict_proba(val_part[FEATURES])[:, 1]
            )
            scores[c] = log_loss(val_part["y"], p, labels=[0, 1])
        best = min(scores, key=scores.get)
    else:
        best = 0.3
    pipe = _pipeline(best).fit(train[FEATURES], train["y"])
    return RiskModel(pipe, best, len(train), int(train["y"].sum()))


def evaluate(y, p) -> dict[str, float]:
    y, p = np.asarray(y), np.asarray(p)
    out = {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "base_rate": float(y.mean()),
        "mean_p": float(p.mean()),
    }
    if 0 < y.sum() < len(y):
        out["auc"] = float(roc_auc_score(y, p))
        out["brier"] = float(brier_score_loss(y, p))
        out["logloss"] = float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)))
    return out


def lift_at_k(y, score, frac: float, rng: np.random.Generator, n_boot: int = 500):
    """Hit rate in the top `frac` by score divided by the overall hit rate, with bootstrap CI.

    Ties are broken at random (fixed by `rng`), so rule-based scores with many ties are not
    flattered or penalized by row order.
    """
    y, score = np.asarray(y), np.asarray(score, dtype=float)
    n = len(y)
    if n == 0 or y.sum() == 0:
        return np.nan, np.nan, np.nan

    def one(idx):
        yy, ss = y[idx], score[idx] + rng.normal(0, 1e-9, len(idx))
        k = max(1, int(round(frac * len(idx))))
        top = np.argsort(-ss)[:k]
        base = yy.mean()
        return yy[top].mean() / base if base > 0 else np.nan

    point = one(np.arange(n))
    boots = np.array([one(rng.integers(0, n, n)) for _ in range(n_boot)])
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return float(point), float(lo), float(hi)


def calibration_table(y, p, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False)
    return (
        df.groupby("bin")
        .agg(n=("y", "size"), mean_p=("p", "mean"), observed=("y", "mean"))
        .reset_index()
    )


def calibrate_to_population_rate(p: np.ndarray, target_mean: float) -> tuple[np.ndarray, float]:
    """Shift the logit intercept so mean(p) equals `target_mean` (prior-shift correction).

    Returns the rescaled probabilities and the shift. The ranking is unchanged; only levels move.
    """
    z = logit(np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6))
    f = lambda d: expit(z + d).mean() - target_mean  # noqa: E731
    delta = brentq(f, -10, 10)
    return expit(z + delta), float(delta)


def outlet_effects(frame: pd.DataFrame, p: np.ndarray) -> pd.DataFrame:
    """Mean predicted and observed violation rate by outlet type (compare with Synar Table 8)."""
    df = pd.DataFrame(
        {"outlet_type": frame["outlet_type"].to_numpy(), "p": p, "y": frame["y"].to_numpy()}
    )
    return (
        df.groupby("outlet_type")
        .agg(n=("y", "size"), mean_p=("p", "mean"), observed=("y", "mean"))
        .reset_index()
    )


def score_universe(model: RiskModel, scoring_frame: pd.DataFrame, target_mean: float | None):
    """Score licenses; optionally rescale the mean to a random-sample base rate.

    Returns a frame with `p_raw` (P(violation | inspected)) and `p` (population-calibrated).
    """
    out = scoring_frame[["license_id"]].copy()
    out["p_raw"] = model.predict(scoring_frame)
    if target_mean is None:
        out["p"], out["calibration_shift"] = out["p_raw"], 0.0
    else:
        out["p"], out["calibration_shift"] = calibrate_to_population_rate(
            out["p_raw"].to_numpy(), target_mean
        )
    return out
