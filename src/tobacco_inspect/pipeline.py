"""End-to-end steps behind `tobacco-inspect fit | solve | report` (also used by the notebook).

fit    train the risk model on PA undercover checks, score Pittsburgh licenses, build prizes
solve  plan monthly cycles for one horizon (Thompson-sampled prizes, random share, team MILP)
report route sheets, "why us?" reasons, coverage-by-tract equity audit, policy metrics
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

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
def build_instance(
    config, scores: pd.DataFrame | None = None, use_osm: bool = True, retail_only: bool = True
) -> dict:
    """Retail candidates with prizes plus the drive-time matrix (depot at node 0)."""
    if scores is None:
        scores = pd.read_csv(
            config.path("processed") / SCORES_FILE, dtype={"tract_geoid": str, "license_id": str}
        )
    mask = scores["lon"].notna() & (scores["retail_license"] if retail_only else True)
    cand = unique_locations(scores[mask])
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
    cost = float(config.raw["census"]["topdown_per_check"]["low"])  # lower bound of $116-$400
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


# --------------------------------------------------------------------------- census scenario
def census(config, write: bool = True, n_sims: int = 1000) -> dict:
    """Cost, portioning and capture of checking every distinct retail location once a year."""
    from tobacco_inspect.eval import census as C

    params = C.CostParams.from_config(config)
    day = config.capacity.daily_budget_minutes
    inst = build_instance(config)
    cand, travel = inst["cand"], inst["travel"]
    p = cand["p"].to_numpy()
    cost_summary = C.cost_table(travel, params, day)
    routes, t, svc = C.build_routes(travel, params, day, "base")
    components = pd.concat(
        [
            C.bottom_up_cost(*C.build_routes(travel, params, day, sc), params, sc)
            for sc in C.SCENARIOS
        ],
        ignore_index=True,
    )
    risk_per_route = [float(p[[i - 1 for i in r]].sum()) for r in routes]
    rng = np.random.default_rng(config.seed)
    year, teams = int(config.raw["census"]["year"]), config.capacity.teams
    calendars = {
        plan: C.portion_calendar(plan, len(routes), risk_per_route, year, teams, rng)
        for plan in "ABCD"
    }
    capture = C.capture_table(
        p,
        tracts=cand["tract_geoid"].to_numpy(),
        n_sims=n_sims,
        seed=config.seed,
        lift=float(config.raw["census"]["targeted_lift"]),
    )
    route_rows = [
        {
            "route": r,
            "stops": len(rt),
            "minutes": round(C.partition.route_minutes(rt, t, svc), 1),
            "expected_violations": round(risk_per_route[r], 2),
            "licenses": " | ".join(cand.iloc[i - 1]["trade_name"] for i in rt[:3])
            + (" ..." if len(rt) > 3 else ""),
        }
        for r, rt in enumerate(routes)
    ]
    out = {
        "cand": cand,
        "routes": routes,
        "route_table": pd.DataFrame(route_rows),
        "cost_summary": cost_summary,
        "components": components,
        "calendars": calendars,
        "capture": capture,
        "p": p,
        "params": params,
        "inst": inst,
        "travel": travel,
        "risk_per_route": risk_per_route,
    }
    if write:
        outdir = config.path("outputs")
        outdir.mkdir(parents=True, exist_ok=True)
        out["route_table"].to_csv(outdir / "census_routes.csv", index=False)
        cost_summary.to_csv(outdir / "census_cost_summary.csv", index=False)
        components.to_csv(outdir / "census_cost_components.csv", index=False)
        capture.to_csv(outdir / "census_capture.csv", index=False)
        pd.concat(calendars.values()).to_csv(outdir / "census_calendars.csv", index=False)
    return out


# --------------------------------------------------------------------------- regime comparison
HIDDEN_SIGMAS = (0.0, 0.5, 1.0, 1.5)
RESPONSES = {
    "no response": {},
    "store-specific only (delta 25%, 3 months)": {"delta": 0.25, "memory": 3},
    "strong store-specific (delta 50%, 6 months)": {"delta": 0.5, "memory": 6},
    "plus visibility, linear (gamma 0.3)": {"delta": 0.25, "memory": 3, "gamma": 0.3},
}
GAMMA_POWERS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)


def regime(config, write: bool = True, n_scale: float = 1.0) -> dict:
    """Budget-capped vs census-floor regime comparison (memo 06). Scenario, not part of run-all.

    `n_scale` shrinks every Monte Carlo size (tests); results at 1.0 are what the notebook shows.
    """
    from tobacco_inspect.eval import census as C
    from tobacco_inspect.eval import regime as R

    def n(k: int) -> int:
        return max(2, int(round(k * n_scale)))

    rg = config.raw["regime"]
    params = C.CostParams.from_config(config)
    day = config.capacity.daily_budget_minutes
    inst = build_instance(config)
    cand, travel = inst["cand"], inst["travel"]
    p, h = cand["p"].to_numpy(), cand["h"].to_numpy()
    N = len(p)
    kappa = float(config.raw["risk"]["kappa"])
    floor, share = int(rg["floor_months"]), float(rg["second_pass_share"])
    cycle = config.capacity.cycle_budget
    e2 = int(round(share * N))
    current_year = config.capacity.budget_inspections * 4  # today's city volume (~44 a year)
    truths = {s: R.Truth.calibrated(p, float(rg["observed_lift"]), s) for s in HIDDEN_SIGMAS}
    truth = truths[0.0]  # conservative baseline for the census floor's second pass

    front = R.frontier(
        p,
        travel,
        params,
        day,
        [current_year, 86, 138, 207, 276],
        truth,
        kappa,
        second_pass_fracs=(0.1, share, 0.5),
        n_sims=n(150),
        n_truth=n(300),
    )
    path = front[
        front.policy.isin(["targeted", "census_floor", "census_floor+adaptive_second_pass"])
    ].assign(policy="path")
    second = pd.concat(
        [
            R.adaptive_second_pass(p, e2, kappa, t, n(300), np.random.default_rng(1))[0].assign(
                hidden_sigma=s
            )
            for s, t in truths.items()
        ],
        ignore_index=True,
    )
    cap_cost = float(
        front[front.policy == "targeted"].sort_values("checks").iloc[0].cost_per_check * cycle * 12
    )
    cen_row = front[
        (front.policy == "census_floor+adaptive_second_pass") & (front.checks == N + e2)
    ].iloc[0]
    cen_cost = float(cen_row.cost_bottom_up)

    def both(resp, sims, **kw):
        a = R.year_sim(p, "capped", resp, truth, kappa, n_sims=n(sims), budget_per_cycle=cycle, h=h)
        b = R.year_sim(
            p,
            "census_floor",
            resp,
            truth,
            kappa,
            n_sims=n(sims),
            floor_months=floor,
            second_pass_share=share,
            h=h,
            **kw,
        )
        return a, b

    grid_rows = []
    for name, resp in RESPONSES.items():
        a, b = both(resp, 80)
        grid_rows.append(
            {
                "response": name,
                "capped_reduction": a["reduction"],
                "census_reduction": b["reduction"],
                "capped_per_1k_dollars": 100 * a["reduction"] / cap_cost * 1000,
                "census_per_1k_dollars": 100 * b["reduction"] / cen_cost * 1000,
                "capped_per_100_checks": 1e4 * a["reduction"] / a["checks"],
                "census_per_100_checks": 1e4 * b["reduction"] / b["checks"],
            }
        )
    shape_rows = []
    for k in GAMMA_POWERS:
        a, b = both({"delta": 0.25, "memory": 3, "gamma": 0.3, "gamma_power": k}, 60)
        shape_rows.append(
            {
                "gamma_power": k,
                "capped_per_1k": 100 * a["reduction"] / cap_cost * 1000,
                "census_per_1k": 100 * b["reduction"] / cen_cost * 1000,
            }
        )
    shape = pd.DataFrame(shape_rows)
    order_rows = []
    for name, resp in (
        ("delta 25%, 3 months", {"delta": 0.25, "memory": 3}),
        ("delta 50%, 6 months", {"delta": 0.5, "memory": 6}),
    ):
        for order in ("random", "risk_first"):
            _, b = both(resp, 80, order=order)
            order_rows.append(
                {
                    "response": name,
                    "first_pass_order": order,
                    "reduction": b["reduction"],
                    "reduction_h": b["reduction_h"],
                }
            )
    rule_rows = []
    for rule in ("thompson", "static", "random"):
        _, b = both({}, 80, second_pass=rule)
        rule_rows.append(
            {
                "second_pass": rule,
                "detections": b["detections"],
                "distinct_violators": b["distinct_detected"],
                "repeat_violators": b["repeat_violators"],
            }
        )
    cap_run, cen_run = both({}, 120)
    equity_tbl = R.equity_compare(
        cand,
        load_universe(config),
        {"budget-capped": cap_run["counts"], "census floor + 2nd pass": cen_run["counts"]},
    )
    out = {
        "cand": cand,
        "p": p,
        "h": h,
        "N": N,
        "kappa": kappa,
        "truths": truths,
        "truth": truth,
        "max_sigma": R.max_hidden_sigma(p, float(rg["observed_lift"])),
        "frontier": front,
        "marginal": R.marginal(path, "path"),
        "second_pass": second,
        "second_pass_checks": e2,
        "cap_cost": cap_cost,
        "cen_cost": cen_cost,
        "response_grid": pd.DataFrame(grid_rows),
        "shape_sweep": shape,
        "break_even_power": R.crossing(
            shape.gamma_power.to_numpy(), (shape.census_per_1k - shape.capped_per_1k).to_numpy()
        ),
        "order_table": pd.DataFrame(order_rows),
        "second_pass_rules": pd.DataFrame(rule_rows),
        "capped_run": cap_run,
        "census_run": cen_run,
        "equity": equity_tbl,
    }
    if write:
        outdir = config.path("outputs")
        outdir.mkdir(parents=True, exist_ok=True)
        for name, key in (
            ("frontier", "frontier"),
            ("second_pass", "second_pass"),
            ("response_grid", "response_grid"),
            ("shape_sweep", "shape_sweep"),
            ("equity", "equity"),
        ):
            out[key].to_csv(outdir / f"regime_{name}.csv", index=False)
    return out


# --------------------------------------------------------------------------- marginal value
def valuation(config, write: bool = True, n_scale: float = 1.0) -> dict:
    """Marginal cost, break-even deterrence, opportunity cost, what-ifs, robustness (memo 07).

    Scenario, not part of run-all; needs `fit` and `solve` first. Reuses `regime()` results
    (frontier, response grid, costs) rather than recomputing them.
    """
    from tobacco_inspect.eval import census as C
    from tobacco_inspect.eval import valuation as V

    vcfg = config.raw["valuation"]
    reg = regime(config, write=False, n_scale=n_scale)
    params = C.CostParams.from_config(config)
    inst = build_instance(config)
    cand, travel, N = inst["cand"], inst["travel"], reg["N"]
    current = config.capacity.budget_inspections * 4
    marginal = V.marginal_cost_table(reg["frontier"], params, current, N, reg["second_pass_checks"])
    full = marginal.iloc[-1]
    break_even = V.break_even_table(
        reg["response_grid"], reg["cap_cost"], reg["cen_cost"], float(reg["p"].sum())
    )
    opp = V.opportunity_cost_table(
        params,
        N,
        float(full["incremental_dollars"]),
        int(full["incremental_checks"]),
        current,
        int(vcfg["pa_published_checks_per_year"]),
        float(config.raw["census"]["award_dollars"]),
    )
    summary = pd.read_csv(config.path("outputs") / "schedule_summary.csv")
    whatif = pd.concat(
        [
            V.whatif_census(travel, params, vcfg["whatif_day_hours"], vcfg["whatif_teams"]).assign(
                scenario="census floor"
            ),
            V.whatif_capped(summary, vcfg["whatif_day_hours"], (1, 2, 3)).assign(
                scenario="capped plan"
            ),
        ],
        ignore_index=True,
    )
    robustness = V.lambda_robustness(
        config, cand, vcfg["lambdas"], config.capacity.budget_inspections
    )
    restated = pd.DataFrame(
        {
            "quantity": [
                "break-even visibility shape (gamma_power)",
                "max hidden sigma consistent with observed lift",
            ],
            "value": [reg["break_even_power"], reg["max_sigma"]],
            "source": ["regime_shape_sweep.csv", "regime_second_pass.csv"],
        }
    )
    out = {
        "marginal": marginal,
        "break_even": break_even,
        "opportunity": opp,
        "whatif": whatif,
        "robustness": robustness,
        "restated": restated,
        "regime": reg,
    }
    if write:
        outdir = config.path("outputs")
        outdir.mkdir(parents=True, exist_ok=True)
        for key in ("marginal", "break_even", "opportunity", "whatif", "robustness", "restated"):
            out[key].to_csv(outdir / f"valuation_{key}.csv", index=False)
    return out


def figures(config, names=None, out_dir=None, write=True):
    """Render the report figures; with `write`, save PNGs to `out_dir` (default paths.figures)."""
    from tobacco_inspect import viz
    from tobacco_inspect.viz.data import load_viz_data

    data = load_viz_data(config)
    if not write:
        return {n: viz.render(n, data, config) for n in (names or viz.FIGURES)}
    return viz.export_all(data, config, out_dir or config.path("figures"), names)


def figures_from_specs(config, spec_paths, out_dir=None):
    """Render chart-builder spec JSON files (saved from the dashboard) to PNGs."""
    from tobacco_inspect import viz
    from tobacco_inspect.viz.data import load_viz_data
    from tobacco_inspect.viz.registry import export_png
    from tobacco_inspect.viz.spec import ChartSpec

    data = load_viz_data(config)
    out_dir = out_dir or config.path("figures")
    dpi = int(config.raw["viz"]["dpi"])
    return [
        export_png(
            viz.render_spec(ChartSpec.from_json(Path(p).read_text(encoding="utf-8")), data, config),
            Path(out_dir) / f"{Path(p).stem}.png",
            dpi,
        )
        for p in spec_paths
    ]
