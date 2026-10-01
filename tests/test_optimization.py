"""Offline tests for the optimization stage: features, risk, prize, scheduling, evaluation."""

import copy

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest
import yaml

from tobacco_inspect.config import DEFAULT_CONFIG, ConfigError, load_config, parse_config
from tobacco_inspect.eval import baselines, equity, metrics, simulate
from tobacco_inspect.model import harrington, history, orienteering, prize, risk, thompson
from tobacco_inspect.routing import distance


def _solver():
    for name in ("gurobi", "appsi_highs"):
        if pyo.SolverFactory(name).available(exception_flag=False):
            return name
    pytest.skip("no MILP solver available")


# --------------------------------------------------------------------------- config
def test_cycle_arithmetic():
    cap = load_config().capacity
    assert cap.cycles == cap.horizon_weeks // cap.cycle_weeks
    assert cap.cycle_budget * cap.cycles >= cap.budget_inspections
    assert cap.cycle_days == 5 * cap.cycle_weeks


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["capacity"].update(cycle_weeks=99),
        lambda d: d["risk"].update(kappa=0),
        lambda d: d["harrington"].update(state_weights=[1, 2]),
        lambda d: d["prize"].update(site_mix={"school": 0.5, "youth_site": 0.4}),
        lambda d: d["data"].update(scope="county"),
    ],
)
def test_new_config_sections_validated(mutate):
    with open(DEFAULT_CONFIG, encoding="utf-8") as fh:
        data = copy.deepcopy(yaml.safe_load(fh))
    mutate(data)
    with pytest.raises(ConfigError):
        parse_config(data)


# --------------------------------------------------------------------------- history features
def _checks():
    d = pd.to_datetime
    return pd.DataFrame(
        {
            "Retailer Name": ["JOE'S MART #1"] * 4 + ["OTHER SHOP"],
            "location_key": ["A|1"] * 4 + ["B|2"],
            "decision_date_parsed": d(
                ["2020-01-01", "2020-06-01", "2021-03-01", "2022-01-01", "2021-01-01"]
            ),
            "underage_sale_violation": [1, 0, 1, 0, 0],
            "fy": [2020, 2020, 2021, 2022, 2021],
            "up_involved": [True] * 5,
        }
    )


def test_history_features_use_only_past_records_and_lag():
    h = history.build_index(_checks())["A|1"]
    f = history.history_features(h, "2021-03-01", lag_days=30)
    assert f["n_prior_checks"] == 2  # the 2021-03-01 record itself is inside the lag guard
    assert f["n_prior_viol"] == 1 and f["viol_12m"] == 0 and f["viol_24m"] == 1
    later = history.history_features(h, "2021-04-15", lag_days=30)
    assert later["n_prior_checks"] == 3 and later["viol_12m"] == 1


def test_training_frame_is_leakage_safe():
    frame = history.build_training_frame(_checks(), lag_days=30)
    base = frame.set_index(["location_key", "decision_date_parsed"])
    changed = _checks()
    changed.loc[3, "underage_sale_violation"] = 1  # alter the LAST record (2022-01-01)
    frame2 = history.build_training_frame(changed, lag_days=30).set_index(
        ["location_key", "decision_date_parsed"]
    )
    cols = ["n_prior_viol", "viol_36m", "days_since_viol"]
    earlier = base.index[base.index.get_level_values(1) < "2022-01-01"]
    pd.testing.assert_frame_equal(base.loc[earlier, cols], frame2.loc[earlier, cols])


def test_name_key_strips_store_numbers():
    assert history.name_key("JOE'S MART #12") == history.name_key("Joe's Mart 7")


# --------------------------------------------------------------------------- harrington
def test_escalation_and_deterrence_monotone():
    assert list(harrington.escalation_depth([0, 2, 9])) == [0, 2, 4]
    assert list(harrington.targeted([0, 1, 3])) == [False, True, True]
    low = pd.DataFrame({"viol_36m": [0], "days_since_check": [100]})
    high = pd.DataFrame({"viol_36m": [3], "days_since_check": [400]})
    assert harrington.deterrence_gain(high)[0] > harrington.deterrence_gain(low)[0] > 0
    assert harrington.deterrence_gain(high)[0] <= 1.0


# --------------------------------------------------------------------------- thompson
def test_thompson_reproducible_and_centered():
    a, b = thompson.beta_prior_from_p(np.array([0.1, 0.5]), kappa=20)
    assert a / (a + b) == pytest.approx([0.1, 0.5])
    s1 = thompson.sample_violation_rates(a, b, np.random.default_rng(7))
    s2 = thompson.sample_violation_rates(a, b, np.random.default_rng(7))
    assert (s1 == s2).all()
    a2, b2 = thompson.update(a, b, checks=np.array([4, 4]), violations=np.array([4, 0]))
    assert a2[0] / (a2[0] + b2[0]) > 0.1 and a2[1] / (a2[1] + b2[1]) < 0.5


def test_random_share_reserves_at_least_one_slot():
    rng = np.random.default_rng(1)
    picks = thompson.random_share_pick(4, 0.2, np.arange(50), rng)
    assert len(picks) == 1 and len(set(picks)) == 1
    assert len(thompson.random_share_pick(4, 0.0, np.arange(50), rng)) == 0


# --------------------------------------------------------------------------- prize
def test_youth_share_shrinkage_pulls_noisy_tracts_to_median():
    share = np.array([0.1, 0.2, 0.3, 0.9])
    tight = prize.shrink_youth_share(share, np.array([0.01] * 4))
    noisy = prize.shrink_youth_share(share, np.array([0.01, 0.01, 0.01, 0.8]))
    assert abs(noisy[3] - np.median(share)) < abs(tight[3] - np.median(share))


def test_prize_formula():
    cfg = load_config()
    r = prize.compute_prizes(cfg, np.array([0.5]), np.array([0.2]), np.array([1.0]))
    assert r[0] == pytest.approx(0.5 * 0.2 + cfg.prize["lambda_deterrence"] * 1.0)


# --------------------------------------------------------------------------- risk
def test_calibration_shift_hits_target_and_keeps_ranking():
    p = np.array([0.05, 0.1, 0.2, 0.4])
    q, delta = risk.calibrate_to_population_rate(p, 0.3)
    assert q.mean() == pytest.approx(0.3, abs=1e-6)
    assert (np.argsort(p) == np.argsort(q)).all() and delta > 0


def test_lift_at_k_perfect_ranking():
    y = np.array([1] * 10 + [0] * 90)
    lift, lo, hi = risk.lift_at_k(y, y.astype(float), 0.1, np.random.default_rng(0), n_boot=50)
    assert lift == pytest.approx(10.0) and lo <= lift <= hi


def test_fit_risk_model_learns_signal():
    rng = np.random.default_rng(0)
    n = 3000
    frame = pd.DataFrame({c: rng.normal(size=n) for c in history.NUMERIC})
    frame["outlet_type"] = rng.choice(["a", "b"], n)
    logit = 1.5 * frame["viol_36m"] - 1.0
    frame["y"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    frame["fy"] = rng.choice([2020, 2021, 2022], n)
    model = risk.fit_risk_model(frame)
    assert risk.evaluate(frame["y"], model.predict(frame))["auc"] > 0.7


# --------------------------------------------------------------------------- routing and MILP
def test_haversine_matrix_properties():
    lons, lats = [-80.0, -79.99, -79.95], [40.44, 40.45, 40.46]
    m = distance.haversine_minutes(lons, lats)
    assert np.allclose(m, m.T) and np.allclose(np.diag(m), 0)
    assert 2 < m[0, 1] < 6  # about 1.4 km straight line -> a few minutes


TRAVEL = [
    [0, 10, 10, 30, 30],
    [10, 0, 5, 30, 30],
    [10, 5, 0, 30, 30],
    [30, 30, 30, 0, 5],
    [30, 30, 30, 5, 0],
]
PRIZES = [0, 5, 6, 20, 1]
SERVICE = [0, 2, 2, 2, 2]


def test_team_orienteering_respects_budget_time_and_once():
    plan = orienteering.solve_team_orienteering(
        PRIZES, TRAVEL, SERVICE, day_minutes=30, n_routes=2, budget=3, solver=_solver()
    )
    assert len(plan.visited) == len(set(plan.visited)) <= 3
    assert all(t <= 30 + 1e-6 for t in plan.times)
    assert plan.prize >= 11  # cluster {1,2} fits one 30-minute route


def test_team_orienteering_floor_forces_a_visit():
    plan = orienteering.solve_team_orienteering(
        PRIZES,
        TRAVEL,
        SERVICE,
        day_minutes=70,
        n_routes=1,
        budget=3,
        floors=[([4], 1)],
        solver=_solver(),
    )
    assert 4 in plan.visited


def test_infeasible_floor_raises_clear_error():
    with pytest.raises(ValueError, match="infeasible"):
        orienteering.solve_team_orienteering(
            PRIZES,
            TRAVEL,
            SERVICE,
            day_minutes=30,
            n_routes=1,
            budget=3,
            floors=[([4], 1)],
            solver=_solver(),
        )


def test_milp_is_never_worse_than_ranked_batched():
    kwargs = dict(day_minutes=30, n_routes=1, budget=4)
    milp = orienteering.solve_team_orienteering(PRIZES, TRAVEL, SERVICE, solver=_solver(), **kwargs)
    heur = orienteering.plan_ranked_batched(PRIZES, TRAVEL, SERVICE, **kwargs)
    assert milp.prize >= heur.prize - 1e-9
    assert all(t <= 30 + 1e-6 for t in heur.times)


# --------------------------------------------------------------------------- evaluation
def test_baselines_and_metrics():
    frame = pd.DataFrame(
        {
            "viol_36m": [0, 2, 0, 1],
            "n_prior_viol": [0, 2, 0, 1],
            "days_since_viol": [1825, 100, 1825, 400],
            "viol_12m": [0, 1, 0, 0],
            "days_since_check": [200, 300, 900, 500],
        }
    )
    rng = np.random.default_rng(0)
    assert baselines.prior_violators_first(frame, 1, rng)[0] == 1
    assert baselines.status_quo_followup(frame, 1, rng)[0] == 1
    assert len(set(baselines.random_baseline(4, 3, rng))) == 3
    p = np.array([0.1, 0.5, 0.1, 0.3])
    assert metrics.expected_violations([1, 3], p) == pytest.approx(0.8)
    assert metrics.violations_per_hour([1, 3], p, 120) == pytest.approx(0.4)
    assert metrics.jaccard([1, 2], [2, 3]) == pytest.approx(1 / 3)
    assert metrics.unpredictability([[1, 2], [3, 4]])["unpredictability"] == 1.0


def test_nearest_neighbor_stays_inside_day():
    tour = baselines.nearest_neighbor(np.array(TRAVEL, float), np.array(SERVICE, float), 40, 5)
    assert tour[0] in (1, 2) and len(tour) >= 2


def test_equity_audit():
    uni = pd.DataFrame(
        {
            "license_id": list("abcd"),
            "tract_geoid": ["t1", "t1", "t2", "t3"],
            "acs_poverty_rate": [0.4, 0.4, 0.1, 0.2],
            "acs_youth_share": [0.2] * 4,
        }
    )
    cov = equity.coverage_by_tract(uni, pd.Series([1, 1, 0, 0]))
    assert cov.set_index("tract_geoid").loc["t1", "inspections_per_retailer"] == 1.0
    summary = equity.equity_summary(cov)
    assert summary["tracts"] == 3 and summary["share_inspections_high_poverty"] == 1.0


def test_simulation_predictable_policy_is_exploitable():
    p = np.full(40, 0.3)
    top = np.arange(4)
    fixed = lambda c, h: top  # noqa: E731  same four stores every cycle
    rng_policy = np.random.default_rng(3)
    randomized = lambda c, h: rng_policy.choice(40, 4, replace=False)  # noqa: E731
    f = np.mean(
        [
            simulate.run(fixed, p, 4, 24, np.random.default_rng(i), rho=0.9)["total"]
            for i in range(30)
        ]
    )
    r = np.mean(
        [
            simulate.run(randomized, p, 4, 24, np.random.default_rng(i), rho=0.9)["total"]
            for i in range(30)
        ]
    )
    assert r > f
    # with no behavioral response the two policies are equivalent in expectation
    f0 = np.mean(
        [simulate.run(fixed, p, 4, 24, np.random.default_rng(i))["total"] for i in range(30)]
    )
    assert f0 == pytest.approx(0.3 * 4 * 24, rel=0.15)
