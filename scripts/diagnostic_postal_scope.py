"""Postal-name-scope diagnostics for the report's Analysis section (1,808 'PITTSBURGH' FDA records).

Reproduces: repeat-check logistic backtest, 217-location prioritisation benchmark vs random,
and the recency-weight sensitivity. Writes outputs/diagnostic_postal_*.csv and prints a summary.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from tobacco_inspect.data.features import proximity_features
from tobacco_inspect.model.prize import SEVERITY_POINTS, exposure_h

ROOT = Path(__file__).resolve().parents[1]
SEED, N_DRAWS, AS_OF = 20261001, 10_000, pd.Timestamp("2026-07-31")  # as-of date that reproduces the draft table
cfg = yaml.safe_load((ROOT / "config/default.yaml").read_text())
config = SimpleNamespace(prize=cfg["prize"])

o = pd.read_csv(ROOT / "data/processed/oce_pa_checks.csv.gz", low_memory=False)
p = o[o.City.str.upper().str.strip() == "PITTSBURGH"].copy()
p["dec"] = pd.to_datetime(p.decision_date_parsed)
p["insp"] = pd.to_datetime(p.inspection_date_parsed)
p["eff"] = p.insp.fillna(p.dec)
p["y"] = p.underage_sale_violation.astype(int)
out = {"records": len(p), "violations": int(p.y.sum()), "locations": p.location_key.nunique(),
       "missing_insp_date": int(p.insp.isna().sum())}

# ---- 1. repeat-check logistic backtest
p = p.sort_values(["location_key", "eff"]).reset_index(drop=True)
g = p.groupby("location_key")
p["n_prior"] = g.cumcount()
p["v_prior"] = g.y.cumsum() - p.y
p["prev_y"] = g.y.shift(1)
p["gap"] = (p.eff - g.eff.shift(1)).dt.days
r = p[p.n_prior > 0].copy()
r["rate"] = (r.v_prior + 1) / (r.n_prior + 2)  # Laplace-smoothed prior violation rate
r["log_n"] = np.log(r.n_prior)
X = ["rate", "gap", "prev_y", "log_n"]  # smoothed prior rate, days since previous check, last outcome, log #prior checks
tr, te = r[r.eff < "2024-01-01"], r[r.eff >= "2024-01-01"]
m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(tr[X], tr.y)
s = m.predict_proba(te[X])[:, 1]
q = pd.qcut(pd.Series(s).rank(method="first"), 5, labels=False)
top = te.y.to_numpy()[q.to_numpy() == 4].mean()
out.update(repeat_obs=len(r), train=len(tr), test=len(te), auc=roc_auc_score(te.y, s),
           top_quintile_rate=top, test_rate=te.y.mean(), quintile_lift=top / te.y.mean())

# ---- 2. 217-location prioritisation benchmark
sev = p.assign(pts=p.Outcome.map(SEVERITY_POINTS).fillna(0.0)).groupby("location_key").pts.sum()
L = p.groupby("location_key").agg(n=("y", "size"), v=("y", "sum"), last=("eff", "max"),
                                  street=("Street Address", "first"), zip5=("Zip", "first")).reset_index()
fl = pd.read_csv(ROOT / "data/interim/fda_locations.csv", dtype={"tract_geoid": str})
L = L.merge(fl[["location_key", "lon", "lat", "tract_geoid"]], on="location_key", how="left")
L = L[L["last"] >= "2021-01-01"].reset_index(drop=True)
out["candidates"] = len(L)
schools = pd.read_csv(ROOT / "data/interim/schools_pgh.csv")
sites = pd.read_csv(ROOT / "data/interim/youth_sites.csv")
F = L[["lon", "lat"]].join(proximity_features(L, schools, "school", [300])).join(
    proximity_features(L, sites, "youth_site", [300]))
F = F.rename(columns={"school_within_300m": "school_within_300m", "youth_site_within_300m": "youth_site_within_300m"})
acs = pd.read_csv(ROOT / "data/interim/acs_tracts.csv", dtype={"tract_geoid": str})
F = pd.concat([F, L[["tract_geoid"]].merge(acs, on="tract_geoid", how="left")[["acs_youth_share", "acs_youth_share_moe"]]], axis=1)
h = exposure_h(F, config, severity_points=L.location_key.map(sev).to_numpy())["h"].to_numpy()
pi = ((L.v + 1) / (L.n + 2)).to_numpy()
days = (AS_OF - L["last"]).dt.days.to_numpy()
delta = pd.Series(days).rank(pct=True).to_numpy()  # percentile rank of days since last check


SPECS = {
    "p_plus_delta": lambda w: pi + w * delta,          # history + recency (no h_i)
    "h_p_plus_delta": lambda w: h * pi + w * delta,    # report formula r = h*p + delta
}
HIST = {"p_plus_delta": pi, "h_p_plus_delta": h * pi}
out["h_diagnostics"] = dict(no_coords=int(F.lon.isna().sum()), no_acs_youth=int(F.acs_youth_share.isna().sum()),
                            h_mean=float(h.mean()), h_sd=float(h.std()), p_mean=float(pi.mean()), p_sd=float(pi.std()),
                            h_p_mean=float((h * pi).mean()), delta_mean=float(delta.mean()),
                            corr_h_p=float(np.corrcoef(h, pi)[0, 1]),
                            sites_within_300m=int(((F.school_within_300m > 0) | (F.youth_site_within_300m > 0)).sum()))


def capture(sc, idx):
    return sc[idx].sum() / sc.sum()


for name, f in SPECS.items():
    rng = np.random.default_rng(SEED)
    base = f(1.0)
    rows = []
    for B in (10, 20, 40, 80):
        cap = capture(base, np.argsort(-base)[:B])
        rnd = np.array([capture(base, rng.choice(len(L), B, replace=False)) for _ in range(N_DRAWS)])
        rows.append(dict(budget=B, selected_pct=B / len(L), captured=cap, random_mean=rnd.mean(),
                         random_p95=np.quantile(rnd, .95), lift=cap / rnd.mean()))
    bench = pd.DataFrame(rows)
    B = 40
    out[name] = dict(recency_only_B40=capture(base, np.argsort(-delta)[:B]),
                     history_only_B40=capture(base, np.argsort(-HIST[name])[:B]))
    top0 = set(np.argsort(-base)[:B])
    rows = []
    for w in (0.5, 1.0, 2.0):
        sel = np.argsort(-f(w))[:B]
        rows.append(dict(recency_weight=w, retained_pct=len(top0 & set(sel)) / B,
                         any_prior_violation=(L.v.to_numpy()[sel] > 0).mean(),
                         median_days_since_check=float(np.median(days[sel]))))
    sens = pd.DataFrame(rows)
    bench.to_csv(ROOT / f"outputs/diagnostic_postal_benchmark_{name}.csv", index=False)
    sens.to_csv(ROOT / f"outputs/diagnostic_postal_sensitivity_{name}.csv", index=False)
    print(name); print(bench.round(4).to_string()); print(sens.round(4).to_string())
(ROOT / "outputs/diagnostic_postal_summary.json").write_text(json.dumps(out, indent=2, default=float))
print(json.dumps(out, indent=2, default=float))
