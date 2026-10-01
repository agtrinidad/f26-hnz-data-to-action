"""End-to-end steps behind `tobacco-inspect fit | solve | report` (also used by the notebook).

fit    train the risk model on PA undercover checks, score Pittsburgh licenses, build prizes
solve  plan monthly cycles for one horizon (Thompson-sampled prizes, random share, team MILP)
report route sheets, "why us?" reasons, coverage-by-tract equity audit, policy metrics
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from tobacco_inspect.data import synar
from tobacco_inspect.eval import backtest, baselines, equity, metrics
from tobacco_inspect.model import harrington, history, orienteering, prize, risk, thompson
from tobacco_inspect.routing import distance

SCORES_FILE = "risk_scores.csv"


# --------------------------------------------------------------------------- inputs
def load_checks(config) -> pd.DataFrame:
    path = config.path("processed") / "oce_pa_checks.csv.gz"
    checks = pd.read_csv(path, dtype={"Zip": str}, parse_dates=["decision_date_parsed"])
    checks["up_involved"] = checks["up_involved"].astype(bool)
    return checks


def load_universe(config) -> pd.DataFrame:
    """City licenses joined to their enrichment features (one row per license)."""
    processed = config.path("processed")
    uni = pd.read_csv(processed / "retailer_universe.csv", dtype={"tract_geoid": str, "zip5": str})
    feats = pd.read_csv(processed / "location_features.csv", dtype={"tract_geoid": str})
    keep = [c for c in feats.columns if c not in uni.columns or c == "license_id"]
    return uni.merge(feats[keep], on="license_id", how="left")


def city_location_keys(config) -> set:
    fl = pd.read_csv(config.path("interim") / "fda_locations.csv", dtype={"location_key": str})
    return set(fl.loc[fl["city_scope"] == "in_city", "location_key"])


def unique_locations(df: pd.DataFrame, rank_col: str = "prize") -> pd.DataFrame:
    """One row per physical location: a store with several licenses (e.g. cigarette + OTP) is
    inspected once, so keep the highest-ranked license row per `location_key`."""
    key = "location_key" if "location_key" in df else "street_address"
    ordered = df.sort_values(rank_col, ascending=False) if rank_col in df else df
    return ordered.drop_duplicates(key).sort_index().reset_index(drop=True)


# --------------------------------------------------------------------------- fit
def fit(config, write: bool = True) -> dict:
    """Train, backtest (Gate A), score the universe and build prizes. Returns a results dict."""
    risk_cfg = config.raw["risk"]
    checks = load_checks(config)
    frame = history.build_training_frame(checks, lag_days=risk_cfg["lag_days"])
    results = backtest.rolling_backtest(
        frame,
        test_years=tuple(risk_cfg["test_years"]),
        city_keys=city_location_keys(config),
        fracs=tuple(config.raw["eval"]["lift_fracs"]),
        seed=config.seed,
        n_boot=risk_cfg["n_boot"],
    )
    model = risk.fit_risk_model(frame)

    uni = load_universe(config)
    scoring = history.build_scoring_frame(
        uni, checks, risk_cfg["as_of"], lag_days=risk_cfg["lag_days"]
    )
    target, _, _ = synar.allegheny_rate()
    scores = risk.score_universe(model, scoring, target)
    scores = uni[
        [
            "license_id",
            "location_key",
            "trade_name",
            "street_address",
            "tract_geoid",
            "retail_license",
            "lon",
            "lat",
            "fda_observed",
        ]
    ].merge(scores, on="license_id")
    scores = scores.merge(
        scoring[
            [
                "license_id",
                "outlet_type",
                "n_prior_checks",
                "n_prior_viol",
                "viol_12m",
                "viol_24m",
                "viol_36m",
                "days_since_check",
                "days_since_viol",
                "severity_points",
            ]
        ],
        on="license_id",
    )
    exposure = prize.exposure_h(uni, config, scoring["severity_points"].to_numpy())
    scores[["site", "youth", "severity", "h"]] = exposure[
        ["site", "youth", "severity", "h"]
    ].to_numpy()
    weights = config.raw["harrington"]["state_weights"]
    scores["deterrence"] = harrington.deterrence_gain(scores, weights)
    scores["targeted"] = harrington.targeted(scores["viol_24m"])
    scores["prize"] = prize.compute_prizes(config, scores["h"], scores["p"], scores["deterrence"])
    out = {
        "model": model,
        "backtest": results,
        "scores": scores,
        "coefficients": model.coefficients(),
        "calibration_shift": float(scores["calibration_shift"].iloc[0]),
    }
    if write:
        outdir = config.path("outputs")
        outdir.mkdir(parents=True, exist_ok=True)
        scores.to_csv(config.path("processed") / SCORES_FILE, index=False)
        results.to_csv(outdir / "gate_a_backtest.csv", index=False)
        (outdir / "risk_model_summary.json").write_text(
            json.dumps(
                {
                    "C": model.c,
                    "n_train": model.n_train,
                    "positives": model.positives,
                    "calibration_shift_logit": out["calibration_shift"],
                    "population_rate_target": target,
                    "coefficients": out["coefficients"].round(4).to_dict(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return out


# --------------------------------------------------------------------------- solve
def build_instance(config, scores: pd.DataFrame | None = None, use_osm: bool = True) -> dict:
    """Retail candidates with prizes plus the drive-time matrix (depot at node 0)."""
    if scores is None:
        scores = pd.read_csv(
            config.path("processed") / SCORES_FILE, dtype={"tract_geoid": str, "license_id": str}
        )
    cand = unique_locations(scores[scores["retail_license"] & scores["lon"].notna()])
    depot = config.raw["solve"]["depot"]
    pts = pd.concat(
        [pd.DataFrame({"lon": [depot["lon"]], "lat": [depot["lat"]]}), cand[["lon", "lat"]]],
        ignore_index=True,
    )
    travel, source = distance.travel_time_matrix(config, pts, use_osm=use_osm)
    return {"cand": cand, "travel": travel, "travel_source": source}


def plan_cycle(
    inst,
    config,
    rng,
    visited: set,
    budget: int | None = None,
    day_minutes=None,
    n_routes=None,
    pool: int | None = None,
) -> dict:
    """Plan one monthly cycle: Thompson-sampled prizes, reserved random share, team MILP."""
    cap, scfg = config.capacity, config.raw["solve"]
    cand, travel = inst["cand"], inst["travel"]
    budget = budget or cap.cycle_budget
    day_minutes = day_minutes or cap.daily_budget_minutes
    pool = pool or scfg["candidate_pool"]
    eligible = np.array([i for i in range(len(cand)) if i not in visited])
    alpha, beta = thompson.beta_prior_from_p(cand["p"].to_numpy(), config.raw["risk"]["kappa"])
    p_tilde = thompson.sample_violation_rates(alpha, beta, rng)
    r_tilde = prize.compute_prizes(
        config, cand["h"].to_numpy(), p_tilde, cand["deterrence"].to_numpy()
    )
    forced = thompson.random_share_pick(budget, config.coverage["random_share"], eligible, rng)
    rest = np.array([i for i in eligible if i not in set(forced)])
    top = rest[np.argsort(-r_tilde[rest])[:pool]]
    members = list(forced) + list(top)  # candidate index per node 1..
    nodes = [0] + [m + 1 for m in members]
    sub = travel[np.ix_(nodes, nodes)]
    service = [0.0] + [float(cap.service_minutes)] * len(members)
    prizes = [0.0] + [float(r_tilde[m]) for m in members]
    floors = [(list(range(1, len(forced) + 1)), len(forced))] if len(forced) else []
    n_routes = n_routes or min(cap.teams * cap.cycle_days, budget)
    plan = orienteering.solve_team_orienteering(
        prizes,
        sub.tolist(),
        service,
        day_minutes,
        n_routes,
        budget,
        floors,
        solver=config.solver,
        time_limit=scfg["time_limit_s"],
    )
    heur = orienteering.plan_ranked_batched(
        prizes, sub.tolist(), service, day_minutes, n_routes, budget, floors
    )
    selected = [members[i - 1] for i in plan.visited]
    return {
        "plan": plan,
        "heuristic": heur,
        "members": members,
        "selected": selected,
        "forced": [int(f) for f in forced],
        "p_tilde": p_tilde,
        "r_tilde": r_tilde,
    }


def cycle_workdays(start: date, cycle: int, cap) -> list[date]:
    """Workdays of one monthly cycle: Mon-Fri, skipping US federal holidays (illustrative dates)."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay

    first = pd.Timestamp(start) + pd.Timedelta(weeks=cycle * cap.cycle_weeks)
    bday = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    return [d.date() for d in pd.date_range(first, periods=cap.cycle_days, freq=bday)]


def solve(config, scores: pd.DataFrame | None = None, use_osm: bool = True, write: bool = True):
    """Plan every monthly cycle in the horizon (each store at most once per horizon)."""
    inst = build_instance(config, scores, use_osm)
    rng = np.random.default_rng(config.seed)
    cap = config.capacity
    start = date.fromisoformat(config.raw["solve"].get("start_date", "2026-10-05"))
    visited: set[int] = set()
    rows, summaries = [], []
    for c in range(cap.cycles):
        res = plan_cycle(inst, config, rng, visited)
        plan = res["plan"]
        workdays = cycle_workdays(start, c, cap)
        days = rng.choice(len(workdays), size=max(len(plan.routes), 1), replace=False)
        for r, route in enumerate(plan.routes):
            team = r % cap.teams + 1
            visit_date = workdays[int(days[r])]
            for stop, node in enumerate(route, start=1):
                i = res["members"][node - 1]
                row = inst["cand"].iloc[i]
                rows.append(
                    {
                        "cycle": c + 1,
                        "route": r + 1,
                        "team": team,
                        "date": visit_date.isoformat(),
                        "stop": stop,
                        "license_id": row["license_id"],
                        "store": row["trade_name"],
                        "address": row["street_address"],
                        "tract": row["tract_geoid"],
                        "p": row["p"],
                        "h": row["h"],
                        "prize": row["prize"],
                        "random_share_pick": i in res["forced"],
                        "cand_index": i,
                    }
                )
        visited |= set(res["selected"])
        summaries.append(
            {
                "cycle": c + 1,
                "stores": len(res["selected"]),
                "routes": len(plan.routes),
                "route_minutes": round(sum(plan.times), 1),
                "prize": round(plan.prize, 4),
                "heuristic_prize": round(res["heuristic"].prize, 4),
                "solver": plan.solver,
                "status": plan.status,
                "travel_source": inst["travel_source"],
            }
        )
    schedule, summary = pd.DataFrame(rows), pd.DataFrame(summaries)
    if write:
        outdir = config.path("outputs")
        outdir.mkdir(parents=True, exist_ok=True)
        schedule.to_csv(outdir / "schedule_route_sheets.csv", index=False)
        summary.to_csv(outdir / "schedule_summary.csv", index=False)
    return schedule, summary, inst


# --------------------------------------------------------------------------- report
def reasons(row: pd.Series) -> str:
    """Plain-language "why us?" for one scheduled store (behavior and exposure, no demographics)."""
    parts = []
    if row["random_share_pick"]:
        parts.append("selected by simple random draw (reserved random share)")
    if row["viol_12m"] > 0:
        parts.append(f"violation in the last 12 months ({int(row['viol_12m'])}): follow-up due")
    elif row["viol_36m"] > 0:
        parts.append(f"{int(row['viol_36m'])} violation(s) in the last 36 months")
    if row["n_prior_checks"] == 0:
        parts.append("no FDA check on record in the data")
    elif row["days_since_check"] >= 365:
        parts.append(f"{int(row['days_since_check'])} days since last recorded check")
    if row["site"] >= 0.5:
        parts.append("close to schools or youth sites")
    parts.append(f"outlet type: {row['outlet_type'].replace('_', ' ')}")
    parts.append(f"model violation probability {row['p']:.0%}, exposure {row['h']:.2f}")
    return "; ".join(parts)


def report(
    config, schedule: pd.DataFrame | None = None, scores: pd.DataFrame | None = None
) -> dict:
    outdir = config.path("outputs")
    if schedule is None:
        schedule = pd.read_csv(outdir / "schedule_route_sheets.csv", dtype={"tract": str})
    if scores is None:
        scores = pd.read_csv(config.path("processed") / SCORES_FILE, dtype={"tract_geoid": str})
    extra = scores.set_index("license_id")[
        ["viol_12m", "viol_36m", "n_prior_checks", "days_since_check", "site", "outlet_type"]
    ]
    sheet = schedule.join(extra, on="license_id")
    sheet["why_us"] = sheet.apply(reasons, axis=1)
    sheet.drop(columns=["cand_index"]).to_csv(outdir / "why_us.csv", index=False)

    uni = unique_locations(
        load_universe(config)[lambda d: d["retail_license"]], rank_col="license_id"
    )
    counts = schedule.groupby("license_id").size()
    cov = equity.coverage_by_tract(uni, uni["license_id"].map(counts).fillna(0))
    cov.to_csv(outdir / "coverage_by_tract.csv", index=False)
    summary = equity.equity_summary(cov)
    (outdir / "equity_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {"why_us": sheet, "coverage": cov, "equity": summary}


def policy_metrics(selected_by_cycle: list[list[int]], inst, config, plan_minutes: float) -> dict:
    """Model-based metrics for a sequence of monthly selections (candidate indices)."""
    cand = inst["cand"]
    flat = [i for c in selected_by_cycle for i in c]
    cost = 116.0  # lower bound of the cost-per-check proxy ($116 to ~$400), docs/assumptions.md
    out = {
        "stores": len(flat),
        "expected_violations": metrics.expected_violations(flat, cand["p"].to_numpy()),
        "violations_per_hour": metrics.violations_per_hour(
            flat, cand["p"].to_numpy(), plan_minutes
        ),
        "high_exposure_share": metrics.high_exposure_coverage(flat, cand["h"].to_numpy()),
        "cost_per_detected_low": metrics.cost_per_detected(flat, cand["p"].to_numpy(), cost),
    }
    out.update(metrics.unpredictability(selected_by_cycle))
    return out


__all__ = ["fit", "solve", "report", "build_instance", "plan_cycle", "policy_metrics", "baselines"]
